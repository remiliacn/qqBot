import requests
from lxml import etree
from nonebot.log import logger


class GetPCRNews:
    def __init__(self):
        self.base_url = 'https://api.biligame.com/news/' \
                        'list?gameExtensionId=267&positionId=2&typeId=4&pageNum=1&pageSize=5'
        self.headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0;"
                          " Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/81.0.4044.129 Safari/537.36"
        }
        self.info_not_available = '无搜索结果，请检查物品名是否存在国服PCR'

    def _get_update_id(self) -> int:
        try:
            page = requests.get(self.base_url, headers=self.headers, timeout=5.)
        except Exception as e:
            logger.warning(f"News error {e}")
            return -1

        json_data = page.json()
        return json_data['data'][0]['id']

    async def pcr_check(self, query) -> str:
        url = f'https://wiki.biligame.com/pcr/{query}'
        try:
            page = requests.get(url, headers=self.headers, timeout=10)
        except Exception as e:
            return f'查询出现错误: {e}'

        e = etree.HTML(page.text)
        searches = e.xpath('//*[@id="mw-content-text"]/div/table[2]/tbody/tr/th/a/text()')
        if searches:
            result = '主要掉落关卡：\n' + ''.join(element + ', ' for element in searches[0: len(searches) - 1]) + searches[
                len(searches) - 1] + '\n'
            searchesRare = e.xpath('//*[@id="mw-content-text"]/div/table[3]/tbody/tr/th/a/text()')
            result += '次要掉落关卡：\n'
            result += '无' if not searchesRare else ''.join(
                element + ', ' for element in searchesRare[0: len(searchesRare) - 1]) + searchesRare[
                                                       len(searchesRare) - 1] + '\n'

        else:
            return self.info_not_available

        return result
