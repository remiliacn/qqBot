import json
from os.path import exists
from random import choice
from typing import Union


class Shadiaoadmin:
    def __init__(self):
        self.access_token = 'PLACEHOLDER'
        self.auth_stat = False
        self.repeat_dict = {}

        self.group_path = 'config/group.json'
        self.group_quotes_path = 'data/quotes.json'
        file = open(self.group_path, 'r+')
        fl = file.read()
        self.group_setting = json.loads(str(fl))

        self.group_quotes = self._get_group_quotes()

    def _get_group_quotes(self) -> dict:
        group_quotes = {}
        if not exists(self.group_quotes_path):
            with open(self.group_quotes_path, 'w+') as file:
                json.dump(group_quotes, file)
        else:
            with open(self.group_quotes_path, 'r', encoding='utf-8') as file:
                group_quotes = json.loads(file.read())

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
    
    def get_group_quote_count(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        if group_id not in self.group_quotes:
            return 0

        if not self.group_quotes[group_id]:
            return 0

        return len(self.group_quotes[group_id])

    def set_data(self, group_id, tag, stat):
        if isinstance(group_id, int):
            group_id = str(group_id)

        if group_id not in self.group_setting:
            self.group_setting[group_id] = {}

        self.group_setting[group_id][tag] = stat
        self.make_a_json('config/group.json')

    def get_data(self, group_id, tag):
        if isinstance(group_id, int):
            group_id = str(group_id)

        if group_id not in self.group_setting:
            self.group_setting[group_id] = {}
            if tag != 'exempt':
                self.group_setting[group_id][tag] = True
            else:
                self.group_setting[group_id][tag] = False

            self.make_a_json('config/group.json')

        if tag not in self.group_setting[group_id]:
            if tag != 'exempt':
                self.group_setting[group_id][tag] = True
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