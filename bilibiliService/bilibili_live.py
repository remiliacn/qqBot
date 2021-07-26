import re
from os import getcwd

import requests
from nonebot.log import logger as logging
from urllib3 import HTTPSConnectionPool


def get_info_in_json(json_result, ch_name: str) -> str:
    live_title = json_result['data']['title']
    live_desc: str = json_result['data']['description']
    live_desc = re.sub('<.*?>', '', live_desc)
    live_cover = json_result['data']['user_cover']

    image = requests.get(live_cover, timeout=10)
    image.raise_for_status()

    file_name = live_cover.split('/')[-1]
    path = f'{getcwd()}/data/bilibiliPic/{file_name}'
    with open(path, 'wb') as file:
        file.write(image.content)

    return f'{ch_name}开播啦！\n' \
           f'直播间标题：{live_title}\n' \
           f'直播间描述：{live_desc}\n' \
           f'封面\n' \
           f'[CQ:image,file=file:///{path}]'


class BilibiliLive:
    def __init__(self, live_room_cid, ch_name: str):
        self.api_url = f'https://api.live.bilibili.com/room/v1/Room/get_info?room_id={live_room_cid}'
        self.ch_name = ch_name
        self.status, self.live_stat = self._get_live_info()

    def _get_live_info(self) -> (bool, dict):
        live_temp_dict = {}
        try:
            page = requests.get(self.api_url, timeout=5)
        except HTTPSConnectionPool as err:
            logging.warning(f'Uncaught error while fetching bilibili live for {self.ch_name}: {err}')
            return False, {}

        if not page.status_code == 200:
            logging.warning(f'API connection failed to bilibili live room update for {self.ch_name}')
            return False, {}

        json_result = page.json()
        live_stat = json_result['data']['live_status']
        if live_stat == 1:
            info = get_info_in_json(json_result, self.ch_name)
            live_temp_dict[self.ch_name] = info
            return True, live_temp_dict

        else:
            return False, {}

    def get_status(self):
        return self.status

    def get_info(self):
        return self.live_stat
