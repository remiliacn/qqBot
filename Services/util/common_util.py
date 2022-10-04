from typing import List, Union

from nonebot import CommandSession


def _compile_forward_node(self_id: str, data: str):
    return {
        'type': 'node',
        'data': {
            'name': 'Meow',
            'uin': self_id,
            'content': data
        }
    }


def compile_forward_message(self_id: Union[int, str], *args: List[str]) -> list:
    self_id = str(self_id)
    data_list = []
    for arg in args:
        data_list.append(_compile_forward_node(self_id, arg))

    return data_list


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
