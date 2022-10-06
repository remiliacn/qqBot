import sqlite3
import time
from typing import Union


class UserLimitModifier:
    def __init__(self, rate_limit_time, rate_limit_modifier):
        self.rate_limit_time = rate_limit_time
        self.rate_limit_modifier = rate_limit_modifier


class RateLimiter:
    def __init__(self):
        self.rate_limiter_database_path = 'data/db/ratelimiter.db'
        self.rate_limiter_db = sqlite3.connect(self.rate_limiter_database_path)
        self.LIMIT_BY_GROUP = 'GROUP'
        self.LIMIT_BY_USER = 'USER'

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

    def set_function_limit(self, function_name: str, rate_limit: int):
        self.rate_limiter_db.execute(
            """
            insert or replace into rate_limiter_config (function_name, rate_limit) values (
                ?, ?
            )
            """, (function_name, rate_limit)
        )

        self.rate_limiter_db.commit()

    def get_function_limit(self, function_name: str):
        result = self.rate_limiter_db.execute(
            """
            select rate_limit from rate_limiter_config where function_name = ? limit 1;
            """, (function_name,)
        ).fetchone()

        return result if isinstance(result, int) else result[0] if result is not None and result[0] is not None else 0

    def get_user_last_update(self, function_name: str, user_id: Union[str, int]):
        user_id = str(user_id)
        result = self.rate_limiter_db.execute(
            """
            select last_updated from rate_limiter where user_id = ? and function_name = ? limit 1;
            """, (user_id, function_name)
        ).fetchone()

        return result if isinstance(result, int) else result[0] \
            if result is not None and result[0] is not None else int(time.time())

    def get_user_hit(self, function_name: str, user_id: Union[str, int]):
        user_id = str(user_id)
        result = self.rate_limiter_db.execute(
            """
            select hit from rate_limiter where function_name = ? and user_id = ? limit 1;
            """, (function_name, user_id)
        ).fetchone()

        return result if isinstance(result, int) else result[0] if result is not None and result[0] is not None else 0

    def user_allowed_function(
            self,
            function_name: str,
            user_id: Union[str, int],
            group_id: Union[str, int],
            user_limit_modifier: UserLimitModifier
    ) -> str:
        user_id = str(user_id)
        group_id = str(group_id)
        user_last_update_time = self.get_user_last_update(function_name, user_id)
        group_last_update_time = self.get_user_last_update(function_name, group_id)
        function_usage_limit = self.get_function_limit(function_name)
        user_hit = self.get_user_hit(function_name, user_id)
        group_hit = self.get_user_hit(function_name, group_id)

        if int(time.time()) - group_last_update_time > 60:
            update_group_hit = 1
            group_last_update_time_updated = int(time.time())
        else:
            if group_hit + 1 > function_usage_limit:
                return self.LIMIT_BY_GROUP
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

        if int(time.time()) - user_last_update_time > user_limit_modifier.rate_limit_time:
            update_user_hit = 1
            user_last_update_time_updated = int(time.time())
        else:
            if user_hit + 1 > function_usage_limit * user_limit_modifier.rate_limit_modifier:
                return self.LIMIT_BY_USER
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
        return ''
