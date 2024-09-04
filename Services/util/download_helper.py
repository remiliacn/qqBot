from os import makedirs, path
from os.path import exists
from re import sub

from nonebot import logger

from Services.util import global_httpx_client
from Services.util.common_util import slight_adjust_pic_and_get_path, calculate_sha1_string


async def download_image(url: str, saved_path: str, headers=None, needs_postprocess=False) -> str:
    logger.info(f'Now trying to download: {url}')

    if headers is None:
        headers = {}
    if not exists(saved_path):
        try:
            makedirs(saved_path)
        except OSError:
            return ''

    logger.debug(f'Downloading file from URL: {url}')
    file_name = url.split('/')[-1]
    file_name = sub(r'\?auth=.*?$', '', file_name)
    if len(file_name) > 25 or '.' not in file_name:
        if 'nt.qq.com' not in url:
            file_name = f'{calculate_sha1_string(url)}'
        else:
            file_name = f'{calculate_sha1_string(url)}'

    saved_path = path.join(saved_path, file_name)
    if not exists(saved_path):
        try:
            return await global_httpx_client.download(url=url, file_name=saved_path, headers=headers)
        except IOError:
            logger.error(f'Failed to download {url}. This is an IOError')

        if needs_postprocess:
            edited_path = await slight_adjust_pic_and_get_path(saved_path)
            return edited_path

    return ''
