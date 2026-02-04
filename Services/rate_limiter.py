import sqlite3
import time
from dataclasses import dataclass, fields
from functools import wraps
from inspect import signature
from typing import Any, Callable, Union, Optional, Iterable

from loguru import logger
from nonebot.internal.matcher import Matcher

from Services.util.common_util import time_to_literal
from model.common_model import RateLimitStatus
from util.db_utils import fetch_one_or_default


@dataclass
class RateLimitConfig:
    """
    速率限制配置，支持可选的渐进式/指数退避。

    标准速率限制参数：
        user_time: 同一用户连续使用之间的基础延迟时间（秒）。
        user_count: 在时间周期内每个用户允许使用的次数。
        group_time: 同一群组内连续使用之间的延迟时间（秒）。
        group_count: 在时间周期内每个群组允许使用的次数。
        apply_group_limit: 如果为True，在用户限制之外还应用群组级速率限制。
                          如果group_time或group_count被设置，则自动设置为True。

    渐进式速率限制（指数退避）参数：
        progressive: 如果为True，对群组内重复使用启用指数退避。
                    每次连续使用会使延迟时间呈指数级增长。
                    仅适用于群聊，不适用于私聊。
                    前N次使用保持基础延迟，从第N+1次开始递增（N由tolerance定义）。
        multiplier: 每次连续使用时应用的倍数。
                   例如：基础时间=20秒，倍数=1.5时：
                   第1次：20秒，第2次：20秒，第3次：30秒，第4次：45秒，第5次：67.5秒
        max_period: 最大延迟时间上限（秒），防止极端锁定。
                   达到上限后，延迟时间不再增加。
        reset_after: 不活跃期限（秒），超过此时间后渐进式状态将重置。
                    如果用户等待时间超过此值，延迟将重置为基础时间。
        tolerance: 允许的连续命中次数，在此期间不增加延迟时间。

    限制逻辑：
        - 用户限制和群组限制独立检查
        - 如果配置了用户限制，则检查用户是否超限
        - 如果配置了群组限制，则检查群组是否超限
        - 只要任一限制触发，整体判定为受限
        - 可以只配置用户限制、只配置群组限制，或两者都配置

    示例：
        仅用户限制：
        >>> config = RateLimitConfig(user_time=30.0, user_count=2)
        # 每个用户30秒内最多使用2次

        仅群组限制：
        >>> config = RateLimitConfig(group_time=60, group_count=10)
        # 每个群组60秒内最多使用10次

        用户+群组限制：
        >>> config = RateLimitConfig(user_time=20.0, user_count=1, group_time=60, group_count=5)
        # 每个用户20秒内最多1次，且每个群组60秒内最多5次

        渐进式速率限制（指数退避）：
        >>> config = RateLimitConfig(
        ...     user_time=20.0,
        ...     multiplier=1.5,
        ...     max_period=300.0,
        ...     reset_after=120.0
        ... )
        # 用户延迟递增：20秒 → 20秒 → 30秒 → 45秒 → 67.5秒 → ... → 300秒（达到上限）
        # 前两次使用保持基础延迟，从第3次开始递增
        # 在不活跃120秒后重置为20秒
    """
    user_time: Optional[float | int] = None
    user_count: Optional[float | int] = None
    group_time: Optional[float | int] = None
    group_count: Optional[float | int] = None
    apply_user_limit: bool = False
    apply_group_limit: bool = False
    progressive: bool = False
    multiplier: Optional[float | int] = None
    max_period: Optional[float | int] = None
    reset_after: Optional[float | int] = None
    tolerance: int = 2

    def __post_init__(self):
        numeric_fields = {
            f.name for f in fields(self)
            if f.type in (float, int, Optional[float], Optional[int]) or 'float' in str(f.type) or 'int' in str(f.type)
        }
        for field_name in numeric_fields:
            if (val := getattr(self, field_name, None)) is not None and not isinstance(val, (int, float)):
                raise TypeError(f"{field_name} must be int or float, got {type(val).__name__}")

        if self.user_time is not None or self.user_count is not None:
            self.apply_user_limit = True
            if self.user_time is None or self.user_time <= 0:
                self.user_time = 30.0
            if self.user_count is None or self.user_count <= 0:
                self.user_count = 1.0

        if self.group_time is not None or self.group_count is not None:
            self.apply_group_limit = True
            if self.group_time is None or self.group_time <= 0:
                self.group_time = 20
            if self.group_count is None or self.group_count <= 0:
                self.group_count = 1

        if self.multiplier is not None or self.max_period is not None or self.reset_after is not None:
            self.progressive = True

            if not self.multiplier or self.multiplier <= 1.0:
                self.multiplier = 2.0
            if not self.max_period or self.max_period <= 0.0:
                self.max_period = 320.0
            if not self.reset_after or self.reset_after <= 0.0:
                self.reset_after = 120.0

        if self.tolerance < 0:
            self.tolerance = 0

        if not self.apply_user_limit and not self.apply_group_limit:
            self.apply_user_limit = True
            self.user_time = 30.0
            self.user_count = 1.0


class RateLimiter:
    def __init__(self):
        self.rate_limiter_database_path = 'data/db/ratelimiter.db'
        self.rate_limiter_db = sqlite3.connect(self.rate_limiter_database_path)
        self.LIMIT_BY_GROUP = 'GROUP'
        self.LIMIT_BY_USER = 'USER'
        self.TEMPRORARY_DISABLED = 'DISABLED'
        self._progressive_state: dict[str, dict[str, Union[float, int]]] = {}

        self._init_ratelimiter()

    @staticmethod
    def _now() -> float:
        return time.time()

    def _init_ratelimiter(self):
        self.rate_limiter_db.execute(
            """
            create table if not exists rate_limiter_config
            (
                function_name varchar(255) unique on conflict ignore primary key,
                rate_limit integer
            )
            """
        )
        self.rate_limiter_db.execute(
            """
            create table if not exists rate_limiter
            (
                user_id      varchar(30),
                function_name varchar(255),
                hit          integer,
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
            """,
            (function_name, rate_limit),
        )

        self.rate_limiter_db.commit()

    async def reset_user_limit(self, user_id: Union[int, str]):
        self.rate_limiter_db.execute(
            """
            update rate_limiter
            set hit = 1
            where user_id = ?;
            """,
            (str(user_id),),
        )

        self.rate_limiter_db.commit()

    async def get_function_limit(self, function_name: str):
        result = self.rate_limiter_db.execute(
            """
            select rate_limit
            from rate_limiter_config
            where function_name = ?
            limit 1;
            """,
            (function_name,),
        ).fetchone()

        if result is not None and result[0] is not None:
            return result[0]

        await self.set_function_limit(function_name, 10)
        return 10

    async def get_user_last_update(self, function_name: str, user_id: Union[str, int]):
        user_id_str = str(user_id)
        result = self.rate_limiter_db.execute(
            """
            select last_updated
            from rate_limiter
            where user_id = ?
              and function_name = ?
            limit 1;
            """,
            (user_id_str, function_name),
        ).fetchone()

        if result is None or result[0] is None:
            return self._now()

        return int(result[0])

    async def get_user_hit(self, function_name: str, user_id: Union[str, int]):
        user_id_str = str(user_id)
        result = self.rate_limiter_db.execute(
            """
            select hit
            from rate_limiter
            where function_name = ?
              and user_id = ?
            limit 1;
            """,
            (function_name, user_id_str),
        ).fetchone()

        return fetch_one_or_default(result, 0)

    async def _get_user_state(self, function_name: str, user_id: str) -> tuple[int, float]:
        result = self.rate_limiter_db.execute(
            """
            select hit, last_updated
            from rate_limiter
            where function_name = ?
              and user_id = ?
            limit 1;
            """,
            (function_name, user_id),
        ).fetchone()

        if not result:
            return 0, self._now()

        hit = fetch_one_or_default((result[0],), 0)
        last_updated = int(result[1]) if result[1] is not None else self._now()
        return hit, last_updated

    def _upsert_state(self, user_id: str, function_name: str, hit: int, last_updated: float) -> None:
        self.rate_limiter_db.execute(
            """
            insert or replace into rate_limiter (user_id, function_name, hit, last_updated) values (
                ?, ?, ?, ?
            )
            """,
            (user_id, function_name, hit, int(last_updated)),
        )
        self.rate_limiter_db.commit()

    async def _query_group_permission(
            self,
            function_name: str,
            group_id: str,
            time_period=60.0,
            override_function_limit=None
    ) -> tuple[str, float] | tuple[str, int]:
        now = self._now()
        function_usage_limit = (
            await self.get_function_limit(function_name)
            if override_function_limit is None
            else override_function_limit
        )

        group_hit, group_last_update_time = await self._get_user_state(function_name, group_id)

        if function_usage_limit <= 0:
            return self.TEMPRORARY_DISABLED, group_last_update_time + time_period - now

        if now - group_last_update_time > time_period:
            update_group_hit = 1
            group_last_update_time_updated = now
        else:
            if group_hit + 1 > function_usage_limit:
                return self.LIMIT_BY_GROUP, group_last_update_time + time_period - now
            update_group_hit = group_hit + 1
            group_last_update_time_updated = group_last_update_time

        self._upsert_state(group_id, function_name, update_group_hit, group_last_update_time_updated)
        return '', -1

    async def _query_user_permission(
            self,
            function_name: str,
            user_id: str,
            time_period: float,
            usage_limit: float
    ):
        now = self._now()
        user_hit, user_last_update_time = await self._get_user_state(function_name, user_id)

        if usage_limit <= 0:
            return self.TEMPRORARY_DISABLED, int(user_last_update_time + time_period - now)

        if now - user_last_update_time > time_period:
            update_user_hit = 1
            user_last_update_time_updated = now
        else:
            if user_hit + 1 > usage_limit:
                return self.LIMIT_BY_USER, int(user_last_update_time + time_period - now)

            update_user_hit = user_hit + 1
            user_last_update_time_updated = user_last_update_time

        self._upsert_state(user_id, function_name, update_user_hit, user_last_update_time_updated)
        return '', -1

    async def _assemble_limit_prompt(self, prompt, wait_time) -> RateLimitStatus:
        if prompt == self.LIMIT_BY_USER:
            return RateLimitStatus(
                True,
                f'别玩啦，过{await time_to_literal(wait_time if wait_time > 0 else 1)}再回来玩好不好？',
            )
        elif prompt == self.LIMIT_BY_GROUP:
            return RateLimitStatus(True, f'群使用已到达允许上限，请稍等{await time_to_literal(wait_time)}重试')
        elif prompt == self.TEMPRORARY_DISABLED:
            return RateLimitStatus(True, f'该功能全局禁用中，请稍等{await time_to_literal(wait_time)}再试。')

        return RateLimitStatus(False, None)

    async def group_limit_check(
            self,
            function_name: str,
            group_id: Union[str, int],
            time_period=60.0,
            function_limit=None
    ) -> RateLimitStatus:
        group_id = str(group_id)
        query_result, wait_time = await self._query_group_permission(
            function_name,
            group_id,
            time_period=time_period,
            override_function_limit=function_limit
        )
        return await self._assemble_limit_prompt(query_result, wait_time)

    async def check_rate_limits_with_config(
            self,
            function_name: str,
            user_id: Union[str, int],
            group_id: Union[str, int],
            config: RateLimitConfig
    ) -> RateLimitStatus:
        user_id_str = str(user_id)
        group_id_str = str(group_id)

        if config.apply_user_limit:
            user_time_period = config.user_time

            if config.progressive and group_id != -1:
                key = f"{function_name}:{group_id_str}:{user_id_str}"
                current_time = time.time()

                if key not in self._progressive_state:
                    self._progressive_state[key] = {
                        "consecutive_uses": 0,
                        "last_use_time": 0,
                        "current_period": config.user_time
                    }

                state = self._progressive_state[key]
                time_since_last = current_time - state["last_use_time"]

                if time_since_last > config.reset_after:
                    state["consecutive_uses"] = 0
                    state["current_period"] = config.user_time

                user_time_period = state["current_period"]

            query_user_prompt, user_wait_time = await self._query_user_permission(
                function_name,
                user_id_str,
                user_time_period,
                config.user_count
            )

            if query_user_prompt:
                user_limit_status = await self._assemble_limit_prompt(query_user_prompt, user_wait_time)
                if user_limit_status.is_limited:
                    return user_limit_status

            if config.progressive and group_id != -1:
                key = f"{function_name}:{group_id_str}:{user_id_str}"
                state = self._progressive_state[key]
                state["consecutive_uses"] += 1
                state["last_use_time"] = time.time()

                exponent = max(0, state["consecutive_uses"] - config.tolerance or 0)
                new_period = min(
                    config.user_time * (config.multiplier ** exponent),
                    config.max_period
                )
                state["current_period"] = new_period

        if config.apply_group_limit and group_id != -1:
            group_check = await self.group_limit_check(
                function_name,
                group_id,
                time_period=config.group_time,
                function_limit=config.group_count
            )
            if group_check.is_limited:
                return group_check

        return RateLimitStatus(False, None)

    @staticmethod
    def _extract_ids_from_args(func: Callable, args: tuple, kwargs: dict) -> tuple[Optional[str], Optional[str], Any]:
        sig = signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        user_id = None
        group_id = None

        matcher = bound_args.arguments.get('matcher') or bound_args.arguments.get('_matcher')
        if 'event' in bound_args.arguments or '_event' in bound_args.arguments:
            event = bound_args.arguments.get('event') or bound_args.arguments.get('_event')
            if hasattr(event, 'get_user_id') and callable(event.get_user_id):
                user_id = event.get_user_id()
            elif hasattr(event, 'user_id'):
                user_id = event.user_id

            group_id = getattr(event, 'group_id', -1)

        if user_id is None and 'user_id' in bound_args.arguments:
            user_id = bound_args.arguments['user_id']

        if group_id is None and 'group_id' in bound_args.arguments:
            group_id = bound_args.arguments['group_id']

        if group_id is None:
            group_id = -1

        return user_id, group_id, matcher

    async def _handle_rate_limit_check(
            self,
            function_name: str | Iterable[str],
            user_id: str,
            group_id: str | int,
            config: RateLimitConfig,
            matcher: Matcher,
            show_prompt: bool,
            override_prompt: Optional[str] = None
    ) -> Optional[RateLimitStatus]:
        function_names = [function_name] if isinstance(function_name, str) else list(function_name)

        for func_name in function_names:
            rate_limit_status = await self.check_rate_limits_with_config(
                func_name,
                user_id,
                group_id,
                config
            )

            if rate_limit_status.is_limited:
                logger.warning(f'User: {user_id} is rate limited for function: {func_name}')
                if matcher is not None:
                    if show_prompt and (override_prompt or rate_limit_status.prompt):
                        await matcher.finish(override_prompt or rate_limit_status.prompt)
                    else:
                        await matcher.finish()
                return rate_limit_status

        return None

    def rate_limit(
            self, *, func_name: str | Iterable[str],
            config: RateLimitConfig, show_prompt: bool = True,
            override_prompt: Optional[str] = None) -> Callable:
        """
        Decorator for rate limit

        Args:
            func_name: function key
            config: RateLimitConfig object.
            show_prompt: If True, shows rate limit message; if False, silent finish
            override_prompt: If filled, overrides the default rate limit prompt message

        Returns:
            Decorator that wraps async functions with rate limiting

        Behavior:
            - If rate limit is exceeded: calls matcher.finish() or matcher.finish(prompt)
            - If rate limit is not exceeded: returns the original function result
            - FinishedException is raised and should be caught by nonebot handler
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                user_id, group_id, matcher = self._extract_ids_from_args(func, args, kwargs)

                if user_id is None:
                    raise ValueError(
                        f"Could not extract user_id from function {func.__name__}. "
                        "Function must have 'event' parameter (GroupMessageEvent/PrivateMessageEvent) "
                        "or 'user_id' parameter."
                    )

                limited_status = await self._handle_rate_limit_check(
                    func_name,
                    user_id,
                    group_id,
                    config,
                    matcher,
                    show_prompt,
                    override_prompt
                )

                if limited_status is not None:
                    return limited_status

                return await func(*args, **kwargs)

            return wrapper

        return decorator
