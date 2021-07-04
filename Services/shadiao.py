import os
import random
import re
import time
from json import dump, loads

import aiohttp
import nonebot
import requests

# 临时图库，在网站不可用的时候使用里面的图片。
# github : remiliacn

INFO_NOT_AVAILABLE = "信息暂不可用"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"
}


class flatter:
    def __init__(self):
        self.flatter_path = 'data/flatter.json'
        self.flatter_dict = self._get_flatter_dict()

    def _get_flatter_dict(self) -> dict:
        if not os.path.exists(self.flatter_path):
            with open(self.flatter_path, 'w+') as file:
                dump({}, file, indent=4)

            return {}

        with open(self.flatter_path, 'r', encoding='utf8') as file:
            return loads(file.read())

    def get_flatter_result(self, name: int) -> str:
        flatter_list = self.flatter_dict['data']
        if flatter_list:
            return random.choice(flatter_list).replace('${name}', f'[CQ:at,qq={name}]')

        return '暂无数据！'


class ShadiaoAPI:
    def __init__(self):
        self.base_dir = f'{os.getcwd()}/data/biaoqing/'
        self.timeout = aiohttp.ClientTimeout(total=10)
        self._init_base_dir()
        self.page = random.randint(0, 10)
        self.base_url = f"https://www.fabiaoqing.com/biaoqing/lists/page/{self.page}.html"
        self.image_list = []

    def _init_base_dir(self):
        if not os.path.exists(self.base_dir):
            try:
                os.makedirs(self.base_dir)
            except IOError:
                raise IOError(f'Unable to create directory: {self.base_dir}')

    async def get_image_list(self):
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=self.timeout) as client:
                async with client.get(self.base_url) as page:
                    image_list = re.findall(r'data-original="(.*?)"', await page.text())

        except Exception as e:
            print("发表情网不可用：错误%s" % e)
            image_list = os.listdir(self.base_dir)

        self.image_list = image_list

    async def get_picture(self):
        random.seed(time.time_ns())
        image = random.choice(self.image_list)
        try:
            file_detailed_name = image.split('/')[-1]
            file_name = self.base_dir + file_detailed_name
            if not os.path.exists(file_name):
                async with aiohttp.ClientSession(timeout=self.timeout) as client:
                    async with client.get(image) as page:
                        page.raise_for_status()
                        with open(file_name, 'wb') as f:
                            while True:
                                chunk = await page.content.read(1024 ** 2)
                                if not chunk:
                                    break
                                f.write(chunk)

            nonebot.logger.info(f"Picture got: {file_name}")
            return file_name

        except Exception as e:
            image_list = os.listdir(self.base_dir)
            nonebot.logger.warning("Exception occurred: %s" % e)
            return self.base_dir + random.choice(image_list)


class Avalidator:
    def __init__(self, text):
        self.base_url = f'https://www.libredmm.com/movies/{text}'
        self.torrent_url = 'https://idope.se/'
        self._client = None
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.page_text = ''
        self.product_number = text

    async def get_page_text(self):
        try:
            self._client = aiohttp.ClientSession(timeout=self.timeout)
            async with self._client.get(self.base_url) as page:
                self.page_text = await page.text()

        except aiohttp.ClientTimeout:
            self.page_text = ''

    async def get_content(self) -> str:
        from lxml import etree
        if self.page_text:
            e = etree.HTML(self.page_text)
            title_temp = e.xpath('/html/body/main/h1/span[2]/text()')[0]
            if not title_temp:
                title = '暂不可用'
            else:
                title = ''.join(title_temp)

            date = re.findall(r'<dd>(\d+.*?)</dd>', self.page_text)
            date = date[0] if date else '暂不可用'

            source = re.findall(r'<dd><a href="(.*?)"', self.page_text)
            if not source:
                source = '暂不可用'
            else:
                source = str(source[0]).replace('http://', '').replace('https://', '').replace('.', '点')

            torrentURL = self.torrent_url + f'/torrent-list/{self.product_number}'

            try:
                async with self._client.get(torrentURL) as page:
                    urls = re.findall('<a href="(/torrent/.*?)"', await page.text())
            except Exception as e:
                return f'连接出错: {e}'

            if not urls:
                tor = '暂不可用'
            else:
                try:
                    page = requests.get(self.torrent_url + urls[0], timeout=10)
                except Exception as err:
                    return f'连接出错 {err}'

                tor = re.findall(r'<div id="deteails">(.*?)</div>', page.text)
                if not tor:
                    tor = '暂不可用'
                else:
                    tor = tor[0]

            return f'从番号{self.product_number}我拿到了以下结果：\n' \
                   f'片名：{title}\n' \
                   f'日期：{date}\n' \
                   f'来源：{source}\n' \
                   f'磁链：{tor}'

        return f'未查到与番号"{self.product_number}"相关的内容。'
