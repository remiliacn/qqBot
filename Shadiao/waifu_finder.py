from nonebot.log import logger
import os
import random
import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"
}

class waifuFinder:
    def __init__(self):
        self.baseURL = 'https://www.thiswaifudoesnotexist.net/'
        self.Page = self._getPageContent()
        self.youtuberName = [
                                '千铃', 
                                '夏实萌惠', 
                                '小狐狸', 
                                '夸哥', 
                                '夏哥', 
                                'poyoyo', 
                                '百鬼绫目', 
                                '狗妈', 
                                '狗狗', 
                                '鹿乃', 
                                '野野宫', 
                                '小东', 
                                '花丸', 
                                '樱巫女'
                            ]

    def _getPageContent(self) -> str:

        try:
            page = requests.get(self.baseURL, timeout=10)
        except Exception as err:
            logger.warning(f'Error in {__class__.__name__}: {err}')
            return ''
        return page.text

    def getImage(self) -> (str, str):
        if not os.path.exists("E:/Python/qqBot/Waifu/"):
            os.makedirs("E:/Python/qqBot/Waifu/")

        randNum = random.randint(1, 100000)
        imageName = 'example-%d.jpg' % randNum

        fileName = "E:/Python/qqBot/Waifu/" + imageName
        try:
            if not os.path.exists(fileName):
                img = requests.get(self.baseURL + imageName, timeout=6)
                img.raise_for_status()
                with open(fileName, 'wb') as f:
                    f.write(img.content)

        except Exception as e:
            logger.warning('Something went wrong when getting the waifu. Error message: %s' % e)
            return '', '完了，服务器炸了！拿去图片失败'

        return fileName, '这是AI随机生成的老婆，但是没%s可爱！' % self.youtuberName[random.randint(0, len(self.youtuberName) - 1)]

if __name__ == '__main__':
    waifu = waifuFinder()
    print(waifu.getImage())
