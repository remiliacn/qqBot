from os import path, mkdir, remove, rmdir, walk
from os.path import exists, abspath, join
from typing import Optional, List
from zipfile import ZipFile

from PIL import Image
from nonebot import logger
from youtube_dl.utils import sanitize_filename

from Services.util import global_httpx_client
from awesome.Constants.path_constants import PIXIV_PIC_PATH


async def download_gif(ugoira_url: str, title: str, duration: float) -> Optional[str]:
    if ugoira_url is None:
        logger.warning('Zip ugoira is None!!!')
        return None

    title = sanitize_filename(title)
    gif_zip_path = path.join(PIXIV_PIC_PATH, title).__str__()
    zip_file_name = ugoira_url.split('/')[-1]

    return await _download_gif_processor(zip_file_name, ugoira_url, gif_zip_path, duration)


async def _download_gif_processor(
        zip_file_name: str, ugoira_url: str, gif_zip_path: str, duration: float) -> Optional[str]:
    gif_zip_path_path = None
    zip_file_path = path.join(PIXIV_PIC_PATH, zip_file_name)
    if not exists(gif_zip_path):
        zip_file_path = \
            await global_httpx_client.download(
                ugoira_url, zip_file_path, headers={'Referer': 'https://app-api.pixiv.net/'})

        gif_zip_path_path = gif_zip_path.split('.gif')[0] + '.gif'
        gif_zip_path = gif_zip_path.split('.')[0]
        with ZipFile(zip_file_path, 'r') as zipref:
            if not exists(gif_zip_path):
                mkdir(gif_zip_path)
            zipref.extractall(gif_zip_path)
            im = Image.open(_get_absolute_file_paths(gif_zip_path)[0])
            logger.info('Making the gif...')
            im.save(f'{gif_zip_path_path}', save_all=True,
                    append_images=[Image.open(file) for file in _get_absolute_file_paths(gif_zip_path)],
                    duration=duration,
                    loop=0)

        logger.info('Removing gif making single img cache...')
        remove(zip_file_path)
        for file in _get_absolute_file_paths(gif_zip_path):
            remove(file)

        logger.info('Removing zip cache.')
        rmdir(gif_zip_path)

    return gif_zip_path_path


def _get_absolute_file_paths(directory) -> List[str]:
    file_paths = []
    for folder, subs, files in walk(directory):
        for filename in files:
            file_paths.append(abspath(join(folder, filename)))

    return file_paths
