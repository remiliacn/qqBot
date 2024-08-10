import os
import random
from json import dump, loads


class Flatter:
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

    def get_flatter_result(self, name: str) -> str:
        flatter_list = self.flatter_dict['data']
        if flatter_list:
            return random.choice(flatter_list).replace('${name}', f'[CQ:at,qq={name}]')

        return '暂无数据！'
