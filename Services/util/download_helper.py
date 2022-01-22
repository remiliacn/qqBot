from os import makedirs
from os.path import exists
from re import sub
from time import time

import aiohttp


async def download_image(url, path: str, headers=None) -> str:
    if headers is None:
        headers = {}
    if not exists(path):
        try:
            makedirs(path)
        except OSError:
            return ''

    async with aiohttp.ClientSession(headers={} if headers is None else headers) as client:
        async with client.get(url) as page:
            file_name = url.split('/')[-1]
            file_name = sub(r'\?auth=.*?$', '', file_name)
            if len(file_name) > 10 or '.' not in file_name:
                file_name = f'{int(time())}.jpg'

            path = f'{path}/{file_name}'.replace('//', '/')
            if not exists(path):
                try:
                    with open(path, 'wb') as file:
                        while True:
                            chunk = await page.content.read(1024 ** 2)
                            if not chunk:
                                break

                            file.write(chunk)
                except IOError:
                    return ''

            return path
