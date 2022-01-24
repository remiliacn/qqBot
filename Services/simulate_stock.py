import copy
import re
import time
from datetime import datetime
from json import dump, loads
from os import getcwd
from os.path import exists
from random import randint
from typing import Union, Dict

from loguru import logger

from Services.stock import Stock, Crypto


def _get_price_sn_or_literal(n: float) -> str:
    if n < 0.01:
        return f'{n:.2e}'

    return f'{n:,.2f}'


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

    def reset_user(self, uid: Union[str, int]):
        uid = str(uid)
        if uid not in self.user_stock_data['data']:
            self.user_stock_data['data'][uid] = {"totalMoney": 5 * (10 ** 6)}

        if 'lastReset' in self.user_stock_data['data'][uid]:
            if time.time() - self.user_stock_data['data'][uid]['lastReset'] < 60 * 60 * 24 * 7:
                return '每一周只能remake一次哦~'

        self.user_stock_data['data'][uid] = {"totalMoney": 5 * (10 ** 6), 'lastReset': int(time.time())}
        self._store_user_data()
        return 'Done'

    async def get_all_stonk_log_by_user(self, uid: Union[int, str], ctx=None):
        uid = str(uid)
        try:
            stonk_whole_log = self.user_stock_data['data'][uid]
        except KeyError:
            return self.NO_INFO

        if not stonk_whole_log:
            return self.NO_INFO

        response = [await self.my_money_spent_by_stock_code(uid, stock_code) for stock_code in stonk_whole_log]
        time_now = datetime.now()

        if time_now.hour >= 15 or (time_now.hour == 9 and time_now.minute < 15 or time_now.hour < 9) \
                or time_now.weekday() >= 5:
            time_awareness = '【SZ·休市】\n'
        elif time_now.hour == 12:
            time_awareness = '【SZ·午间休市】\n'
        elif time_now.hour == 11 and time_now.minute >= 30:
            time_awareness = '【SZ·午间休市】\n'
        elif time_now.hour == 9 and 15 <= time_now.minute <= 29:
            time_awareness = '【SZ·集合竞价·开盘】\n'
        elif time_now.hour == 14 and time_now.minute >= 57:
            time_awareness = '【SZ·集合竞价·收盘】\n'
        else:
            time_awareness = '【SZ·交易中】\n'

        if time_now.weekday() >= 5 or (time_now.hour == 9 and time_now.minute < 30) or time_now.hour < 9:
            time_awareness += '【港股·休市】\n'
        elif time_now.hour >= 16:
            time_awareness += "【港股·休市】\n"
        else:
            time_awareness += "【港股·交易中】\n"

        time_awareness += '【虚拟货币·交易中】\n'

        # backfill
        self._backfill_nickname(uid, ctx)
        response = [x for x in response if x]
        user_data = await self.get_user_overall_stat(uid, 60 * 2)
        money_diff = user_data["total"] - 5 * 10 ** 6
        return f'{time_awareness}\n\n' \
               f'总资产{user_data["total"]:,.2f}软妹币\n' \
               f'总收益率：{user_data["ratio"]:,.2f}% {"↑" if user_data["ratio"] >= 0 else "↓"}\n' \
               f'账户盈亏：{"+ " if money_diff >= 0 else ""} {money_diff:,.2f}软妹币 {"↑" if money_diff >= 0 else "↓"}\n\n' \
               + '\n'.join(response)

    def _backfill_nickname(self, uid: Union[str, int], ctx=None):
        if ctx is not None:
            try:
                self.user_stock_data['data'][uid]['nickname'] = ctx['sender']['nickname']
            except KeyError:
                pass

            self._store_user_data()

    async def get_all_user_info(self, valid_time=None):
        user_data = copy.deepcopy(self.user_stock_data)
        data = user_data['data']
        response = ''
        user_data_info = []
        for uid in data:
            data = await self.get_user_overall_stat(uid, valid_time)
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
                        f'【总资产{data["total"]:,.2f}软妹币' \
                        f'（总收益率：{data["ratio"]:.2f}% {"↑" if data["ratio"] > 0 else "↓"}）】\n'

        response += f'\n韭菜榜：\n\n'
        for idx, data in enumerate(sorted_list):
            response += f'收益倒数第{idx + 1}: {data["nickname"]}\n' \
                        f'【总资产{data["total"]:,.2f}软妹币' \
                        f'（总收益率：{data["ratio"]:.2f}% {"↑" if data["ratio"] > 0 else "↓"}）】\n'

        return response.strip()

    def set_stock_cache(self, stock_code, stock_name, stock_type, price_now, is_digital):
        if price_now <= 0:
            return

        if not re.match(r'^[A-Z0-9]+$', stock_code):
            logger.warning(f'{stock_code} not valid?')
            return

        self.stock_price_cache[stock_code] = {
            "priceNow": price_now,
            "stockName": stock_name,
            "lastUpdated": int(time.time()),
            "isDigital": is_digital,
            "stockType": stock_type
        }

        self._store_stock_data()

    def get_type_by_stock_code(self, stock_code):
        try:
            return self.stock_price_cache[stock_code]['stockType']
        except KeyError:
            return None

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

        if price_now <= 0:
            return stock_name

        if not is_digital_coin:
            if amount < 100 or amount % 100 != 0:
                return '出售数量必须为大于100且为100倍数的正整数'
        else:
            if amount <= 0:
                return '?'

        try:
            if isinstance(stock_api, Stock):
                stock_code = stock_api.code

            data = self.user_stock_data['data'][uid][stock_code]
            purchase_count = data['purchaseCount']
            if purchase_count < amount:
                return '您没那么多谢谢'

            price_now, is_digital_coin, \
            stock_name, stock_api, _ = await self._determine_stock_price_digital_name(stock_code)

            if price_now <= 0:
                return stock_name

            special_event = ''
            random_num = randint(0, 99)
            if random_num < 10 or amount >= 1e4:
                random_percentage = randint(1, 70)
                ratio_change = 1 - random_percentage / 1e4

                price_now *= ratio_change
                special_event = f'\n(在您卖出的时候，该产品的价格出现了小幅波动： -{random_percentage / 1e2}%）'

            current_stock = self.user_stock_data['data'][uid][stock_code]
            current_stock['purchaseCount'] -= amount

            price_earned = price_now * amount
            self.user_stock_data['data'][uid]['totalMoney'] += price_earned * 0.999
            fee = price_earned * .001
            if current_stock['purchaseCount'] == 0:
                del self.user_stock_data['data'][uid][stock_code]
            else:
                current_stock['moneySpent'] -= price_earned
                current_stock['purchasePrice'] = \
                    current_stock['moneySpent'] / \
                    current_stock['purchaseCount']

            self._backfill_nickname(uid, ctx)
            self._store_user_data()
            return f'您已每{"股" if not is_digital_coin else "个"}{_get_price_sn_or_literal(price_now)}' \
                   f'软妹币的价格卖出了{amount}{"股" if not is_digital_coin else "个"}' \
                   f'{stock_name}{special_event}\n（印花税：{_get_price_sn_or_literal(fee)}软妹币），' \
                   f'现在您有{self.user_stock_data["data"][uid]["totalMoney"]:,.2f}软妹币了~'

        except KeyError:
            return self.NO_INFO

    async def get_user_overall_stat(self, uid: Union[int, str], valid_time) -> dict:
        data = self.user_stock_data['data']
        uid = str(uid)
        try:
            total_money = data[uid]['totalMoney']
            if 'nickname' in data[uid]:
                nickname = data[uid]['nickname']
            else:
                nickname = '匿名'

            current_stock_money = 0
            ratio = ((total_money - (10 ** 6 * 5)) / (10 ** 6 * 5)) * 100
            for stock in data[uid]:
                if not isinstance(data[uid][stock], dict):
                    continue

                if stock not in self.stock_price_cache:
                    logger.warning(f'Reading {stock}')
                    price_now, is_digital_coin, \
                    stock_name, stock_api, _ = await self._determine_stock_price_digital_name(
                        stock, valid_time=valid_time
                    )

                    if price_now <= 0:
                        return {
                            "total": total_money,
                            "ratio": ratio,
                            "nickname": nickname
                        }
                else:
                    price_now = await self._get_stock_price_from_cache_by_identifier(stock)
                    is_digital_coin = self.stock_price_cache[stock]['isDigital']
                    stock_name = self.stock_price_cache[stock]['stockName']
                    stock_api = Stock(stock) if not is_digital_coin else Crypto(stock)
                    if not is_digital_coin:
                        stock_api.set_type(self.stock_price_cache[stock]['stockType'])

                stock_type = stock_api.type if isinstance(stock_api, Stock) else 'Crypto'
                self.set_stock_cache(stock, stock_name, stock_type, price_now, is_digital_coin)
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
        if price_now <= 0:
            return stock_name

        new_price = price_now * total_count
        rate = (new_price - total_money_spent) / total_money_spent * 100

        logger.success(f'Checking {stock_code} succeed: {price_now:,.2f}')

        return f'{stock_name}[{stock_code}] x {total_count} -> 成本{_get_price_sn_or_literal(total_money_spent)}软妹币\n' \
               f'（最新市值：{_get_price_sn_or_literal(new_price)}软妹币 | ' \
               f'持仓盈亏：{rate:.2f}% {"↑" if rate >= 0 else "↓"} | 平摊成本：{_get_price_sn_or_literal(avg_money)}软妹币/张）\n'

    async def _get_stock_price_from_cache_by_identifier(self, identifier) -> Union[int, float]:
        price_now, is_digital, \
        stock_name, stock_api, _ = await self._determine_stock_price_digital_name(identifier, 60 * 60 * 1)

        return price_now

    @staticmethod
    async def _get_stock_change_anomaly_text(ratio_change):
        if ratio_change >= 1.08:
            anomaly = '涨幅达A股涨停板'
        elif ratio_change >= 1.06:
            anomaly = '火箭发射'
        elif ratio_change >= 1.03:
            anomaly = '快速上涨'
        elif ratio_change >= 0.99:
            anomaly = '未出现大的改变'
        elif ratio_change >= 0.97:
            anomaly = '快速回调'
        elif ratio_change >= 0.94:
            anomaly = '高台跳水'
        elif ratio_change >= 0.88:
            anomaly = '上涨'
        else:
            anomaly = '下跌'

        return anomaly

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
        if price_now <= 0:
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

        random_num = randint(0, 99)
        special_event = ''
        if random_num < 5 or amount >= 1e4:
            random_percentage = randint(1, 70)
            ratio_change = 1 + random_percentage / 1e4

            price_now *= ratio_change
            special_event = f'\n(在您购买的时候，该产品的价格出现了小幅波动：+{random_percentage / 1e2}%）'

        need_money = amount * price_now
        fee = need_money * 0.001
        need_money += fee

        user_money = self.user_stock_data['data'][uid]['totalMoney']
        if need_money > user_money:
            return f'您没钱了（剩余：{user_money:,.2f}，需要：{need_money:,.2f}）'

        self._backfill_nickname(uid, ctx)

        if isinstance(stock_api, Stock):
            stock_code = stock_api.code

        if stock_code not in self.user_stock_data['data'][uid]:
            self.user_stock_data['data'][uid][stock_code] = {
                "purchasePrice": 0,
                "purchaseCount": 0,
                "moneySpent": 0,
                "margin": 1
            }

        self.user_stock_data['data'][uid]['totalMoney'] = user_money - need_money - fee

        current_stock = self.user_stock_data['data'][uid][stock_code]
        current_stock["purchaseCount"] += amount
        current_stock["moneySpent"] += need_money
        current_stock["purchasePrice"] = current_stock["moneySpent"] / current_stock["purchaseCount"]

        current_stock['margin'] = margin
        current_stock['name'] = stock_name
        current_stock['type'] = stock_api.type if isinstance(stock_api, Stock) else 'Crypto'

        self._store_user_data()
        return f'您花费了{_get_price_sn_or_literal(need_money)}软妹币已每' \
               f'{"股" if not is_digital_coin else "个"}{_get_price_sn_or_literal(price_now)}' \
               f'软妹币的价格购买了{amount}{"股" if not is_digital_coin else "个"}{stock_name}{special_event}' \
               f'\n（印花税：{_get_price_sn_or_literal(fee)}软妹币，' \
               f'余额：{self.user_stock_data["data"][uid]["totalMoney"]:,.2f}软妹币）'

    async def _get_western_stock_data(
            self, last_updated_exact, time_diff, stock_code, day_now
    ):
        if datetime.today().weekday() >= 5:
            return last_updated_exact.weekday() >= 4, self.stock_price_cache[stock_code]

        if (day_now.hour >= 18 or day_now.hour < 6) and time_diff > 120:
            return False, self.stock_price_cache[stock_code]

        return True, self.stock_price_cache[stock_code]

    async def _get_chinese_stock_data(
            self, last_updated_exact, stock_code, day_now, day_now_timestamp, last_updated
    ) -> (bool, dict):
        if datetime.today().weekday() >= 5:
            return last_updated_exact.weekday() >= 4, self.stock_price_cache[stock_code]

        # 周1-5逻辑
        # AB股闭市时间
        if self.stock_price_cache[stock_code]['stockType'] in (0, 1) \
                and (day_now.hour < 9 or day_now.hour >= 15):
            # 9点前拿上一天15点后的数据
            if day_now.hour < 9:
                if day_now_timestamp - last_updated > \
                        (60 * 60 * 18 if day_now.weekday() != 0 else 60 * 60 * 24 * 2.5):
                    return False, self.stock_price_cache[stock_code]
                elif last_updated_exact.hour < 15:
                    return False, self.stock_price_cache[stock_code]
                else:
                    return True, self.stock_price_cache[stock_code]
            else:
                return last_updated_exact.hour >= 15 and last_updated_exact.day == day_now.day, \
                       self.stock_price_cache[stock_code]

        # 港股闭市时间
        if self.stock_price_cache[stock_code]['stockType'] == 116 \
                and (day_now.hour < 9 or day_now.hour >= 16):
            if day_now.hour < 9:
                if day_now_timestamp - last_updated > 60 * 60 * 17:
                    return False, self.stock_price_cache[stock_code]
                elif last_updated_exact.hour < 16:
                    return False, self.stock_price_cache[stock_code]
                else:
                    return True, self.stock_price_cache[stock_code]
            else:
                return last_updated_exact.hour >= 16 and last_updated_exact.day == day_now.day, \
                       self.stock_price_cache[stock_code]

        # 开盘竞价时可能无数据
        if datetime.now().hour == 9 and datetime.now().minute <= 25:
            return True, self.stock_price_cache[stock_code]

        return False, self.stock_price_cache[stock_code]

    async def _determine_if_has_cache_or_expired(self, stock_code, valid_time=None) -> (bool, dict):
        day_now_timestamp = time.time()
        if not re.match(r'^[A-Z0-9]+$', stock_code):
            logger.warning(f'Not seem to be a good stock code. {stock_code}')
            return False, {}
        if stock_code in self.stock_price_cache:
            last_updated = self.stock_price_cache[stock_code]['lastUpdated']
            time_diff = day_now_timestamp - last_updated
            if time_diff > 60 * 60 * 24 * 2.5:
                return False, self.stock_price_cache[stock_code]
            if time_diff < (self.CACHE_EXPIRATION if valid_time is None else valid_time):
                return True, self.stock_price_cache[stock_code]
            else:
                # 虚拟盘24小时开所以寄~
                last_updated_exact = datetime.fromtimestamp(last_updated)
                day_now = datetime.now()

                if not self.stock_price_cache[stock_code]['isDigital']:
                    # 如果本天是周末，且上次价格更新是周五，则直接返回数据，反之需要稍微更新一下
                    if stock_code.isdigit():
                        return await self._get_chinese_stock_data(
                            last_updated_exact, stock_code, day_now, day_now_timestamp, last_updated
                        )
                    else:
                        return await self._get_western_stock_data(
                            last_updated_exact, time_diff, stock_code, day_now
                        )

                return False, self.stock_price_cache[stock_code]

        return False, {}

    async def _determine_stock_price_digital_name(self, stock_code, valid_time=None) \
            -> (Union[float, int], bool, str, Union[Crypto, Stock, None, str]):
        is_digital_coin = False
        is_valid_store, get_stored_info = await self._determine_if_has_cache_or_expired(stock_code, valid_time)
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
                    price_now, stock_name = await stock_api.get_purchase_price(stock_type=get_stored_info['stockType'])
                else:
                    price_now, stock_name = await stock_api.get_purchase_price()
                    # 用文字搜的
                    if price_now <= 0:
                        stock_code = await stock_api.get_stock_codes(get_one=True)
                        if not stock_code.isdigit():
                            return -1, False, '为了最小化bot的响应时间，请使用股票的数字代码购买~', None, stock_code

                        stock_api.code = stock_code
                        price_now, _, \
                        stock_name, stock_api, stock_code = await self._determine_stock_price_digital_name(stock_code)

                is_digital_coin = False

        else:
            stock_api = Stock(stock_code)
            if get_stored_info:
                price_now, stock_name = await stock_api.get_purchase_price(get_stored_info['stockType'])
            else:
                price_now, stock_name = await stock_api.get_purchase_price()
            # debug的时候发现的，wtf？
            if price_now == '-' or price_now <= 0:
                return -1, False, self.STOCK_NOT_EXISTS, None, stock_code

        stock_type = stock_api.type if not is_digital_coin else stock_api.crypto_name
        stock_code = stock_api.code if not is_digital_coin else stock_api.crypto_name
        self.set_stock_cache(stock_code, stock_name, stock_type, price_now, is_digital_coin)

        self._store_stock_data()
        logger.success(f'Checking {stock_code} succeed.')
        return price_now, is_digital_coin, stock_name, stock_api, stock_code
