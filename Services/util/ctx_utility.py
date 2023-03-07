from typing import Union

from aiocqhttp import Event as CQEvent


def get_user_id(ctx: Union[CQEvent, dict]) -> int:
    return ctx['user_id']


def get_message_id(ctx: Union[CQEvent, dict]) -> int:
    return ctx['message_id']


def get_group_id(ctx: Union[CQEvent, dict]) -> int:
    return ctx['group_id'] if 'group_id' in ctx else -1


def get_nickname(ctx: Union[CQEvent, dict]) -> str:
    try:
        nickname = ctx['sender']['nickname']
    except KeyError:
        nickname = 'null'

    return nickname
