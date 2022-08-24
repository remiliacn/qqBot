import math
import random
import sqlite3
import time
from asyncio import gather
from json import loads, JSONDecodeError
from re import findall, sub, match
from time import sleep
from typing import Union
from urllib.parse import quote

from httpx import get, AsyncClient, HTTPError
from loguru import logger

from config import BUFF_SESSION_ID


# table = PrettyTable(['物品名', '获利', '挂刀比例', '详细'], encoding='utf-8-sig')


class BuffRequester:
    def __init__(self, is_debug=True):
        self.is_debug = is_debug
        self.data_table = []

        self._item_id_set = set()
        self.connection = sqlite3.connect('data/db/itemId.db')
        self.sleep_time = lambda: 310 + random.randint(2, 8)
        self.just_tried_long_sleep = False

        self.BUFF_FETCH_LIMIT = 20 if self.is_debug else 2
        self.IGXE_FETCH_LIMIT = 30 if self.is_debug else 2
        self.BUFF_FETCH_WAIT_TIME = 20

        # strategy = 'sell_strategy'
        self.strategy = 'buy_strategy'
        self.CN_TO_REAL = .75

        self.STRATEGY = {
            'sell_strategy': {
                'graph_list_name': 'sell_order_graph',
                'single_order_name': 'lowest_sell_order'
            },
            'buy_strategy': {
                'graph_list_name': 'buy_order_graph',
                'single_order_name': 'highest_buy_order'
            }
        }

        self.GENERAL_HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/104.0.0.0 Safari/537.36'
        }

        self.BUFF_SESSION_ID = BUFF_SESSION_ID

        self.target_rate = self._get_target_rate()
        self.STABLE_SELL_VOLUME = 10

        self.BLACKLIST_KEYWORD = ['纪念品', '胶囊', '武器箱', '盎然春意', '封装的涂鸦']

        self.BUFF_HEADERS = {
            'Cookie': f'session={self.BUFF_SESSION_ID};',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/104.0.0.0 Safari/537.36'
        }

        _item_id_set = set()

    def clear_table_content(self):
        self.data_table.clear()

    def get_table_content(self):
        response = ''
        for data in self.data_table:
            response += f'{data[0]:<30} | {data[1]:<12} | {data[2]:<12} | {data[3]}\n'

        return response

    def has_new_data(self):
        return len(self.data_table) > 0

    def set_target_rate(self, rate: float):
        self.target_rate = rate
        self.connection.execute(
            """
            insert or replace into item_id (market_hash, item_id) values ('target_rate', ?)
            """, (str(self.target_rate),)
        )
        self.connection.commit()

    def _get_target_rate(self):
        result = self.connection.execute(
            """
            select item_id from item_id where market_hash = 'target_rate' limit 1;
            """
        ).fetchone()

        if result is not None:
            try:
                return float(result)
            except ValueError:
                pass

        return 0.73

    def clear_item_id_set(self):
        self._item_id_set.clear()

    def get_rows_count_in_db(self) -> int:
        return self.connection.execute(
            """
            select count(*) from item_id
            """
        ).fetchone()[0]

    def store_item_id(self):
        logger.info('Commiting database change.')
        self.connection.commit()

    def insert_item_id(self, name: str, item_id: str):
        self.connection.execute(
            f"""
            INSERT OR IGNORE INTO item_id (market_hash, item_id)
            VALUES('{name}', '{item_id}');
            """
        )

    def get_stored_item_id(self, name: str) -> Union[None, str]:
        rows = self.connection.execute(f"""SELECT item_id FROM ITEM_ID WHERE market_hash = ?; """, (name,)).fetchone()
        return rows[0] if rows else None

    async def igxe_data_fetch(self):
        valid_data_list = []
        igxe_url = f'https://www.igxe.cn/market/csgo?sort=3&page_no={random.randint(1, 60)}' \
                   f'&page_size=20&_={int(time.time())}'
        page_response = get(igxe_url, timeout=None, headers=self.GENERAL_HEADERS)
        if page_response.status_code != 200:
            raise HTTPError("Igxe inaccessible...")

        page_response_text = page_response.text
        data = findall(r'return .*?dataList:\[(.*?)}]', page_response_text)[0]
        data_set = data.split('},')
        for element in data_set:
            elements = element + '}'
            targets = elements[1:].split(',')
            for target in targets:
                args = target.split(':')
                if len(args) < 2:
                    continue
                key = args[0]
                value = args[1]
                elements = elements.replace(f'{key}:', f'"{key}":', 1)
                if len(value) <= 2:
                    elements = elements.replace(f':{value},', f':"{value}",', 1)
                    elements = elements.replace(f':' + value + '}', f':"' + value + '"}', 1)

                elements = sub(r'[a-z]}', '"f"}', elements)

                if match(r'\.\d+', value):
                    elements = elements.replace(value, f'0{value},' if ',' in value else f'0{value}')

            try:
                returned_data = loads(elements)
                valid_data_list.append(returned_data)
            except JSONDecodeError:
                logger.error('Decode failed, need check')
                print(elements)

        return valid_data_list

    async def fetch_igxe_data(self, item: dict):
        original = item['min_price']
        if isinstance(original, str) and not original.isdigit():
            return

        original = float(original)
        if len(item['name']) < 3:
            return

        await self.market_worker(item, original, 'igxe')

    async def gather_igxe_tasks(self, items):
        tasks = []
        for item in items:
            item_name = item['name']
            item_id = item['id']
            if item_id in self._item_id_set:
                logger.warning(f'{item_name} already fetched, skipping...')
                continue
            else:
                self._item_id_set.add(item_id)

            for word in self.BLACKLIST_KEYWORD:
                if word in item_name:
                    logger.warning(f'Skipping {item_name} because {word} in blacklist.')
                    break
            else:
                tasks.append(self.fetch_igxe_data(item))

        return tasks

    async def do_igxe_work(self):
        i = 1
        while i <= self.IGXE_FETCH_LIMIT:
            items = await self.igxe_data_fetch()

            tasks = await self.gather_igxe_tasks(items)
            start_time = time.time()
            await self.process_buff_batch_tasks(tasks)

            sleep_time_diff = self.BUFF_FETCH_WAIT_TIME - round(int(time.time()) - start_time)
            buff_fetch_sleeptime = sleep_time_diff if sleep_time_diff >= 6 else self.BUFF_FETCH_WAIT_TIME

            if self.is_debug:
                logger.info(f'Sleeping {buff_fetch_sleeptime} seconds before fetching next igxe page.')
                sleep(buff_fetch_sleeptime)

            i += 1

    def item_id_init(self):
        logger.info('Initializing item id...')
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS item_id (
                "market_hash" TEXT UNIQUE ON CONFLICT IGNORE, 
                "item_id" TEXT
            )
            """
        )
        self.connection.commit()

    @staticmethod
    def calculate_fee_helper(received_amount: float) -> dict:
        steam_fee = math.floor(max(received_amount * 0.05, 1))
        publisher_fee = math.floor(max(received_amount * .1, 1))
        amount_to_send = received_amount + steam_fee + publisher_fee

        return {
            'steam_fee': steam_fee,
            'publisher_fee': publisher_fee,
            'fees': steam_fee + publisher_fee,
            'amount': amount_to_send
        }

    def calculate_fee(self, amount: Union[int, float, str]) -> float:
        if isinstance(amount, str):
            amount = round(float(amount))

        iteration = 0
        estimated_amount_of_wallet = math.floor(amount / (0.05 + 0.1 + 1))
        ever_undershot = False
        fees = self.calculate_fee_helper(estimated_amount_of_wallet)

        while fees['amount'] != amount and iteration < 10:
            if fees['amount'] > amount:
                if ever_undershot:
                    fees = self.calculate_fee_helper(estimated_amount_of_wallet - 1)
                    fees['steam_fee'] += amount - fees['amount']
                    fees['amount'] = amount
                    break
                else:
                    estimated_amount_of_wallet -= 1
            else:
                ever_undershot = True
                estimated_amount_of_wallet += 1

            fees = self.calculate_fee_helper(estimated_amount_of_wallet)
            iteration += 1

        return amount - fees['fees']

    @staticmethod
    def calculate_rate(price: [int, float], highest_buy_order: Union[int, float]):
        if highest_buy_order < 0.01:
            return 9999999

        low_ratio = round(price / highest_buy_order, 2)
        return low_ratio

    async def get_item_id_from_steam(self, item: dict) -> list:
        market_hash = quote(item['market_hash_name'])
        appid = item['appid'] if 'appid' in item else '730'

        stored_item_id = self.get_stored_item_id(market_hash)
        if stored_item_id is not None:
            logger.success(f'Using stored item_id: {stored_item_id}')
            return [stored_item_id]

        logger.info(f'No cache, gathering item id from steam for {market_hash}')
        marketplace_url = f'https://steamcommunity.com/market/listings/{appid}/{market_hash}'

        try:
            market_page_text = get(marketplace_url, timeout=None)

            if market_page_text.status_code == 429:
                if not self.just_tried_long_sleep:
                    self.just_tried_long_sleep = True
                    logger.warning(f'Getting 429 while fetching item id, sleeping {self.sleep_time()} seconds')
                    self.store_item_id()
                    if self.is_debug:
                        sleep(self.sleep_time())
                    else:
                        return ['22774494']
                else:
                    logger.warning(f'429, retrying...')
                    if self.is_debug:
                        sleep(80)
                    else:
                        return ['22774494']

                return await self.get_item_id_from_steam(item)

            market_page_text = market_page_text.text
        except HTTPError as err:
            timeout_random = random.randint(2, 5)
            logger.warning(f'Timeout error, retrying in {timeout_random} seconds... {err.__class__.__name__}')
            if self.is_debug:
                sleep(timeout_random)
                return await self.get_item_id_from_steam(item)
            else:
                return ['22774494']

        item_id_market = findall(r'Market_LoadOrderSpread\( (\d+)', market_page_text)
        if item_id_market:
            self.insert_item_id(market_hash, item_id_market[0])
            return item_id_market

        return ['-1']

    async def fetch_highest_buy(self, item_id_market: list) -> (float, int):
        if item_id_market[0] == -1:
            return 0.01

        market_detail_url = f'https://steamcommunity.com/market/itemordershistogram' \
                            f'?country={"BR" if self.is_debug else "CN"}' \
                            f'&language=schinese' \
                            f'&currency={"7" if self.is_debug else "23"}&item_nameid={item_id_market[0]}' \
                            f'&two_factor=0&_={time.time()}'

        async with AsyncClient() as client:
            market_detail_json = await client.get(market_detail_url, timeout=None, headers=self.GENERAL_HEADERS)
            if market_detail_json.status_code == 500:
                return 0.01
            market_detail_json = market_detail_json.json()

        sell_average = 0
        sell_average_after_fee = 0
        price_length_count = 0
        volume_count = 0

        maybe_fraud = False

        if market_detail_json and market_detail_json is not None:
            key_name = self.STRATEGY[self.strategy]['graph_list_name']
            if key_name not in market_detail_json:
                return 1e-6, 0

            price_lists = market_detail_json[key_name]

            if len(price_lists) > 2:
                first_sale_price = price_lists[0][0]
                second_sale_price = price_lists[1][0]
                ratio = round((first_sale_price - second_sale_price) / first_sale_price, 2)

                if ratio > 0.92:
                    logger.warning(f'Probably fraud listing, ratio higher than 92% {ratio}')
                    logger.warning(f'1. {first_sale_price}, 2. {second_sale_price}')
                    maybe_fraud = True

            for price_content in price_lists[:self.STABLE_SELL_VOLUME - 2]:
                if volume_count > self.STABLE_SELL_VOLUME:
                    break
                sell_average += price_content[0]
                volume_count += price_content[1]
                price_length_count += 1
            else:
                sell_average *= 3

            sell_average /= (price_length_count if sell_average > 0 else 0.01)
            sell_average_after_fee = self.calculate_fee(sell_average * 100) / 100

        if sell_average_after_fee < 0.0001:
            try:
                sell_average_after_fee = self.calculate_fee(
                    float(market_detail_json[self.STRATEGY[self.strategy]['single_order_name']])
                ) / 100
            except TypeError:
                return 1e-6, sell_average

        logger.success(f'Gathering price info for {item_id_market[0]} succeed.')
        return round(sell_average_after_fee, 2) if not maybe_fraud else 1e-6, sell_average

    async def extract_market_price(self, item: dict) -> (float, int):
        item_id_market = await self.get_item_id_from_steam(item)

        while not item_id_market and self.is_debug:
            logger.warning(f'not able to get item id, retrying in {self.sleep_time()} seconds.')
            self.store_item_id()
            sleep(self.sleep_time())
            item_id_market = await self.get_item_id_from_steam(item)
        else:
            if item_id_market:
                try:
                    fetch_result = await self.fetch_highest_buy(item_id_market)
                    return fetch_result
                except HTTPError as err:
                    logger.warning(f'Encountering error while fetching price data, '
                                   f'sleeping {self.sleep_time() / 5} seconds. {err.__class__.__name__}')
                    if self.is_debug:
                        sleep(self.sleep_time() / 5)
                        fetch_result = await self.fetch_highest_buy(item_id_market)
                        return fetch_result
                    else:
                        return 0.01

            fetch_result = await self.extract_market_price(item)
            self.just_tried_long_sleep = False
            return fetch_result

    async def market_worker(self, item: dict, original: float, platform: str):
        item_min_price = round(original * (self.CN_TO_REAL if self.is_debug else 1), 2)
        deal_price, deal_price_before_fee = await self.extract_market_price(item)

        item_name = item['name']

        rate = self.calculate_rate(item_min_price, deal_price)
        deal_price = round(deal_price, 2)
        item_id = item['id']
        url = f'buff.163.com/goods/{item_id}' \
            if platform == 'buff' else f'www.igxe.cn/product/730/{item_id}'
        if not rate > self.target_rate:
            # currency = 'BR $' if self.is_debug else '￥'
            # br_item_min = f'({currency}{item_min_price})'
            # br_deal_price = f'{currency}{deal_price}'
            # br_before_fee = f'{currency}{deal_price_before_fee}'
            self.data_table.append(
                [
                    item_name,
                    f'￥{original}',
                    str(rate),
                    url
                ]
            )

        logger.info(f'Item: {item_name} '
                    f'rate: {rate} {self.strategy[:3]}: {deal_price}')

    async def fetch_buff_data(self, item: dict):
        original = float(item['sell_min_price'])
        await self.market_worker(item, original, 'buff')

    async def get_buff_tasks(self) -> [callable]:
        i = random.randint(1, 30) if 'Cookie' in self.BUFF_HEADERS or not self.is_debug else 1
        logger.info(f'Fetching page {i}')
        buff_request = get(
            f'https://buff.163.com/api/market/goods?game={random.choice(["dota2", "csgo"])}'
            f'&page_num={i}&page_size=10&_={int(time.time())}',
            headers=self.BUFF_HEADERS, timeout=10
        ).json()
        if 'data' not in buff_request:
            logger.error('No data')
            return

        buff_request = buff_request['data']
        if 'items' not in buff_request or not buff_request['items']:
            logger.error('No item')
            return

        logger.info('Fetching buff data...')

        buff_items = buff_request['items']
        tasks = []

        logger.info('Fetching buff data done, collecting tasks...')
        for item in buff_items:
            item_name = item['name']
            item_id = item['id']
            if item_id in self._item_id_set:
                logger.warning(f'{item_id} already fetched, skipping...')
                continue
            else:
                self._item_id_set.add(item_id)

            listing_on_buff_count = item['sell_num']
            if listing_on_buff_count < 5:
                logger.warning(f'Item {item_name} has only {listing_on_buff_count} listings on buff, aborting')
                continue

            for word in self.BLACKLIST_KEYWORD:
                if word in item_name:
                    logger.warning(f'Skipping {item_name} because {word} in blacklist.')
                    break
            else:
                if len(item_name) > 2:
                    tasks.append(self.fetch_buff_data(item))

        return tasks

    async def process_buff_batch_tasks(self, tasks: [callable]):
        if tasks is None:
            return

        logger.info(f'Collecting data done, firing batch job, size: {len(tasks)}')

        await gather(*tasks)

        self.just_tried_long_sleep = False
        self.store_item_id()

    async def do_buff_work(self):
        i = 1
        while i <= (self.BUFF_FETCH_LIMIT if self.is_debug else 1):
            tasks = await self.get_buff_tasks()
            start_time = time.time()
            await self.process_buff_batch_tasks(tasks)
            i += 1

            sleep_time_diff = self.BUFF_FETCH_WAIT_TIME - round(int(time.time()) - start_time)
            buff_fetch_sleeptime = sleep_time_diff if sleep_time_diff >= 6 else self.BUFF_FETCH_WAIT_TIME

            if self.is_debug:
                logger.info(f'Sleeping {buff_fetch_sleeptime} seconds before fetching next buff page.')
                sleep(buff_fetch_sleeptime)
