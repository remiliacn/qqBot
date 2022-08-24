from nonebot import CommandSession


def is_float(content: str) -> bool:
    try:
        float(content)
        return True

    except ValueError:
        return False


async def check_if_number_user_id(session: CommandSession, arg: str):
    if not arg.isdigit():
        session.finish('输入非法')

    return arg
