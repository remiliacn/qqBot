import re
import time
from os import getcwd
from os.path import exists

import aiohttp
from aiocqhttp import MessageSegment
from loguru import logger

from config import SAUCE_API_KEY


async def sauce_helper(url):
    params = {
        'output_type': 2,
        'api_key': SAUCE_API_KEY,
        'testmode': 0,
        'db': 999,
        'numres': 6,
        'url': url
    }

    response = {}

    async with aiohttp.ClientSession() as client:
        async with client.get(
                'https://saucenao.com/search.php',
                params=params
        ) as page:
            json_data = await page.json()
            if json_data['results']:
                response = await _analyze_saucenao_response(json_data, client)

    return response


async def _analyze_saucenao_response(json_data: dict, client):
    json_data = json_data['results'][0]
    logger.info(f'Json data: \n'
                f'{json_data}')

    if json_data:
        simlarity = json_data['header']['similarity'] + '%'
        thumbnail = json_data['header']['thumbnail']

        path = await _download_saunce_nao_thumbnail(client, thumbnail)
        if not path:
            return {}

        image_content = MessageSegment.image(f'file:///{path}')

        json_data = json_data['data']
        if 'ext_urls' not in json_data:
            if 'jp_name' not in json_data:
                return {}

        ext_url = json_data['ext_urls'][0] if 'ext_urls' in json_data else '[数据删除]'
        return await _analyze_sauce_nao_content(json_data, simlarity, image_content, ext_url, thumbnail)


async def _analyze_sauce_nao_content(json_data, simlarity, image_content, ext_url, thumbnail):
    pixiv_id = 'Undefined'
    title = 'Undefined'
    author = 'Undefined'

    if 'title' not in json_data:
        if 'creator' in json_data:
            author = json_data['creator']
            if isinstance(author, list):
                author = '，'.join(author)
            elif not isinstance(author, str):
                return {}

        elif 'author' in json_data:
            author = json_data['author']
        else:
            if 'source' and 'est_time' in json_data:
                year = json_data['year']
                part = json_data['part']
                est_time = json_data['est_time']

                return {
                    'simlarity': simlarity,
                    'year': year,
                    'part': part,
                    'est_time': est_time,
                    'source': json_data['source'],
                    'thumbnail': image_content
                }

            if 'artist' not in json_data:
                # Handle cases where the image is found in twitter.
                if 'tweet_id' in json_data:
                    return {
                        'data': image_content,
                        'simlarity': simlarity,
                        'title': title,
                        'author': author,
                        'pixiv_id': pixiv_id,
                        'ext_url': ext_url,
                        'thumbnail': thumbnail
                    }
                return {}

            author = json_data['artist']

        if 'jp_name' in json_data:
            title = json_data['jp_name']

    elif 'title' in json_data:
        title = json_data['title']
        if 'author_name' in json_data:
            author = json_data['author_name']
        elif 'member_name' in json_data:
            author = json_data['member_name']
            if 'pixiv_id' in json_data:
                pixiv_id = json_data['pixiv_id']

    response = {
        'data': image_content,
        'simlarity': simlarity,
        'title': title,
        'author': author,
        'pixiv_id': pixiv_id,
        'ext_url': ext_url,
        'thumbnail': thumbnail
    }

    return response


async def _download_saunce_nao_thumbnail(client, thumbnail) -> str:
    async with client.get(thumbnail) as page:
        file_name = thumbnail.split('/')[-1]
        file_name = re.sub(r'\?auth=.*?$', '', file_name)
        if len(file_name) > 10:
            file_name = f'{int(time.time())}.jpg'

        path = f'{getcwd()}/data/pixivPic/{file_name}'
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
