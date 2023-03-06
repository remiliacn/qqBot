import json
from os import getcwd
from os.path import exists
from re import findall

from aiocache import cached
from aiocache.serializers import PickleSerializer

from Services.util.common_util import HttpxHelperClient


class KeylolFreeGame:
    def __init__(self):
        self.free_post_url = 'https://keylol.com/t572814-1-1'
        self.file_location = f'{getcwd()}/data/util/keylol.json'
        self.keylol_data = self._get_keylol_file_data()
        self.client = HttpxHelperClient()

    def _get_keylol_file_data(self):
        if not exists(self.file_location):
            with open(self.file_location, 'w+', encoding='utf-8') as file:
                file.write(json.dumps({'data': {}, 'qq': -1}, indent=4))
            return {'data': {}, 'qq': -1}

        with open(self.file_location, 'r') as file:
            return json.loads(file.read())

    def _save_keylol_data(self):
        with open(self.file_location, 'w+') as file:
            file.write(json.dumps(self.keylol_data, indent=4))

    def get_update_qq(self) -> int:
        return self.keylol_data['qq']

    def get_free_game_list(self) -> str:
        if not self.keylol_data['data']:
            return '无'

        response = ''
        for key, value in self.keylol_data['data'].items():
            response += f'{key}: {value}\n'

        response += '信息来源：其乐lol'
        return response

    @cached(ttl=60 * 60 * 6, serializer=PickleSerializer())
    async def get_update(self) -> str:
        page = await self.client.get(self.free_post_url)

        page_text = page.text
        game_title = findall(
            r'<h3 class="KyloStylisedHeader2">(.*?)</h3>',
            page_text
        )
        game_url = findall(
            r'<a href="(https://keylol.com/t\d+-\d-\d)" target="_blank">\1</a>.*?（发帖人',
            page.text
        )

        try:
            keylol_data = zip(game_title, game_url)
            keylol_dict = {}
            for element in keylol_data:
                keylol_dict[element[0]] = element[1]

            if not self.keylol_data['data']:
                self.keylol_data['data'] = keylol_dict
                self._save_keylol_data()
                return ''

            original_keylol_dict = self.keylol_data['data']
            response = ''
            if original_keylol_dict != keylol_dict:
                self.keylol_data['data'] = keylol_dict
                response += f'可免费领取的游戏更新：\n'
                response += self.get_free_game_list()

                self._save_keylol_data()

            return response

        except Exception as err:
            print(f'keylol data error: {err}')
