import copy
import re
import time
from datetime import datetime
from json import dump, loads
from os import getcwd
from os.path import exists
from typing import Union, Dict

from loguru import logger

from Services.stock import Stock, Crypto


class SimulateStock:
    def __init__(self):
        self.STOCK_NOT_EXISTS = '未开盘或股票不存在（如果不确定股票代码，请使用！股票 名称来找一下~）'
        self.NO_INFO = '您啥还没买呢哦~'
        self.CACHE_EXPIRATION = 80
        self.USD_TO_CNY = 6.35

        self.user_record_filename = f'{getcwd()}/Services/util/userStockRecord.json'
        self.stock_record_file = f'{getcwd()}/Services/util/stockTypeRecord.json'
        self.stock_price_cache: Dict[str: Union[str, float]] = {}
        self.user_stock_data = {"data": {}}

        if not exists(self.user_record_filename):
            self._init_store_user()
        if not exists(self.stock_record_file):
            self._init_store_stock()

        self.user_stock_data = self._read_user_stock_data()
        self.stock_price_cache = self._read_stock_data()

    def _read_user_stock_data(self) -> dict:
        with open(self.user_record_filename, encoding='utf-8') as file:
            return loads(file.read())

    def _read_stock_data(self) -> dict:
        with open(self.stock_record_file, encoding='utf-8') as file:
            return loads(file.read())

    def _init_store_user(self):
        with open(self.user_record_filename, 'w+', encoding='utf-8') as file:
            dump({"data": {}}, file, indent=4, ensure_ascii=False)

    def _init_store_stock(self):
        with open(self.stock_record_file, 'w+', encoding='utf-8') as file:
            dump({}, file, indent=4, ensure_ascii=False)

    def _store_user_data(self):
        with open(self.user_record_filename, 'w+', encoding='utf-8') as file:
            dump(self.user_stock_data, file, indent=4, ensure_ascii=False)

    def _store_stock_data(self):
        with open(self.stock_record_file, 'w+', encoding='utf-8') as file:
            dump(self.stock_price_cache, file, indent=4, ensure_ascii=False)

    async def get_all_stonk_log_by_user(self, uid: Union[int, str], ctx=None):
        uid = str(uid)
        try:
            stonk_whole_log = self.user_stock_data['data'][uid]
        except KeyError:
            return self.NO_INFO

        if not stonk_whole_log:
            return self.NO_INFO

        response = [await self.my_money_spent_by_stock_code(uid, stock_code) for stock_code in stonk_whole_log]
        time_awareness = ''
        if datetime.now().hour == 12:
            time_awareness = '【午间休市】\n'
        elif datetime.now().hour == 11 and datetime.now().minute >= 30:
            time_awareness = '【午间休市】\n'
        elif datetime.now().hour >= 15 or (datetime.now().hour <= 9 and datetime.now().minute <= 30):
            time_awareness = '【休市】\n'
        elif datetime.now().hour == 9 and 15 <= datetime.now().minute <= 25:
            time_awareness = '【集合竞价·开盘】\n'
        elif datetime.now().hour == 14 and datetime.now().minute >= 57:
            time_awareness = '【集合竞价·收盘】\n'

        # backfill
        self._backfill_nickname(uid, ctx)
        response = [x for x in response if x]
        return f'{time_awareness}' + '\n'.join(response)

    def _backfill_nickname(self, uid: Union[str, int], ctx=None):
        if ctx is not None:
            try:
                self.user_stock_data['data'][uid]['nickname'] = ctx['sender']['nickname']
            except KeyError:
                pass

            self._store_user_data()

    async def get_all_user_info(self):
        user_data = copy.deepcopy(self.user_stock_data)
        data = user_data['data']
        response = ''
        user_data_info = []
        for uid in data:
            data = await self._get_user_overall_stat(uid)
            user_data_info.append(data)

        if len(user_data_info) > 3:
            sorted_list_reverse = sorted(user_data_info, key=lambda d: d["ratio"], reverse=True)
            sorted_list = sorted_list_reverse[::-1][:3]
            sorted_list_reverse = sorted_list_reverse[:3]
        else:
            sorted_list_reverse = sorted(user_data_info, key=lambda d: d["ratio"], reverse=True)
            sorted_list = sorted_list_reverse[::-1]

        response += f'龙虎榜：\n\n'
        for idx, data in enumerate(sorted_list_reverse):
            response += f'收益第{idx + 1}: {data["nickname"]}\n' \
                        f'【总资产{data["total"]:.2f}软妹币' \
                        f'（总收益率：{data["ratio"]:.2f}% {"↑" if data["ratio"] > 0 else "↓"}）】\n'

        response += f'\n韭菜榜：\n\n'
        for idx, data in enumerate(sorted_list):
            response += f'收益倒数第{idx + 1}: {data["nickname"]}\n' \
                        f'【总资产{data["total"]:.2f}软妹币' \
                        f'（总收益率：{data["ratio"]:.2f}% {"↑" if data["ratio"] > 0 else "↓"}）】\n'

        return response.strip()

    async def sell_stock(self, uid: Union[int, str], stock_code: str, amount: str, ctx=None):
        stock_code = stock_code.upper() if len(stock_code) <= 4 else stock_code
        if not amount.isdigit():
            try:
                amount = float(amount)
            except ValueError:
                return f'卖不了{amount}'

        uid = str(uid)
        amount = round(float(amount), 2)

        price_now, is_digital_coin, \
        stock_name, stock_api, _ = await self._determine_stock_price_digital_name(stock_code)

        if price_now < 0:
            return stock_name

        if not is_digital_coin:
            if amount < 100 or amount % 100 != 0:
                return '出售数量必须为大于100且为100倍数的正整数'
        else:
            if amount <= 0:
                return '?'

        try:
            data = self.user_stock_data['data'][uid][stock_code]
            purchase_count = data['purchaseCount']
            if purchase_count < amount:
                return '您没那么多谢谢'

            price_now, is_digital_coin, \
            stock_name, stock_api, _ = await self._determine_stock_price_digital_name(stock_code)

            if price_now < 0:
                return stock_name

            self.user_stock_data['data'][uid][stock_code]['purchaseCount'] -= amount

            price_earned = price_now * amount
            self.user_stock_data['data'][uid]['totalMoney'] += price_earned * 0.999
            fee = price_earned * .001
            if self.user_stock_data['data'][uid][stock_code]['purchaseCount'] == 0:
                del self.user_stock_data['data'][uid][stock_code]
            else:
                self.user_stock_data['data'][uid][stock_code]['moneySpent'] -= price_earned
                self.user_stock_data['data'][uid][stock_code]['purchasePrice'] = \
                    self.user_stock_data['data'][uid][stock_code]['moneySpent'] / \
                    self.user_stock_data['data'][uid][stock_code]['purchaseCount']

            self._backfill_nickname(uid, ctx)
            self._store_user_data()
            return f'您已每{"股" if not is_digital_coin else "个"}{price_now}' \
                   f'软妹币的价格卖出了{amount}{"股" if not is_digital_coin else "个"}' \
                   f'{stock_name}（印花税：{fee:.2f}软妹币），' \
                   f'现在您有{self.user_stock_data["data"][uid]["totalMoney"]:.2f}软妹币了~'

        except KeyError:
            return self.NO_INFO

    async def _get_user_overall_stat(self, uid: Union[int, str]) -> dict:
        data = self.user_stock_data['data']
        uid = str(uid)
        try:
            total_money = data[uid]['totalMoney']
            if 'nickname' in data[uid]:
                nickname = data[uid]['nickname']
            else:
                nickname = '匿名'

            current_stock_money = 0
            for stock in data[uid]:
                if not isinstance(data[uid][stock], dict):
                    continue

                if stock not in self.stock_price_cache:
                    logger.warning(f'Reading {stock}')
                    price_now, is_digital_coin, \
                    stock_name, stock_api, _ = await self._determine_stock_price_digital_name(stock)

                    if price_now < 0:
                        return stock_name
                else:
                    price_now = await self._get_stock_price_from_cache_by_identifier(stock)
                current_stock_money += price_now * data[uid][stock]['purchaseCount']

            total_money += current_stock_money
            ratio = ((total_money - (10 ** 6 * 5)) / (10 ** 6 * 5)) * 100

            return {
                "total": total_money,
                "ratio": ratio,
                "nickname": nickname
            }

        except KeyError:
            return {}

    async def my_money_spent_by_stock_code(self, uid: Union[int, str], stock_code: str) -> (str, float, float):
        uid = str(uid)
        stock_code = stock_code.upper() if len(stock_code) <= 4 else stock_code
        try:
            stock_to_check = self.user_stock_data['data'][uid][stock_code]
            if not isinstance(stock_to_check, dict):
                return ''
        except KeyError:
            return self.NO_INFO

        total_count = stock_to_check['purchaseCount']
        if total_count == 0:
            return ''

        total_money_spent = stock_to_check['moneySpent']
        avg_money = stock_to_check['purchasePrice']

        price_now, is_digital_coin, \
        stock_name, stock_api, _ = await self._determine_stock_price_digital_name(stock_code)
        if price_now < 0:
            return stock_name

        new_price = price_now * total_count
        rate = (new_price - total_money_spent) / total_money_spent * 100

        return f'{stock_name}[{stock_code}] x {total_count} -> 成本{total_money_spent:.2f}软妹币\n' \
               f'（最新市值：{new_price:.2f}软妹币 | ' \
               f'持仓盈亏：{rate:.2f}% {"↑" if rate > 0 else "↓"} | 平摊成本：{avg_money:.2f}软妹币/张）\n'

    async def _get_stock_price_from_cache_by_identifier(self, identifier) -> Union[int, float]:
        price_now, is_digital, \
        stock_name, stock_api, _ = await self._determine_stock_price_digital_name(identifier)

        return price_now

    async def buy_with_code_and_amount(
            self, uid: Union[int, str], stock_code: str, amount: Union[str, int], margin=1, ctx=None
    ) -> str:
        stock_code = stock_code.upper() if len(stock_code) <= 4 else stock_code
        if isinstance(amount, str):
            if not amount.isdigit():
                try:
                    amount = float(amount)
                except ValueError:
                    return '购买数量不合法'

            amount = round(float(amount), 2)

        price_now, is_digital_coin, \
        stock_name, stock_api, _ = await self._determine_stock_price_digital_name(stock_code)
        if price_now < 0:
            return stock_name

        if not is_digital_coin:
            if amount < 100 or amount % 100 != 0:
                return '购买数量必须为大于100且为100倍数的正整数'
        else:
            if amount <= 0:
                return '?'

        data = self.user_stock_data['data']
        uid = str(uid)
        if uid not in data:
            # 初始资金500万应该够了吧？
            self.user_stock_data['data'][uid] = {"totalMoney": 10 ** 6 * 5}

        need_money = amount * price_now
        user_money = self.user_stock_data['data'][uid]['totalMoney']
        if need_money > user_money:
            return '您没钱了'

        self._backfill_nickname(uid, ctx)

        fee = need_money * 0.001
        if stock_code not in data[uid]:
            self.user_stock_data['data'][uid][stock_code] = {
                "purchasePrice": 0,
                "purchaseCount": 0,
                "moneySpent": 0,
                "margin": 1
            }

        self.user_stock_data['data'][uid]['totalMoney'] = user_money - need_money - fee

        self.user_stock_data['data'][uid][stock_code]["purchaseCount"] += amount
        self.user_stock_data['data'][uid][stock_code]["moneySpent"] += need_money
        self.user_stock_data['data'][uid][stock_code]["purchasePrice"] = round(
            self.user_stock_data['data'][uid][stock_code]["moneySpent"] /
            self.user_stock_data['data'][uid][stock_code]["purchaseCount"],
            2
        )
        self.user_stock_data['data'][uid][stock_code]['margin'] = margin
        self.user_stock_data['data'][uid][stock_code]['name'] = stock_name
        self.user_stock_data['data'][uid][stock_code]['type'] = stock_api.type \
            if isinstance(stock_api, Stock) else 'Crypto'

        self._store_user_data()
        return f'您花费了{need_money:.2f}软妹币已每{"股" if not is_digital_coin else "个"}{price_now:.2f}' \
               f'软妹币的价格购买了{amount}{"股" if not is_digital_coin else "个"}{stock_name}' \
               f'\n（印花税：{fee:.2f}软妹币，余额：{self.user_stock_data["data"][uid]["totalMoney"]:.2f}软妹币）'

    async def _determine_if_has_cache_or_expired(self, stock_code) -> (bool, dict):
        if stock_code in self.stock_price_cache:
            last_updated = self.stock_price_cache[stock_code]['lastUpdated']
            time_diff = time.time() - last_updated
            if time_diff < self.CACHE_EXPIRATION:
                return True, self.stock_price_cache[stock_code]
            else:
                # 虚拟盘24小时开所以寄~
                if not self.stock_price_cache[stock_code]['isDigital']:
                    # 如果本天是周末，且上次价格更新是周五，则直接返回数据，反之需要稍微更新一下
                    if datetime.today().weekday() >= 5:
                        return datetime.fromtimestamp(last_updated).weekday() >= 4, self.stock_price_cache[stock_code]

                # 最坏情况为上日14:59问的然后第二日9:30查房~
                if time_diff > 60 * 60 * 18:
                    return False, self.stock_price_cache[stock_code]

                # AB股闭市时间
                if self.stock_price_cache[stock_code]['stockType'] in (0, 1) \
                        and (datetime.now().hour < 9 or datetime.now().hour >= 15):
                    return True, self.stock_price_cache[stock_code]

                # 港股闭市时间
                if self.stock_price_cache[stock_code]['stockType'] == 116 \
                        and (datetime.now().hour < 9 or datetime.now().hour >= 16):
                    return True, self.stock_price_cache[stock_code]

                return False, self.stock_price_cache[stock_code]

        return False, {}

    async def _determine_stock_price_digital_name(self, stock_code) \
            -> (Union[float, int], bool, str, Union[Crypto, Stock, None, str]):
        is_digital_coin = False
        is_valid_store, get_stored_info = await self._determine_if_has_cache_or_expired(stock_code)
        stock_api = None

        if get_stored_info and is_valid_store:
            is_digital_coin = get_stored_info['isDigital']
            return get_stored_info['priceNow'], is_digital_coin, \
                   get_stored_info['stockName'], \
                   Stock(stock_code) if not is_digital_coin else Crypto(stock_code), stock_code

        if not stock_code.isdigit():
            # 虚拟币一般是全字母，然后有可能有“-USDT”的部分
            if re.match(r'^[A-Z-]+$', stock_code.upper().strip()):
                stock_api = Crypto(stock_code)
                price_now = stock_api.get_current_value() * self.USD_TO_CNY
                stock_name = stock_api.crypto_usdt
                is_digital_coin = True
            else:
                price_now = -1
                stock_name = ''

            # Price < 1 代表不是虚拟币，可能是美股？
            if price_now <= 0:
                stock_api = Stock(stock_code, keyword=stock_code)
                # 如果有stock_type，直接用，就不用猜了ε=(´ο｀*))
                if get_stored_info:
                    stock_api.set_type(get_stored_info['stockType'])

                price_now, stock_name = await stock_api.get_purchase_price(iteration=False)
                if price_now <= 0:
                    stock_code = await stock_api.get_stock_codes(get_one=True)
                    if not stock_code.isdigit():
                        return -1, False, '为了最小化bot的响应时间，请使用股票的数字代码购买~', None, stock_code
                    else:
                        price_now, is_digital_coin, \
                        stock_name, stock_api, stock_code = await self._determine_stock_price_digital_name(stock_code)

        else:
            stock_api = Stock(stock_code)
            price_now, stock_name = await stock_api.get_purchase_price()
            # debug的时候发现的，wtf？
            if price_now == '-':
                price_now = 0
            if price_now <= 0:
                return -1, False, self.STOCK_NOT_EXISTS, None, stock_code

        # 再查一次，因为有递归的情况~
        is_valid_store, has_existing_data = await self._determine_if_has_cache_or_expired(stock_code)
        if not is_valid_store and not has_existing_data:
            self.stock_price_cache[stock_code] = {
                'priceNow': price_now,
                'stockName': stock_name,
                'lastUpdated': int(time.time()),
                'isDigital': is_digital_coin,
                'stockType': stock_api.type if isinstance(stock_api, Stock) else stock_api.crypto_name
            }
        else:
            self.stock_price_cache[stock_code]['priceNow'] = price_now
            self.stock_price_cache[stock_code]['lastUpdated'] = int(time.time())

        self._store_stock_data()
        return price_now, is_digital_coin, stock_name, stock_api, stock_code
