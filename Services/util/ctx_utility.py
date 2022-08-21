from aiocqhttp import Event as CQEvent


def get_user_id(ctx: CQEvent) -> int:
    return ctx['user_id']


def get_group_id(ctx: CQEvent) -> int:
    return ctx['group_id'] if 'group_id' in ctx else -1


def get_nickname(ctx: CQEvent) -> str:
    try:
        nickname = ctx['sender']['nickname']
    except KeyError:
        nickname = 'null'

    return nickname
