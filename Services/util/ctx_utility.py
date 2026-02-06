from nonebot import logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent


def get_user_id(event: GroupMessageEvent) -> str:
    return event.get_user_id()


def get_group_id(event: GroupMessageEvent | PrivateMessageEvent) -> int:
    if isinstance(event, GroupMessageEvent):
        return event.group_id

    return -1


def get_nickname(event: GroupMessageEvent) -> str:
    logger.info(f'sender event card: [{event.sender.card}], sender nickname: [{event.sender.nickname}]')
    return event.sender.card.strip() if event.sender.card.strip() else event.sender.nickname.strip()
