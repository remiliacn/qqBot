import os
import random

import requests
from nonebot.log import logger

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"
}


class WaifuFinder:
    def __init__(self):
        self.base_url = 'https://www.thiswaifudoesnotexist.net/'
        self.page = self._get_page_content()
        self._youtuber_name = \
            [
                '千铃',
                '夏实萌惠',
                'poyoyo',
                '百鬼绫目',
                '狗妈',
                '狗狗',
                '鹿乃',
                '野野宫',
                '小东',
                '花丸',
                '夸哥',
                '古守',
                '乙女音'
            ]

    def _get_page_content(self) -> str:
        try:
            page = requests.get(self.base_url, timeout=10)
        except Exception as err:
            logger.warning(f'Error in {__class__.__name__}: {err}')
            return ''
        return page.text

    def get_image(self) -> (str, str):
        if not os.path.exists(f"{os.getcwd()}/Waifu/"):
            os.makedirs(f"{os.getcwd()}/Waifu/")

        rand_num = random.randint(1, 100000)
        image_name = 'example-%d.jpg' % rand_num

        file_name = f"{os.getcwd()}/Waifu/" + image_name
        try:
            if not os.path.exists(file_name):
                img = requests.get(self.base_url + image_name, timeout=6)
                img.raise_for_status()
                with open(file_name, 'wb') as f:
                    for chunk in img.iter_content(chunk_size=1024 ** 3):
                        f.write(chunk)

        except Exception as e:
            logger.warning('Something went wrong when getting the waifu. Error message: %s' % e)
            return '', '完了，服务器炸了！拿图片失败'

        return file_name, \
               '这是AI随机生成的老婆，但是没%s可爱！' \
               % self._youtuber_name[
                   random.randint(0, len(self._youtuber_name) - 1)
               ]


if __name__ == '__main__':
    waifu = WaifuFinder()
    print(waifu.get_image())
