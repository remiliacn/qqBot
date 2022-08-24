import sqlite3
from typing import Union

DEFAULT_SETTINGS = {
    'IS_BANNED': False,
    'IS_ENABLED': True,
    'ALLOW_R18': False,
    'CATCH_RECALL': False,
    'NLP_PROCESS': True
}


class GroupControlModule:
    def __init__(self):
        self.access_token = 'PLACEHOLDER'
        self.auth_stat = False

        self.repeat_dict = {}

        self.group_quotes_path = 'data/db/quotes.db'

        self.group_info_db = sqlite3.connect(self.group_quotes_path)
        self._init_group_setting()

    def _init_group_setting(self):
        self.group_info_db.execute(
            """
            create table if not exists group_settings (
                group_id varchar(20) unique on conflict ignore,
                is_banned boolean,
                is_enabled boolean,
                allow_r18 boolean,
                recall_catch boolean,
                nlp_process boolean
            )
            """
        )
        self.group_info_db.commit()

    def _get_group_quotes(self):
        self.group_info_db.execute(
            """
            create table if not exists quotes (
                "cq_image" text unique on conflict ignore, 
                "qq_group" text
            )
            """
        )
        self.group_info_db.commit()

    def add_quote(self, group_id: Union[int, str], quote: str):
        if isinstance(group_id, int):
            group_id = str(group_id)

        self.group_info_db.execute(
            f"""
            insert into quotes (cq_image, qq_group) values ('{quote}', '{group_id}')
            """
        )
        self.group_info_db.commit()

    def get_group_quote(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        query = self.group_info_db.execute(
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

        self.group_info_db.execute(
            f"""
            delete from quotes where qq_group='{group_id}'
            """
        )
        self.group_info_db.commit()
        return True

    def get_group_quote_count(self, group_id: Union[int, str]):
        if isinstance(group_id, int):
            group_id = str(group_id)

        query_result = self.group_info_db.execute(
            f"""
            select count(*) from quotes where qq_group='{group_id}'
            """
        )

        return query_result.fetchone()[0]

    def set_group_permission(self, group_id: Union[int, str], tag, stat):
        group_id = str(group_id)

        self.group_info_db.execute(
            f"""
            insert or replace into group_settings 
            (group_id, {tag}) values (
                ?, ?
            )
            """, (group_id, stat)
        )

        self._commit_change()

    def get_group_permission(self, group_id: Union[int, str], tag: str) -> bool:
        if isinstance(group_id, int):
            group_id = str(group_id)

        result = self.group_info_db.execute(
            f"""
            select {tag} from group_settings where group_id = ? limit 1;
            """, (group_id,)
        ).fetchone()

        if result is None or result[0] is None:
            return DEFAULT_SETTINGS[tag.upper()]

        return result[0]

    def set_access_token(self, access_token):
        self.access_token = access_token

    def get_access_token(self):
        return self.access_token

    def get_if_authed(self):
        return self.auth_stat

    def set_if_authed(self, stats):
        self.auth_stat = stats

    def _commit_change(self):
        self.group_info_db.commit()


if __name__ == '__main__':
    o = GroupControlModule()
    print(o.get_group_permission(756519601, 'is_enabled'))
