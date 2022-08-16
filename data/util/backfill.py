import json
import sqlite3
from os import getcwd, path
from typing import Union


class Backfill:
    def __init__(self):
        self.quote_data_file = f'{getcwd()}/data/db/quotes.db'
        self.quote_connection = sqlite3.connect(self.quote_data_file)
        self.setu_data_file_original = 'config/setu.json'
        self.setu_data_file = f'{getcwd()}/data/db/setu.db'
        self.setu_connection = sqlite3.connect(self.setu_data_file)

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

        if path.exists(self.quote_data_file):
            with open(self.quote_data_file) as file:
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


if __name__ == '__main__':
    o = Backfill()
    o.main_execution_setu()
    print(o.setu_connection.execute(
        f"""
    select penalty from bad_words where keyword = ?
    """, ('陈睿',)))
