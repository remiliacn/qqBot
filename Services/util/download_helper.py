from os import makedirs, path
from os.path import exists

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

    file_name = calculate_sha1_string(url)
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
