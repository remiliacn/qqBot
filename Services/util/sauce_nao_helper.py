from os import getcwd

import aiohttp
from loguru import logger
from nonebot.adapters.onebot.v11 import MessageSegment

from Services.util.download_helper import download_image
from config import SAUCE_API_KEY


async def sauce_helper(url) -> dict:
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
                response = await _analyze_saucenao_response(json_data)

    return response


async def _analyze_saucenao_response(json_data: dict):
    json_data = json_data['results'][0]
    logger.info(f'Json data: \n'
                f'{json_data}')

    if json_data:
        header = json_data['header']
        simlarity = header['similarity'] + '%'
        thumbnail = header['thumbnail']
        index_name = header['index_name'] if 'index_name' in header else '无'

        path = await _download_saunce_nao_thumbnail(thumbnail)
        if not path:
            return {}

        image_content = MessageSegment.image(path)

        json_data = json_data['data']
        if 'ext_urls' not in json_data:
            if 'jp_name' not in json_data:
                return {}

        ext_url = json_data['ext_urls'][0] if 'ext_urls' in json_data else '[数据删除]'
        analyzed_data = await _analyze_sauce_nao_content(json_data, image_content)

        analyzed_data['simlarity'] = simlarity
        analyzed_data['ext_url'] = ext_url
        analyzed_data['thumbnail'] = image_content
        analyzed_data['index_name'] = index_name

        return analyzed_data


async def _analyze_sauce_nao_content(json_data: dict, image_content: MessageSegment) -> dict:
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
                        'title': title,
                        'author': author,
                        'pixiv_id': pixiv_id
                    }
                return {}

            author = json_data['artist']

        if 'jp_name' in json_data and json_data['jp_name']:
            title = json_data['jp_name']
        elif 'eng_name' in json_data and json_data['eng_name']:
            title = json_data['eng_name']

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
        'title': title,
        'author': author,
        'pixiv_id': pixiv_id
    }

    return response


async def _download_saunce_nao_thumbnail(thumbnail) -> str:
    return await download_image(thumbnail, f'{getcwd()}/data/pixivPic/', needs_postprocess=True)
