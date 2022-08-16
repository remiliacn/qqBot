import json
import sqlite3
from os import path, getcwd
from typing import Union


class Backfill:
    def __init__(self):
        self.quote_data_file_original = f'{getcwd()}/data/quotes.json'
        self.quote_data_file = f'{getcwd()}/data/db/quotes.db'
        self.quote_connection = sqlite3.connect(self.quote_data_file)
        self.setu_data_file_original = 'config/setu.json'
        self.setu_data_file = f'{getcwd()}/data/db/setu.db'
        self.setu_connection = sqlite3.connect(self.setu_data_file)
        self.stat_data_file_original = 'config/stats.json'
        self.stat_data_file = f'{getcwd()}/data/db/stats.db'
        self.stat_connection = sqlite3.connect(self.stat_data_file)

    def _group_activity_backfill(self, group_id: str, value_obj: dict):
        for tag, value in value_obj.items():
            if isinstance(value, int):
                self.stat_connection.execute(
                    f"""
                    insert into group_activity_count (group_id, tag, hit) values (
                        '{group_id}', '{tag}', {value}
                    )
                    """
                )
            elif isinstance(value, dict):
                for tag2, value2 in value.items():
                    self.stat_connection.execute(
                        f"""
                        insert into user_activity_count (user_id, tag, hit) values (
                            '{group_id}', '{tag2}', {value2}
                        )
                        """
                    )
        self.stat_connection.commit()

    def _user_detail_activitity_backfill(self, user_id: str, data: dict):
        for tag, inner_data in data.items():
            if isinstance(inner_data, int):
                self.stat_connection.execute(
                    f"""
                    insert into user_activity_count (user_id, tag, hit) values (
                        '{user_id}', '{tag}', {inner_data}
                    )
                    """
                )
            elif isinstance(inner_data, dict) and tag == 'user_xp':
                self._user_xp_backfill(user_id, inner_data)

    def _bad_word_backfill(self, data: dict):
        for key, value in data.items():
            self.setu_connection.execute(
                f"""
                insert into bad_words (keyword, penalty) values ('{key}', {value})
                """
            )

        self.setu_connection.commit()

    def _keyword_backfill(self, data: dict):
        for key, value in data.items():
            record = (key, value)
            self.setu_connection.execute(
                f"""
                insert into setu_keyword (keyword, hit) VALUES (?, ?)
                """,
                record
            )

        self.setu_connection.commit()

    def _group_keyword_backfill(self, data: dict):
        for group_id, info in data.items():
            group_xp = info['groupXP']
            for keyword, hit in group_xp.items():
                record = (keyword, hit, group_id)
                self.setu_connection.execute(
                    f"""
                    insert into setu_group_keyword (keyword, hit, group_id) values 
                    (?, ?, ?)
                    """,
                    record
                )

        self.setu_connection.commit()

    def main_execution_stat(self):
        self.stat_connection.execute(
            """
            create table if not exists group_activity_count (
                "group_id" varchar(20) not null,
                "tag" varchar(20) not null,
                "hit" integer not null,
                unique(group_id, tag) on conflict ignore
            )
            """
        )
        self.stat_connection.execute(
            """
            create table if not exists user_activity_count (
                "user_id" varchar(20) not null,
                "tag" varchar(20) not null,
                "hit" integer not null,
                unique(user_id, tag) on conflict ignore 
            )
            """
        )
        self.stat_connection.execute(
            """
            create table if not exists user_xp_count (
                "user_id" varchar(20) not null,
                "keyword" varchar(150) not null,
                "hit" integer not null,
                unique(user_id, keyword) on conflict ignore
            )
            """
        )
        self.stat_connection.execute(
            """
            create table if not exists monitor_xp_data (
                "keyword" varchar(150) unique on conflict ignore,
                "hit" integer not null
            )
            """
        )
        self.stat_connection.execute(
            """
            create table if not exists global_stat (
                "keyword" varchar(150) unique on conflict ignore,
                "hit" integer not null
            )
            """
        )
        self.stat_connection.commit()

        if path.exists(self.stat_data_file_original):
            with open(self.stat_data_file_original, encoding='utf-8-sig') as file:
                data = json.loads(file.read())
                for key, value in data.items():
                    if key.isdigit():
                        self._group_activity_backfill(key, value)
                    elif key == 'users':
                        for user_id, data in value.items():
                            self._user_detail_activitity_backfill(user_id, data)
                    elif key == 'xp':
                        self._monitor_xp_backfill(value)
                    elif key == 'global':
                        self._global_data_backfill(value)

    def main_execution_setu(self):
        self.setu_connection.execute(
            """
            create table if not exists bad_words (
                "keyword" text unique on conflict ignore,
                "penalty" integer
            )
            """
        )
        self.setu_connection.execute(
            """
            create table if not exists setu_keyword (
                "keyword" text unique on conflict ignore,
                "hit" integer
            )
            """
        )
        self.setu_connection.execute(
            """
            create table if not exists setu_group_keyword (
                "keyword" text,
                "hit" integer,
                "group_id" varchar(20)
            )
            """
        )
        self.setu_connection.commit()

        if path.exists(self.setu_data_file_original):
            with open(self.setu_data_file_original, encoding='utf-8-sig') as file:
                json_data = json.loads(file.read())
                bad_word_dict = json_data['bad_words']
                keyword_data = json_data['keyword']
                group_data = json_data['group']

                self._bad_word_backfill(bad_word_dict)
                self._keyword_backfill(keyword_data)
                self._group_keyword_backfill(group_data)

    def main_execution_quote(self):
        self.quote_connection.execute(
            """
            create table if not exists quotes (
                "cq_image" text unique on conflict ignore,
                "qq_group" text
            )
            """
        )
        self.quote_connection.commit()

        if path.exists(self.quote_data_file_original):
            with open(self.quote_data_file_original) as file:
                data = json.loads(file.read())
                for key, values in data.items():
                    for value in values:
                        self.insert_data(key, value)

            self.commit_change()

    def insert_data(self, group_id: Union[int, str], cq_code: str):
        self.quote_connection.execute(
            f"""
            insert into quotes (cq_image, qq_group) values ('{cq_code}', '{group_id}')
            """
        )

    def commit_change(self):
        self.quote_connection.commit()

    def _user_xp_backfill(self, user_id: str, inner_data: dict):
        for tag, hit in inner_data.items():
            self.stat_connection.execute(
                f"""
                insert into user_xp_count (user_id, keyword, hit) values (
                    '{user_id}', ?, {hit}
                )
                """, (tag,)
            )

        self.stat_connection.commit()

    def _monitor_xp_backfill(self, inner_data: dict):
        for keyword, hit in inner_data.items():
            self.stat_connection.execute(
                """
                insert into monitor_xp_data (keyword, hit) values (
                    ?, ?
                )
                """, (keyword, hit)
            )

        self.stat_connection.commit()

    def _global_data_backfill(self, value: dict):
        for keyword, hit in value.items():
            self.stat_connection.execute(
                """
                insert into global_stat (keyword, hit) values (
                    ?, ?
                )
                """, (keyword, hit)
            )

        self.stat_connection.commit()


if __name__ == '__main__':
    o = Backfill()
    result = o.stat_connection.execute(
        """
        select rank() over(order by hit desc) 
        from group_activity_count where group_id = ? and tag = ?
        """, ('708157568', 'setu')
    ).fetchone()
    print(result)
