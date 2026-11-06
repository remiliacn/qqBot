from nonebot import logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent


def get_user_id(event: GroupMessageEvent | PrivateMessageEvent) -> str:
    return str(event.get_user_id())


def get_group_id(event: GroupMessageEvent | PrivateMessageEvent) -> int:
    if isinstance(event, GroupMessageEvent):
        return event.group_id

    return -1


def get_nickname(event: GroupMessageEvent | PrivateMessageEvent) -> str:
    card = (getattr(event.sender, 'card', None) or '').strip()
    nickname = (getattr(event.sender, 'nickname', None) or '').strip()
    logger.info(f'sender event card: [{card}], sender nickname: [{nickname}]')
    return card or nickname or str(event.get_user_id())
