import sqlite3
import time
from typing import Union

from Services.util.common_util import time_to_literal


class UserLimitModifier:
    def __init__(self, rate_limit_time: float, rate_limit_modifier: float, overwrite_global=False):
        """
        :param rate_limit_time: 时间内限流参数（单位：秒）
        :param rate_limit_modifier: 普通配置的限流是群限流参数，这里是提供一个倍数
        :param overwrite_global: 如果为True，则覆盖群限流参数。默认为False

        使用范例：如果我创建了一个UserLimitModifier(30.0, 2.0)，然后该功能的群限制为10，则代表单个用户在30秒，只能请求10 * 2.0次。
        如果我创建了一个UserLimitModifier(30.0, 5.0, True)，群限制为10，则单用户30秒内只能请求5次。
        """
        self.rate_limit_time = rate_limit_time
        self.rate_limit_modifier = rate_limit_modifier
        self.overwrite_global = overwrite_global


class RateLimiter:
    def __init__(self):
        self.rate_limiter_database_path = 'data/db/ratelimiter.db'
        self.rate_limiter_db = sqlite3.connect(self.rate_limiter_database_path)
        self.LIMIT_BY_GROUP = 'GROUP'
        self.LIMIT_BY_USER = 'USER'
        self.TEMPRORARY_DISABLED = 'DISABLED'

        self._init_ratelimiter()

    def _init_ratelimiter(self):
        self.rate_limiter_db.execute(
            """
            create table if not exists rate_limiter_config (
                function_name varchar(255) unique on conflict ignore primary key,
                rate_limit integer
            )
            """
        )
        self.rate_limiter_db.execute(
            """
            create table if not exists rate_limiter (
                user_id varchar(30),
                function_name varchar(255),
                hit integer,
                last_updated integer,
                unique (user_id, function_name) on conflict ignore
            )
            """
        )
        self.rate_limiter_db.commit()

    async def set_function_limit(self, function_name: str, rate_limit: int):
        self.rate_limiter_db.execute(
            """
            insert or replace into rate_limiter_config (function_name, rate_limit) values (
                ?, ?
            )
            """, (function_name, rate_limit)
        )

        self.rate_limiter_db.commit()

    async def get_function_limit(self, function_name: str):
        result = self.rate_limiter_db.execute(
            """
            select rate_limit from rate_limiter_config where function_name = ? limit 1;
            """, (function_name,)
        ).fetchone()

        if isinstance(result, int):
            return result

        if result is not None and result[0] is not None:
            return result[0]

        await self.set_function_limit(function_name, 10)
        return 10

    async def get_user_last_update(self, function_name: str, user_id: Union[str, int]):
        user_id = str(user_id)
        result = self.rate_limiter_db.execute(
            """
            select last_updated from rate_limiter where user_id = ? and function_name = ? limit 1;
            """, (user_id, function_name)
        ).fetchone()

        return result if isinstance(result, int) else result[0] \
            if result is not None and result[0] is not None else int(time.time())

    async def get_user_hit(self, function_name: str, user_id: Union[str, int]):
        user_id = str(user_id)
        result = self.rate_limiter_db.execute(
            """
            select hit from rate_limiter where function_name = ? and user_id = ? limit 1;
            """, (function_name, user_id)
        ).fetchone()

        return result if isinstance(result, int) else result[0] if result is not None and result[0] is not None else 0

    async def _query_group_permission(self, function_name: str, group_id: str, time_manner=60) -> (str, int):
        group_last_update_time = await self.get_user_last_update(function_name, group_id)

        function_usage_limit = await self.get_function_limit(function_name)
        if function_usage_limit <= 0:
            return self.TEMPRORARY_DISABLED, group_last_update_time + time_manner - int(time.time())
        group_hit = await self.get_user_hit(function_name, group_id)

        if int(time.time()) - group_last_update_time > time_manner:
            update_group_hit = 1
            group_last_update_time_updated = int(time.time())
        else:
            if group_hit + 1 > function_usage_limit:
                return self.LIMIT_BY_GROUP, group_last_update_time + time_manner - int(time.time())
            update_group_hit = group_hit + 1
            group_last_update_time_updated = group_last_update_time

        self.rate_limiter_db.execute(
            """
            insert or replace into rate_limiter (user_id, function_name, hit, last_updated) values (
                ?, ?, ?, ?
            )
            """, (group_id, function_name, update_group_hit, group_last_update_time_updated)
        )
        self.rate_limiter_db.commit()
        return '', -1

    async def _query_user_permission(self, function_name: str, user_id: str, user_modifier: UserLimitModifier):
        user_last_update_time = await self.get_user_last_update(function_name, user_id)
        function_usage_limit = await self.get_function_limit(function_name)

        user_hit = await self.get_user_hit(function_name, user_id)

        if function_usage_limit <= 0:
            return self.TEMPRORARY_DISABLED, user_last_update_time + user_modifier.rate_limit_time - int(time.time())

        if int(time.time()) - user_last_update_time > user_modifier.rate_limit_time:
            update_user_hit = 1
            user_last_update_time_updated = int(time.time())
        else:
            user_usage_limit = function_usage_limit * user_modifier.rate_limit_modifier if not \
                user_modifier.overwrite_global else user_modifier.rate_limit_modifier

            if user_hit + 1 > user_usage_limit:
                return self.LIMIT_BY_USER, \
                       user_last_update_time + user_modifier.rate_limit_time - int(time.time())

            update_user_hit = user_hit + 1
            user_last_update_time_updated = user_last_update_time

        self.rate_limiter_db.execute(
            """
            insert or replace into rate_limiter (user_id, function_name, hit, last_updated) values (
                ?, ?, ?, ?
            )
            """, (user_id, function_name, update_user_hit, user_last_update_time_updated)
        )

        self.rate_limiter_db.commit()
        return '', -1

    async def _query_permission(
            self,
            function_name: str,
            user_id: str,
            group_id: str,
            user_limit_modifier: UserLimitModifier
    ) -> (str, int):
        query_group_prompt, wait_time = await self._query_group_permission(function_name, group_id)
        if query_group_prompt:
            return query_group_prompt, wait_time

        query_user_prompt, wait_time = await self._query_user_permission(function_name, user_id, user_limit_modifier)
        return query_user_prompt, wait_time

    async def _assemble_limit_prompt(self, prompt, wait_time):
        if prompt == self.LIMIT_BY_USER:
            return f'别玩啦，过{await time_to_literal(wait_time)}后再回来玩好不好？'
        elif prompt == self.LIMIT_BY_GROUP:
            return f'群使用已到达允许上限，请稍等{await time_to_literal(wait_time)}后重试'
        elif prompt == self.TEMPRORARY_DISABLED:
            return f'该功能全局禁用中，请稍等{await time_to_literal(wait_time)}后再试。'

        return None

    async def user_group_limit_check(
            self,
            function_name: str,
            user_id: Union[str, int],
            group_id: Union[str, int],
            user_limit_modifier: UserLimitModifier
    ) -> Union[str, None]:
        user_id = str(user_id)
        group_id = str(group_id)

        query_result, wait_time = await self._query_permission(function_name, user_id, group_id, user_limit_modifier)
        return await self._assemble_limit_prompt(query_result, wait_time)

    async def user_limit_check(
            self,
            function_name: str,
            user_id: Union[str, int],
            user_limit_modifier: UserLimitModifier
    ):
        user_id = str(user_id)
        query_result, wait_time = await self._query_user_permission(function_name, user_id, user_limit_modifier)
        return await self._assemble_limit_prompt(query_result, wait_time)

    async def group_limit_check(self, function_name: str, group_id: Union[str, int]):
        group_id = str(group_id)
        query_result, wait_time = await self._query_group_permission(function_name, group_id)
        return await self._assemble_limit_prompt(query_result, wait_time)
