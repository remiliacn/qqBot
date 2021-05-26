import base64
import time
from typing import Union

import requests
import re

from config import CANGKU_USERNAME, CANGKU_PASSWORD

NO_SEARCH_RESULT_ERROR = '无搜索结果'
UNKNOWN_ERROR = '未知错误'

OK = 'OK'
FAILED = 'Failed'

class CangkuResponse:
    def __init__(self, status: str, data: any, error=None):
        self.status = status
        self.data = data
        self.error = error


    def get_status(self) -> str:
        return self.status


    def get_data(self):
        return self.data


    def get_error(self):
        if self.error is not None:
            return self.error
        else:
            return 'No Error'


class CangkuApi:
    def __init__(self):
        self._search_api = 'https://cangku.io/api/v1/post/search?search='
        self._info_api = 'https://cangku.io/api/v1/post/info?id='
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/90.0.4430.212 Safari/537.36',
            'referer': 'https://cangku.io/',
            'origin': 'https://cangku.io',
            'accept': 'application/json, text/plain, */*'
        }
        self.temp_info = {}

        self.session = requests.Session()
        self.auth()
        self.last_auth_time = time.time()


    def auth(self):
        _ = self.session.get(
            'https://cangku.io/login'
        )

        payload = {
            "login": CANGKU_USERNAME,
            "password": CANGKU_PASSWORD,
            "remember": False,
            "include": "roles,"
                       "meta:"
                       "include(location|website|birthday|post_display|date_display|new_tab)"
        }

        xsrf_token = self.session.cookies.get_dict()['XSRF-TOKEN'].replace('%3D', '')
        self.headers['x-xsrf-token'] = xsrf_token
        self.session.post(
            'https://cangku.io/api/v1/auth/login',
            headers=self.headers,
            json=payload
        )


    def _get_search_results(
            self,
            query: str,
            user_id: str,
            is_r18: bool=True
    ) -> CangkuResponse:
        search_url = self._search_api + query
        if is_r18:
            page = self.session.get(search_url, headers=self.headers)
        else:
            page = requests.get(search_url)

        if page.status_code != 200:
            return CangkuResponse(FAILED, {}, error=NO_SEARCH_RESULT_ERROR)

        page_data = page.json()
        if 'data' not in page_data:
            return CangkuResponse(FAILED, {}, error=UNKNOWN_ERROR)

        data = page_data['data']
        self.temp_info[user_id] = data
        return CangkuResponse(OK, data)


    def get_search_string(self, query: str, user_id: str, is_r18: bool=True) -> str:
        result = self._get_search_results(query, user_id, is_r18)
        # Auth may expired.
        if time.time() - self.last_auth_time > 3600:
            self.auth()
            self.last_auth_time = time.time()

        if result.get_status() != OK:
            return result.get_error()

        response = ''
        data = result.get_data()
        if len(data) > 10:
            data = data[0:10]

        for idx, element in enumerate(data):
            if 'title' not in element:
                response += f'{idx + 1}. 未知标题\n'
            else:
                response += f'{idx + 1}. {element["title"]}\n'

        return response


    def get_info_by_index(self, user_id: str, index: Union[str, int]) -> CangkuResponse:
        if isinstance(index, str):
            if not index.isdigit():
                return CangkuResponse(FAILED, {}, error='输入非数字')

            index = int(index)

        index -= 1

        if user_id not in self.temp_info:
            return CangkuResponse(FAILED, {}, error='不。。不可能！你怎么触发这个错误的？')

        if not self.temp_info[user_id]:
            return CangkuResponse(FAILED, {}, error=NO_SEARCH_RESULT_ERROR)

        if index >= len(self.temp_info[user_id]):
            return CangkuResponse(FAILED, {}, error='索引位置大于搜索结果最大数')

        data = self.temp_info[user_id][index]
        if 'id' not in data:
            return CangkuResponse(FAILED, {}, error=UNKNOWN_ERROR)

        info_page_url = self._info_api + str(data['id'])
        page = self.session.get(info_page_url, headers=self.headers)
        if page.status_code != 200:
            return CangkuResponse(FAILED, {}, error=UNKNOWN_ERROR)

        json_data = page.json()
        if 'data' not in json_data:
            return CangkuResponse(FAILED, {}, error=UNKNOWN_ERROR)

        data_content = json_data['data']['content']
        dissect_data = self._dissect_content_data(data_content)
        return dissect_data


    @staticmethod
    def anaylze_dissected_data(data: CangkuResponse) -> str:
        if data.get_status() != OK:
            return data.get_error()

        data = data.get_data()
        response = ''
        if 'title' in data:
            response += f'标题： {data["title"]}\n'

        if 'time' in data:
            response += f'发布时间：{data["time"]}\n'
        else:
            response += '发布时间：未知\n'

        if 'info' in data:
            response += f'额外信息：{data["info"]}\n'

        if 'from' in data:
            author = data['from']
            if author:
                response += f'发布者：{data["from"]}\n'
            else:
                response += f'发布者：？\n'

        if 'link1' in data:
            link = data["link1"]
            response += f'提取链接1：'
            base64_link = re.findall(r'#bdlink=(.*?)$', link)
            if base64_link:
                link = base64.b64decode(base64_link[0]).decode('utf-8')
                response += f'bdpan://{link} (检测到为仓库快传链接，请配合官方插件使用）'
            else:
                response += link

            response += '\n'

        if 'link2' in data:
            link = data["link2"]
            response += f'提取链接2：{link}'
            base64_link = re.findall(r'#bdlink=(.*?)$', link)
            if base64_link:
                link = base64.b64decode(base64_link[0]).decode('utf-8')
                response += f'bdpan://{link} (检测到为仓库快传链接，请配合官方插件使用）'
            else:
                response += link

            response += '\n'

        return response


    @staticmethod
    def _dissect_content_data(content: str) -> CangkuResponse:
        if 'dlbox' not in content:
            return CangkuResponse(FAILED, {}, error='No dlbox.')

        search = re.findall(r'\[dlbox (.*?)\]', content)
        if not search:
            return CangkuResponse(FAILED, {}, error='Dlbox not legal.')

        args = re.findall(r'[\w\d]+=".*?"', search[0])
        if not args:
            return CangkuResponse(FAILED, {}, error='Dissection failed.')

        info_dict = {}
        for arg in args:
            info = re.findall('(.*?)="(.*?)"', arg)

            # info = (key, value)
            if not info:
                continue

            info = info[0]
            key = info[0]
            value = info[1]
            info_dict[key] = value

        return CangkuResponse(OK, info_dict)

