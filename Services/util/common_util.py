from typing import List, Union

from nonebot import CommandSession

from Services.util.ctx_utility import get_user_id, get_group_id


def _compile_forward_node(self_id: str, data: str):
    return {
        'type': 'node',
        'data': {
            'name': 'Meow',
            'uin': self_id,
            'content': data
        }
    }


async def get_general_ctx_info(ctx: dict) -> (int, int, int):
    message_id = ctx['message_id']
    return message_id, get_user_id(ctx), get_group_id(ctx)


async def time_to_literal(time: int) -> str:
    hour = time // 3600
    time %= 3600

    minute = time // 60
    second = time % 60

    result = ''
    result += f'{hour}时' if hour > 0 else ''
    result += f'{minute}分' if minute > 0 else ''
    result += f'{second}秒'

    return result


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


if __name__ == '__main__':
    print(time_to_literal(3675))
