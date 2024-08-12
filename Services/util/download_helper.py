from os import makedirs, path
from os.path import exists
from time import time

from nonebot import logger

from Services.util import global_httpx_client


async def download_image(url, saved_path: str, headers=None) -> str:
    if headers is None:
        headers = {}
    if not exists(saved_path):
        try:
            makedirs(saved_path)
        except OSError:
            return ''

    file_name = url.split('/')[-1]
    if len(file_name) > 10 or '.' not in file_name:
        file_name = f'{int(time())}.{file_name.split(".")[-1]}'

    saved_path = path.join(saved_path, file_name)
    if not exists(saved_path):
        try:
            return await global_httpx_client.download(url=url, file_name=saved_path, headers=headers)
        except IOError:
            logger.error(f'Failed to download {url}. This is an IOError')

    return ''
