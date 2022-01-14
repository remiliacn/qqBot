import asyncio
from os import getcwd
from random import choice
from re import findall

import aiohttp

from Services.util.download_helper import download_image

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/97.0.4692.71 Safari/537.36'
}


class NiceImageCrawler:
    def __init__(self):
        self.main_url = 'http://212.129.244.210/'

    async def get_image_list_in_index(self):
        async with aiohttp.ClientSession() as client:
            page = await client.get(self.main_url, headers=HEADERS)
            raw_response = await page.text()
            images_list = findall(r'<a href="(.*?)" title="(.*?)" .*? rel="bookmark">', raw_response)
            return images_list

    @staticmethod
    async def get_random_image_by_url(url):
        async with aiohttp.ClientSession() as client:
            page = await client.get(url, headers=HEADERS)
            raw_response = await page.text()
            image_list = findall(r'<a href="(.*?\.jpg)"', raw_response)
            url = choice(image_list)
            path = await download_image(url, f'{getcwd()}/data/pixivPic')
            return path

    async def get_random_image(self):
        image_url_list = await self.get_image_list_in_index()
        return await self.get_random_image_by_url(choice(image_url_list)[0])


async def main():
    test = NiceImageCrawler()
    print(await test.get_random_image_by_url('http://212.129.244.210/?p=5981'))
    print(await test.get_random_image())


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
