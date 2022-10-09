import re
from os import getcwd

from nonebot.log import logger as logging
from urllib3 import HTTPSConnectionPool

from Services.util.common_util import HttpxHelperClient


class BilibiliLive:
    def __init__(self, live_room_cid, ch_name: str):
        self.api_url = f'https://api.live.bilibili.com/room/v1/Room/get_info?room_id={live_room_cid}'
        self.ch_name = ch_name
        self.client = HttpxHelperClient()

    @staticmethod
    async def _get_info_in_json(json_result: dict, ch_name: str) -> str:
        live_title = json_result['data']['title']
        live_desc: str = json_result['data']['description']
        live_desc = re.sub('<.*?>', '', live_desc)
        live_cover = json_result['data']['user_cover']

        client = HttpxHelperClient()

        file_name = live_cover.split('/')[-1]
        path = f'{getcwd()}/data/bilibiliPic/{file_name}'
        path = await client.download(live_cover, path, timeout=10.0)

        return f'{ch_name}开播啦！\n' \
               f'直播间标题：{live_title}\n' \
               f'直播间描述：{live_desc}\n' \
               f'封面\n' \
               f'[CQ:image,file=file:///{path}]'

    async def _get_live_info(self):
        live_temp_dict = {}
        try:
            page = await self.client.get(self.api_url, timeout=5)
        except HTTPSConnectionPool as err:
            logging.warning(f'Uncaught error while fetching bilibili live for {self.ch_name}: {err}')
            self.status = False
            self.live_stat = {}
            return

        if not page.status_code == 200:
            logging.warning(f'API connection failed to bilibili live room update for {self.ch_name}')
            self.status = False
            self.live_stat = {}

        json_result = page.json()
        live_stat = json_result['data']['live_status']
        if live_stat == 1:
            info = await self._get_info_in_json(json_result, self.ch_name)
            live_temp_dict[self.ch_name] = info
            self.status = True
            self.live_stat = live_temp_dict
        else:
            self.status = False
            self.live_stat = {}

    def get_status(self):
        return self.status

    def get_info(self):
        return self.live_stat
