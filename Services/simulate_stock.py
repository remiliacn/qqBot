import asyncio
import itertools
import re
import sqlite3
import time
from datetime import datetime
from os import getcwd
from os.path import exists
from random import randint
from typing import Union, Dict, List

from loguru import logger

from Services.stock import Stock, Crypto


class StockInfo:
    def __init__(self, stock_name: str, price_now: float, last_updated: int, is_digital: bool, stock_type: str):
        self.stock_name = stock_name
        self.price_now = price_now
        self.last_updated = last_updated
        self.is_digital = is_digital
        self.stock_type = stock_type


class StockTransaction:
    def __init__(
            self, stock_code, quote_name: str,
            user_id, purchase_price, purchase_count,
            money_spent, margin, stock_type
    ):
        self.stock_code = stock_code
        self.quote_name = quote_name
        self.user_id = user_id
        self.purchase_price = purchase_price
        self.purchase_count = purchase_count
        self.money_spent = money_spent
        self.margin = margin
        self.stock_type = stock_type


class StockPurchaseInfo:
    def __init__(self, purchase_count: float, money_spent: float, purchase_price: float):
        self.purchase_count = purchase_count
        self.money_spent = money_spent
        self.purchase_price = purchase_price


class UserInfo:
    def __init__(self, user_id: str, total_money: float, nickname: str, last_reset: int):
        self.user_id = user_id
        self.total_money = total_money
        self.nickname = nickname
        self.last_reset = last_reset


def _get_price_sn_or_literal(n: float) -> str:
    if n < 0.01:
        return f'{n:.2e}'

    return f'{n:,.2f}'


class SimulateStock:
    def __init__(self):
        self.STOCK_NOT_EXISTS = '未开盘、产品不存在、或已退市。（如果不确定股票代码，请使用！股票 名称来找一下~）'
        self.NO_INFO = '您啥还没买呢哦~'
        self.CACHE_EXPIRATION = 80
        self.USD_TO_CNY = 6.35

        self.user_record_filename = f'{getcwd()}/data/db/stock_data.db'

        self._init_user_stock_data()
        self.stock_data_db = sqlite3.connect(self.user_record_filename)
        self.stock_price_cache: Dict[str, StockInfo] = {}
        self._init_price_cache()

    def _init_price_cache(self):
        self.stock_price_cache = {}
        result = self.stock_data_db.execute(
            """
            select stock_quote, stock_name, price_now, last_updated, is_digital_coin, stock_type from stock_info
            """
        ).fetchall()

        for r in result:
            self.stock_price_cache[r[0]] = StockInfo(r[1], r[2], r[3], r[4], r[5])

    def _init_user_stock_data(self):
        if not exists(self.user_record_filename):
            temp_connection = sqlite3.connect(self.user_record_filename)
            temp_connection.execute(
                """
                create table if not exists user_stock (
                    "user_id" varchar(20) not null unique on conflict ignore,
                    "total_money" real not null,
                    "nickname" varchar(150) not null,
                    "last_reset" integer
                )
                """
            )
            temp_connection.execute(
                """
                create table if not exists user_transaction (
                    "stock_code" varchar(100) not null unique on conflict ignore,
                    "quote_name" varchar(100) not null unique on conflict ignore,
                    "user_id" varchar(50) not null,
                    "purchase_price" real not null,
                    "purchase_count" real not null,
                    "money_spent" real not null,
                    "margin" real not null,
                    "stock_type" varchar(50) not null
                )
                """
            )
            temp_connection.execute(
                """
                create table if not exists stock_info (
                    "stock_quote" var(50) not null unique on conflict ignore,
                    "stock_name" var(50) not null,
                    "price_now" real not null,
                    "last_updated" integer not null,
                    "is_digital_coin" boolean not null,
                    "stock_type" varchar(50) not null
                )
                """
            )
            temp_connection.commit()

    def _commit_change(self):
        self.stock_data_db.commit()

    def _get_user_info(self, uid: str) -> UserInfo:
        result = self.stock_data_db.execute(
            """
            select user_id, total_money, nickname, last_reset from user_stock
            where user_id = ?
            """, (uid,)
        ).fetchone()

        if result is None:
            return None

        return UserInfo(result[0], result[1], result[2], result[3])

    def reset_user(self, uid: Union[str, int], nickname: str):
        uid = str(uid)
        last_reset_time = self.stock_data_db.execute(
            """
            select last_reset from user_stock where user_id = ?
            """, (uid,)
        ).fetchone()

        current_time = int(time.time())
        if last_reset_time is not None and last_reset_time[0] is not None:
            if current_time - last_reset_time[0] < 60 * 60 * 24 * 7:
                return '必须一周后才能重置持仓'

        elif last_reset_time is None:
            self.stock_data_db.execute(
                """
                insert or replace into user_stock (user_id, total_money, nickname, last_reset) values (
                    ?, 5000000, ?, ?
                )
                """, (uid, nickname, current_time)
            )

            self._commit_change()
            return 'Done!'

        self.stock_data_db.execute(
            """
            delete from user_transaction where user_id = ?
            """, (uid,)
        )
        self.stock_data_db.execute(
            """
            delete from user_stock where user_id = ?
            """, (uid,)
        )
        self.stock_data_db.execute(
            """
            update user_stock set last_reset = ?, total_money = 5000000 where user_id = ?
            """, (current_time, uid)
        )
        self._commit_change()
        return 'Done!'

    async def _query_all_user_stonk_stock_code(self, uid: str) -> list:
        result = self.stock_data_db.execute(
            """
            select stock_code from user_transaction where user_id = ?
            """, (uid,)
        ).fetchall()

        return [r[0] for r in result] if result is not None else []

    async def _query_user_stock_by_quote(self, uid: str, stock_code: str) -> StockPurchaseInfo:
        result = self.stock_data_db.execute(
            """
            select purchase_count, money_spent, purchase_price from user_transaction 
            where user_id = ? and stock_code = ?
            """, (uid, stock_code)
        ).fetchone()

        if result is None:
            return None

        return StockPurchaseInfo(result[0], result[1], result[2])

    async def my_money_spent_by_stock_code(self, uid: Union[int, str], stock_code: str) -> (str, float, float):
        uid = str(uid)
        stock_code = stock_code.upper() if len(stock_code) <= 4 else stock_code
        stock_to_check = await self._query_user_stock_by_quote(uid, stock_code)
        if not stock_to_check:
            return ''

        total_count = stock_to_check.purchase_count
        if total_count == 0:
            return ''

        total_money_spent = stock_to_check.money_spent
        avg_money = stock_to_check.purchase_price

        price_now, is_digital_coin, \
        stock_name, stock_api, _, _ = await self._determine_stock_price_digital_name(stock_code)
        if price_now <= 0:
            return stock_name

        new_price = price_now * total_count
        if total_money_spent < 1e-6:
            total_money_spent = 1e-6
        rate = (new_price - total_money_spent) / total_money_spent * 100

        logger.success(f'Checking {stock_code} succeed: {price_now:,.2f}')

        return f'{stock_name}[{stock_code}] x {total_count} -> 成本{_get_price_sn_or_literal(total_money_spent)}软妹币\n' \
               f'（最新市值：{_get_price_sn_or_literal(new_price)}软妹币 | ' \
               f'持仓盈亏：{rate:.2f}% {"↑" if rate >= 0 else "↓"} | 平摊成本：{_get_price_sn_or_literal(avg_money)}软妹币/张）\n'

    async def get_all_stonk_log_by_user(self, uid: Union[int, str]):
        uid = str(uid)

        stonk_whole_log = await self._query_all_user_stonk_stock_code(uid)

        if not stonk_whole_log:
            return self.NO_INFO

        response = [await self.my_money_spent_by_stock_code(uid, stock_code) for stock_code in stonk_whole_log]
        time_now = datetime.now()

        if time_now.hour >= 15 or (time_now.hour == 9 and time_now.minute < 15 or time_now.hour < 9) \
                or time_now.weekday() >= 5 or await self._get_if_is_chinese_holiday(time_now):
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

        if time_now.weekday() >= 5 or (time_now.hour == 9 and time_now.minute < 30) \
                or time_now.hour < 9 or await self._get_if_is_chinese_holiday(time_now):
            time_awareness += '【港股·休市】\n'
        elif time_now.hour >= 16:
            time_awareness += "【港股·休市】\n"
        else:
            time_awareness += "【港股·交易中】\n"

        time_awareness += '【虚拟货币·交易中】\n'

        response = [x for x in response if x]
        user_data = await self.get_user_overall_stat(uid, 60 * 2)
        money_diff = user_data["total"] - 5 * 10 ** 6
        return f'{time_awareness}\n\n' \
               f'总资产{user_data["total"]:,.2f}软妹币\n' \
               f'总收益率：{user_data["ratio"]:,.2f}% {"↑" if user_data["ratio"] >= 0 else "↓"}\n' \
               f'账户盈亏：{"+ " if money_diff >= 0 else ""} {money_diff:,.2f}软妹币 {"↑" if money_diff >= 0 else "↓"}\n\n' \
               + '\n'.join(response)

    @staticmethod
    def _partition(lst, size):
        for i in range(0, len(lst), size):
            yield list(itertools.islice(lst, i, i + size))

    async def get_all_user_info(self, valid_time=None):
        user_data = self.stock_data_db.execute(
            """
            select user_id from user_stock
            """
        ).fetchall()

        user_data_info: List[dict] = []
        response = ''
        tasks = []
        for uid in user_data:
            uid = uid[0]
            tasks.append(self.get_user_overall_stat(uid, valid_time))

        partition_list = list(self._partition(tasks, 5))
        for partition in partition_list:
            result = await asyncio.gather(*partition)
            for data in result:
                if data:
                    user_data_info.append(data)

            await asyncio.sleep(2)

        if len(user_data_info) > 5:
            sorted_list_reverse = sorted(user_data_info, key=lambda d: d["ratio"], reverse=True)
            sorted_list = sorted_list_reverse[::-1][:5]
            sorted_list_reverse = sorted_list_reverse[:5]
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

        logger.success('Leaderboard fetch completed successfully.')
        return response.strip()

    def set_stock_cache(self, stock_code, stock_name, stock_type, price_now, is_digital):
        if price_now <= 0:
            return

        if not re.match(r'^[A-Z0-9]+$', stock_code):
            logger.warning(f'{stock_code} not valid?')
            return

        self.stock_data_db.execute(
            """
            insert or replace into stock_info 
                (stock_quote, stock_name, price_now, last_updated, is_digital_coin, stock_type) values (
                ?, ?, ?, ?, ?, ?
            )
            """, (stock_code, stock_name, price_now, int(time.time()), is_digital, str(stock_type))
        )

        self._commit_change()

    def get_type_by_stock_code(self, stock_code):
        result = self.stock_data_db.execute(
            """
            select stock_type from stock_info where stock_quote = ?
            """, (stock_code,)
        ).fetchone()

        return result[0] if result is not None and result[0] is not None else None

    async def _delete_user_stock_by_quote(self, uid: str, stock_code: str):
        self.stock_data_db.execute(
            """
            delete from user_transaction where user_id = ? and stock_code = ?
            """, (uid, stock_code)
        )
        self._commit_change()

    async def _update_user_transaction(self, data: StockPurchaseInfo, stock_code: str, user_data: UserInfo):
        self.stock_data_db.execute(
            """
            update user_transaction set 
                purchase_count = ?,
                purchase_price = ?,
                money_spent = ?
                where stock_code = ?
            """, (data.purchase_count, data.purchase_price, data.money_spent, stock_code)
        )
        self.stock_data_db.execute(
            """
            update user_stock set total_money = ?, nickname = ? where user_id = ?
            """, (user_data.total_money, user_data.nickname, user_data.user_id)
        )
        self._commit_change()

    async def sell_stock(self, uid: Union[int, str], stock_code: str, amount: str):
        stock_code = stock_code.upper() if len(stock_code) <= 4 else stock_code
        if not amount.isdigit():
            try:
                amount = float(amount)
            except ValueError:
                return f'卖不了{amount}'

        uid = str(uid)
        amount = round(float(amount), 2)

        try:
            price_now, is_digital_coin, \
            stock_name, stock_api, _, stock_rate = await self._determine_stock_price_digital_name(stock_code)
        except TypeError:
            return self.STOCK_NOT_EXISTS

        if price_now - stock_rate[1] <= 0.02:
            return '目前跌停无法卖出'

        if price_now <= 0:
            return stock_name

        if not is_digital_coin:
            if amount < 100 or amount % 100 != 0:
                return '出售数量必须为大于100且为100倍数的正整数'
        else:
            if amount <= 0:
                return '?'

        if isinstance(stock_api, Stock):
            stock_code = stock_api.code

        query_data = await self._query_user_stock_by_quote(uid, stock_code)
        if query_data.purchase_count < amount:
            return '您没那么多谢谢'

        price_now, is_digital_coin, \
        stock_name, stock_api, _, stock_rate = await self._determine_stock_price_digital_name(stock_code)

        if price_now - stock_rate[1] <= 0.015:
            return '目前跌停无法卖出'

        if price_now <= 0:
            return stock_name

        special_event = ''
        random_num = randint(0, 99)
        if random_num < 10 or amount >= 1e4:
            random_percentage = randint(1, 70)
            ratio_change = 1 - random_percentage / 1e4

            price_now *= ratio_change
            special_event = f'\n(在您卖出的时候，该产品的价格出现了小幅波动： -{random_percentage / 1e2}%）'

        query_data.purchase_count -= amount
        price_earned = price_now * amount

        user_data = self._get_user_info(uid)

        user_data.total_money += price_earned * 0.999

        fee = price_earned * .001
        if query_data.purchase_count == 0:
            await self._delete_user_stock_by_quote(uid, stock_code)
        else:
            query_data.money_spent -= price_earned
            query_data.purchase_price = query_data.money_spent / query_data.purchase_count

        await self._update_user_transaction(query_data, stock_code, user_data)
        return f'您已每{"股" if not is_digital_coin else "个"}{_get_price_sn_or_literal(price_now)}' \
               f'软妹币的价格卖出了{amount}{"股" if not is_digital_coin else "个"}' \
               f'{stock_name}{special_event}\n（印花税：{_get_price_sn_or_literal(fee)}软妹币），' \
               f'现在您有{user_data.total_money:,.2f}软妹币了~'

    async def _get_user_stock_data(self, uid: str) -> dict:
        result = self.stock_data_db.execute(
            """
            select total_money, nickname from user_stock
            where user_id = ?
            """, (uid,)
        ).fetchone()

        if result is None:
            return {}

        return {
            'total_money': result[0],
            'nickname': result[1]
        }

    async def get_user_overall_stat(self, uid: Union[int, str], valid_time) -> dict:
        uid = str(uid)
        data = await self._get_user_stock_data(uid)
        if not data:
            return {}

        total_money = data['total_money']
        nickname = data['nickname']

        current_stock_money = 0
        ratio = ((total_money - (10 ** 6 * 5)) / (10 ** 6 * 5)) * 100

        stocks = await self._query_all_user_stonk_stock_code(uid)
        self._init_price_cache()
        for stock in stocks:
            if stock not in self.stock_price_cache:
                logger.warning(f'Reading {stock}')
                price_now, is_digital_coin, \
                stock_name, stock_api, _, _ = await self._determine_stock_price_digital_name(
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
                is_digital_coin = self.stock_price_cache[stock].is_digital
                stock_name = self.stock_price_cache[stock].stock_name
                stock_api = Stock(stock) if not is_digital_coin else Crypto(stock)
                if not is_digital_coin:
                    stock_api.set_type(self.stock_price_cache[stock].stock_type)

            user_stock_data = await self._query_user_stock_by_quote(uid, stock)

            stock_type = stock_api.type if isinstance(stock_api, Stock) else 'Crypto'
            self.set_stock_cache(stock, stock_name, stock_type, price_now, is_digital_coin)
            current_stock_money += price_now * user_stock_data.purchase_count

        total_money += current_stock_money
        if round(total_money, 2) == 5000000.00:
            return {}

        ratio = ((total_money - (10 ** 6 * 5)) / (10 ** 6 * 5)) * 100
        return {
            "total": total_money,
            "ratio": ratio,
            "nickname": nickname
        }

    async def _get_stock_price_from_cache_by_identifier(self, identifier) -> Union[int, float]:
        price_now, is_digital, \
        stock_name, stock_api, _, _ = await self._determine_stock_price_digital_name(identifier, 60 * 60 * 1)

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

    async def _get_user_money(self, uid: str):
        result = self.stock_data_db.execute(
            """
            select total_money from user_stock where user_id = ?
            """, (uid,)
        ).fetchone()

        return result[0] if result is not None and result[0] is not None else -1

    async def _insert_user_transaction(self, data: StockTransaction, user_money: float, nickname: str):
        self.stock_data_db.execute(
            """
            insert or replace into user_transaction (
                stock_code, quote_name, user_id, purchase_price, purchase_count, money_spent, margin, stock_type
            ) values (
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """, (
                data.stock_code,
                data.quote_name, data.user_id,
                data.purchase_price, data.purchase_count,
                data.money_spent, data.margin, data.stock_type
            )
        )
        self.stock_data_db.execute(
            """
            insert or replace into user_stock (user_id, total_money, nickname, last_reset) values (
                ?, ?, ?, coalesce(
                    (select last_reset from user_stock where user_id = ?), ?
                )
            )
            """, (data.user_id, user_money, nickname, data.user_id, int(time.time()))
        )
        self._commit_change()

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
        try:
            price_now, is_digital_coin, \
            stock_name, stock_api, _, stock_rate = await self._determine_stock_price_digital_name(stock_code)
        except TypeError:
            return self.STOCK_NOT_EXISTS

        nickname = ctx['sender']['nickname']

        if stock_rate[0] - price_now <= 0.01:
            return '产品涨停无法买入'

        if price_now <= 0:
            return self.STOCK_NOT_EXISTS

        if not is_digital_coin:
            if amount < 100 or amount % 100 != 0:
                return '购买数量必须为大于100且为100倍数的正整数'
        else:
            if amount <= 0:
                return '?'

        uid = str(uid)
        user_money = await self._get_user_money(uid)
        if user_money == -1:
            user_money = 5000000

        random_num = randint(0, 99)
        special_event = ''
        if random_num < 5 or amount >= 1e4:
            random_percentage = randint(1, 15)
            ratio_change = 1 + random_percentage / 1e4

            price_now *= ratio_change
            special_event = f'\n(在您购买的时候，该产品的价格出现了小幅波动：+{random_percentage / 1e2}%）'

        need_money = amount * price_now
        fee = need_money * 0.001
        need_money += fee

        if need_money + fee > user_money:
            return f'您没钱了（剩余：{user_money:,.2f}，需要：{need_money:,.2f}）'

        if isinstance(stock_api, Stock):
            stock_code = stock_api.code

        user_money -= (need_money + fee)
        current_stock = await self._query_user_stock_by_quote(uid, stock_code)
        if current_stock is None:
            purchase_count = 0
            money_spent = 0
        else:
            purchase_count = current_stock.purchase_count
            money_spent = current_stock.money_spent

        purchase_count += amount
        money_spent += need_money
        purchase_price = money_spent / purchase_count

        stock_type = stock_api.type if isinstance(stock_api, Stock) else 'Crypto'
        transaction = StockTransaction(
            stock_code, stock_name, uid, purchase_price,
            purchase_count, money_spent, margin, stock_type
        )
        await self._insert_user_transaction(transaction, user_money, nickname)

        return f'您花费了{_get_price_sn_or_literal(need_money)}软妹币已每' \
               f'{"股" if not is_digital_coin else "个"}{_get_price_sn_or_literal(price_now)}' \
               f'软妹币的价格购买了{amount}{"股" if not is_digital_coin else "个"}{stock_name}{special_event}' \
               f'\n（印花税：{_get_price_sn_or_literal(fee)}软妹币，' \
               f'余额：{user_money:,.2f}软妹币）'

    async def _get_western_stock_data(
            self, last_updated_exact, time_diff, stock_code, day_now
    ):
        if datetime.today().weekday() >= 5:
            return last_updated_exact.weekday() >= 4, self.stock_price_cache[stock_code]

        if (day_now.hour >= 18 or day_now.hour < 6) and time_diff > 120:
            return False, self.stock_price_cache[stock_code]

        return True, self.stock_price_cache[stock_code]

    @staticmethod
    async def _get_if_is_chinese_holiday(day_now):
        if day_now.month == 1 and day_now.day <= 3:
            return True

        if (day_now.month == 1 and day_now.day >= 29) or (day_now.month == 2 and day_now.day <= 6):
            return True

        if day_now.month == 4 and 3 <= day_now.day <= 5:
            return True

        if day_now.month == 5 and day_now.day <= 4:
            return True

        if day_now.month == 6 and 3 <= day_now.day <= 5:
            return True

        if day_now.month == 9 and 10 <= day_now.day <= 12:
            return True

        if day_now.month == 10 and day_now.day <= 7:
            return True

        return False

    async def _get_chinese_stock_data(
            self, last_updated_exact, stock_code, day_now, day_now_timestamp, last_updated
    ) -> (bool, dict):
        if day_now.weekday() >= 5:
            return last_updated_exact.weekday() >= 4, self.stock_price_cache[stock_code]

        if await self._get_if_is_chinese_holiday(day_now):
            return True, self.stock_price_cache[stock_code]

        # 周1-5逻辑
        # AB股闭市时间
        if self.stock_price_cache[stock_code].stock_type in ('0', '1') \
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
        if self.stock_price_cache[stock_code].stock_type == '116' \
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

    async def _determine_if_has_cache_or_expired(self, stock_code, valid_time=None) -> (bool, StockInfo):
        day_now_timestamp = time.time()
        if not re.match(r'^[A-Z0-9]+$', stock_code):
            logger.warning(f'Not seem to be a good stock code. {stock_code}')
            return False, None
        self._init_price_cache()
        if stock_code in self.stock_price_cache:
            last_updated = self.stock_price_cache[stock_code].last_updated
            time_diff = day_now_timestamp - last_updated
            if time_diff > 60 * 60 * 24 * 2.5:
                logger.info(f'Cache too old, needs to refresh for {stock_code}')
                return False, self.stock_price_cache[stock_code]
            if time_diff < (self.CACHE_EXPIRATION if valid_time is None else valid_time):
                logger.success(f'Cache valid, returning response for {stock_code}')
                return True, self.stock_price_cache[stock_code]
            else:
                # 虚拟盘24小时开所以寄~
                last_updated_exact = datetime.fromtimestamp(last_updated)
                day_now = datetime.now()

                if not self.stock_price_cache[stock_code].is_digital:
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

        return False, None

    async def _determine_stock_price_digital_name(self, stock_code, valid_time=None) \
            -> (Union[float, int], bool, str, Union[Crypto, Stock, None, str], bool):
        is_digital_coin = False
        is_valid_store, get_stored_info = await self._determine_if_has_cache_or_expired(stock_code, valid_time)

        get_stored_info: StockInfo
        stock_api = None

        stock_rate = (10e6, -1000)

        if get_stored_info is not None and is_valid_store:
            is_digital_coin = get_stored_info.is_digital
            return get_stored_info.price_now, is_digital_coin, \
                   get_stored_info.stock_name, \
                   Stock(stock_code) if not is_digital_coin else Crypto(stock_code), stock_code, stock_rate

        if not stock_code.isdigit():
            # 虚拟币一般是全字母，然后有可能有“-USDT”的部分
            if re.match(r'^[A-Z-]+$', stock_code.upper().strip()):
                stock_api = Crypto(stock_code)
                price_now = await stock_api.get_current_value() * self.USD_TO_CNY
                stock_name = stock_api.crypto_usdt
                is_digital_coin = True
            else:
                price_now = -1
                stock_name = ''

            # Price < 1 代表不是虚拟币，可能是美股？
            if price_now <= 0:
                stock_api = Stock(stock_code, keyword=stock_code)
                # 如果有stock_type，直接用，就不用猜了ε=(´ο｀*))
                if get_stored_info is not None:
                    stock_api.set_type(get_stored_info.stock_type)
                    price_now, stock_name, stock_rate = await stock_api.get_purchase_price(
                        stock_type=get_stored_info.stock_type
                    )
                else:
                    price_now, stock_name, stock_rate = await stock_api.get_purchase_price()
                    # 用文字搜的
                    if price_now <= 0:
                        stock_code = await stock_api.get_stock_codes(get_one=True)
                        if not stock_code.isdigit():
                            return -1, False, '为了最小化bot的响应时间，请使用股票的数字代码购买~', None, stock_code, stock_rate

                        stock_api.code = stock_code
                        price_now, _, \
                        stock_name, stock_api, stock_code, _ = await self._determine_stock_price_digital_name(
                            stock_code
                        )

                is_digital_coin = False

        else:
            stock_api = Stock(stock_code)
            if get_stored_info:
                price_now, stock_name, stock_rate = await stock_api.get_purchase_price(get_stored_info.stock_type)
            else:
                price_now, stock_name, stock_rate = await stock_api.get_purchase_price()
            # debug的时候发现的，wtf？
            if price_now == '-' or price_now <= 0:
                return -1, False, self.STOCK_NOT_EXISTS, None, stock_code, False

        stock_type = stock_api.type if not is_digital_coin else stock_api.crypto_name
        stock_code = stock_api.code if not is_digital_coin else stock_api.crypto_name
        self.set_stock_cache(stock_code, stock_name, stock_type, price_now, is_digital_coin)

        logger.success(f'Checking {stock_code} succeed.')
        return price_now, is_digital_coin, stock_name, stock_api, stock_code, stock_rate


if __name__ == '__main__':
    o = SimulateStock()
