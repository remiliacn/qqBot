import json
import sqlite3
from os import getcwd
from typing import Union


class QuoteBackfill:
    def __init__(self):
        self.original_file_path = f'{getcwd()}/data/db/quotes.db'
        self.connection = sqlite3.connect(self.original_file_path)

    def main_execution(self):
        self.connection.execute(
            """
            create table if not exists quotes (
                "cq_image" text unique on conflict ignore, 
                "qq_group" text
            )
            """
        )
        self.connection.commit()

        with open(self.original_file_path) as file:
            data = json.loads(file.read())
            for key, values in data.items():
                for value in values:
                    self.insert_data(key, value)

        self.commit_change()

    def insert_data(self, group_id: Union[int, str], cq_code: str):
        self.connection.execute(
            f"""
            insert into quotes (cq_image, qq_group) values ('{cq_code}', '{group_id}')
            """
        )

    def commit_change(self):
        self.connection.commit()


if __name__ == '__main__':
    o = QuoteBackfill()
    o.main_execution()
