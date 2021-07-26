import json
import re
from os.path import exists
from random import choice
from typing import Union

# Tag list meaning hint.
TAG_LIST = {
    'recall': {
        'description': '是否拦截撤回',
        'default': False
    },
    'banned': {
        'description': '是否不接受该群的指令',
        'default': False
    },
    'exempt': {
        'description': '是否使用闪照',
        'default': True
    },
    'R18': {
        'description': '是否允许R18内容',
        'default': False
    }
}


class Shadiaoadmin:
    def __init__(self):
        self.access_token = 'PLACEHOLDER'
        self.auth_stat = False
        self.repeat_dict = {}

        self.group_path = 'config/group.json'
        self.group_quotes_path = 'data/quotes.json'
        if not exists(self.group_path):
            with open(self.group_path, 'w+') as file:
                json.dump({}, file)

        file = open(self.group_path, 'r+')
        fl = file.read()
        self.group_setting = json.loads(str(fl))

        self.group_quotes = self._get_group_quotes()
        self.make_a_json(self.group_quotes_path)

    def _get_group_quotes(self) -> dict:
        group_quotes = {}
        if not exists(self.group_quotes_path):
            with open(self.group_quotes_path, 'w+') as file:
                json.dump(group_quotes, file)
        else:
            with open(self.group_quotes_path, 'r', encoding='utf-8') as file:
                group_quotes = json.loads(file.read())

            # Remove quote if the image does not exist anymore.
            for element in group_quotes:
                if group_quotes[element]:
                    removed_list = []
                    for quote in group_quotes[element]:
                        file_name = re.match(r'.*?file=file:///(.*?)]', quote).groups()[0]
                        if not exists(file_name):
                            removed_list.append(quote)

                    for idx in removed_list:
                        group_quotes[element].remove(idx)

        return group_quotes

    def add_quote(self, group_id: Union[int, str], quote: str):
        if isinstance(group_id, int):
            group_id = str(group_id)

        if group_id not in self.group_quotes:
            self.group_quotes[group_id] = []

        if quote not in self.group_quotes[group_id]:
            self.group_quotes[group_id].append(quote)
            self.make_a_json(self.group_quotes_path)

    def get_group_quote(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        if group_id not in self.group_quotes:
            return '本组还没有语录哦~'

        if not self.group_quotes[group_id]:
            return '本组还没有语录哦~'

        return choice(self.group_quotes[group_id])

    def combine_group_quote(self, *args) -> bool:
        group_id_collection = [str(x) for x in args]
        for idx, group_id in enumerate(group_id_collection):
            if group_id not in self.group_quotes:
                return False
            if idx != 0:
                quote_for_group = self.group_quotes[group_id]
                for element in quote_for_group:
                    self.group_quotes[group_id_collection[0]].append(element)
        return True

    def clear_group_quote(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        if group_id not in self.group_quotes:
            return False

        if not self.group_quotes[group_id]:
            return False

        self.group_quotes[group_id].clear()
        self.make_a_json(self.group_quotes_path)
        return True

    def get_group_quote_count(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        if group_id not in self.group_quotes:
            return 0

        if not self.group_quotes[group_id]:
            return 0

        return len(self.group_quotes[group_id])

    def set_group_permission(self, group_id, tag, stat, global_setting=False):
        if isinstance(group_id, int):
            group_id = str(group_id)

        if group_id not in self.group_setting:
            self.group_setting[group_id] = {}

        if not global_setting:
            self.group_setting[group_id][tag] = stat
        else:
            self.group_setting['global'][tag] = stat

        self.make_a_json('config/group.json')

    def get_group_permission(self, group_id, tag, default_if_none=True):
        if isinstance(group_id, int):
            group_id = str(group_id)

        if group_id not in self.group_setting:
            self.group_setting[group_id] = {}

        if tag not in self.group_setting[group_id]:
            if tag != 'exempt':
                self.group_setting[group_id][tag] = default_if_none
            else:
                self.group_setting[group_id][tag] = False

            self.make_a_json('config/group.json')

        return self.group_setting[group_id][tag]

    def set_access_token(self, access_token):
        self.access_token = access_token

    def get_access_token(self):
        return self.access_token

    def get_if_authed(self):
        return self.auth_stat

    def set_if_authed(self, stats):
        self.auth_stat = stats

    def make_a_json(self, file_name):
        if file_name == self.group_path:
            with open(self.group_path, 'w+') as f:
                json.dump(self.group_setting, f, indent=4)

        elif file_name == self.group_quotes_path:
            with open(self.group_quotes_path, 'w+') as f:
                json.dump(self.group_quotes, f, indent=4)
