from pydantic import BaseModel


class GameConfig(BaseModel):
    BULLET_IN_GUN: int = 6
    """ 晚安模式在开启时会禁言中枪玩家6小时，而不是平常的2分钟。 """
    ENABLE_GOOD_NIGHT_MODE: bool = True
