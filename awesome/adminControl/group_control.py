import json
import sqlite3
from os.path import exists
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
        self.group_quotes_path = 'data/db/quotes.db'

        self.group_quote_db = sqlite3.connect(self.group_quotes_path)
        if not exists(self.group_path):
            with open(self.group_path, 'w+') as file:
                json.dump({}, file)

        file = open(self.group_path, 'r+')
        fl = file.read()
        self.group_setting = json.loads(str(fl))

    def _get_group_quotes(self):
        self.group_quote_db.execute(
            """
            create table if not exists quotes (
                "cq_image" text unique on conflict ignore, 
                "qq_group" text
            )
            """
        )
        self.group_quote_db.commit()

    def add_quote(self, group_id: Union[int, str], quote: str):
        if isinstance(group_id, int):
            group_id = str(group_id)

        self.group_quote_db.execute(
            f"""
            insert into quotes (cq_image, qq_group) values ('{quote}', '{group_id}')
            """
        )
        self.group_quote_db.commit()

    def get_group_quote(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        query = self.group_quote_db.execute(
            f"""
            select cq_image from quotes where qq_group = '{group_id}' order by random() limit 1;
            """
        ).fetchone()

        if query[0] is None:
            return '本组还没有语录哦~'

        return query[0]

    def clear_group_quote(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        self.group_quote_db.execute(
            f"""
            delete from quotes where qq_group='{group_id}'
            """
        )
        self.group_quote_db.commit()
        return True

    def get_group_quote_count(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        query_result = self.group_quote_db.execute(
            f"""
            select count(*) from quotes where qq_group='{group_id}'
            """
        )

        return query_result.fetchone()[0]

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
            self.group_quote_db.commit()
