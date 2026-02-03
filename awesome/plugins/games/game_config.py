from pydantic import BaseModel

from Services.rate_limiter import RateLimitConfig


class GameConfig(BaseModel):
    BULLET_IN_GUN: int = 6
    """ 晚安模式在开启时会禁言中枪玩家6小时，而不是平常的2分钟。 """
    ENABLE_GOOD_NIGHT_MODE: bool = True


DICE_RATE_LIMIT = RateLimitConfig(
    user_time_period=15.0,
    user_function_limit=1.0,
    allowlist_can_bypass=True,
    group_time_period=5,
    group_function_limit=1,
    apply_group_limit=True,
)
