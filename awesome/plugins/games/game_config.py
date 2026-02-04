from pydantic import BaseModel

from Services.rate_limiter import RateLimitConfig


class GameConfig(BaseModel):
    BULLET_IN_GUN: int = 6
    """ 晚安模式在开启时会禁言中枪玩家6小时，而不是平常的2分钟。 """
    ENABLE_GOOD_NIGHT_MODE: bool = True


DICE_RATE_LIMIT = RateLimitConfig(
    user_time=15.0,
    user_count=1.0,
    group_time=5,
    group_count=1,
)

ROULETTE_RATE_LIMIT = RateLimitConfig(
    user_time=5.0,
    user_count=1.0,
    group_time=10.0,
    group_count=5.0,
)
