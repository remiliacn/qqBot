import os
import random

from loguru import logger

from Services.util.common_util import HttpxHelperClient


class WaifuFinder:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                          " AppleWebKit/537.36 (KHTML, like Gecko)"
                          " Chrome/75.0.3770.142 Safari/537.36"
        }
        self.base_url = 'https://www.thiswaifudoesnotexist.net/'
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
        self.client = HttpxHelperClient()

    async def get_image(self) -> (str, str):
        if not os.path.exists(f"{os.getcwd()}/Waifu/"):
            os.makedirs(f"{os.getcwd()}/Waifu/")

        rand_num = random.randint(1, 100000)
        image_name = 'example-%d.jpg' % rand_num

        file_name = f"{os.getcwd()}/Waifu/" + image_name
        try:
            file_name = await self.client.download(
                self.base_url + image_name,
                file_name,
                timeout=20.0,
                headers=self.headers
            )

        except Exception as e:
            logger.warning('Something went wrong when getting the waifu. Error message: %s' % e)
            return '', '完了，服务器炸了！拿图片失败'

        return file_name, f'这是AI随机生成的老婆，但是没{random.choice(self._youtuber_name)}可爱！'
