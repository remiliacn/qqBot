from os.path import exists
from typing import List, Union

from httpx import AsyncClient
from loguru import logger
from nonebot import CommandSession

from Services.util.ctx_utility import get_user_id, get_group_id


def _compile_forward_node(self_id: str, data: str):
    return {
        'type': 'node',
        'data': {
            'name': '月朗风清',
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


class HttpxHelperClient:
    def __init__(self):
        self.headers = {
            'User-Agent': 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/84.0.4147.125 Safari/537.36'
        }

    async def get(self, url: str, timeout=5.0, headers=None):
        headers = headers if headers is not None else self.headers

        async with AsyncClient(timeout=timeout, headers=headers, verify=False) as client:
            return await client.get(url)

    async def post(self, url: str, json: dict, headers=None, timeout=10.0):
        headers = headers if headers is not None else self.headers
        async with AsyncClient(headers=headers, timeout=timeout) as client:
            return await client.post(url, json=json)

    async def download(self, url: str, file_name: str, timeout=20.0, headers=None):
        file_name = file_name.replace('\\', '/')
        headers = headers if headers is not None else self.headers

        try:
            if not exists(file_name):
                with open(file_name, 'wb') as file:
                    async with AsyncClient(timeout=timeout, headers=headers) as client:
                        async with client.stream('GET', url) as response:
                            async for chunk in response.aiter_bytes():
                                file.write(chunk)

            return file_name
        except Exception as err:
            logger.warning(f'Download failed in common util download: {err.__class__}')

        return ''
