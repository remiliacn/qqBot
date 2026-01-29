import json
import sqlite3
from os import remove
from os.path import exists
from sqlite3 import OperationalError
from typing import Union, Optional

from nonebot import logger

from Services.util.common_util import OptionalDict
from awesome.Constants.user_permission import *
from config import SUPER_USER

USER_T = Union[OWNER, ADMIN, WHITELIST, BANNED]


def _init_data(path: str) -> dict:
    if exists(path):
        with open(path, 'r', encoding='utf8') as file:
            fl = file.read()
            return json.loads(str(fl))

    else:
        if SUPER_USER == 0:
            logger.error('请配置config的SUPER_USER参数')

            from time import sleep
            sleep(8)
            exit(-1)

        empty_dict = {
            str(SUPER_USER): {
                "OWNER": True,
                "ADMIN": True,
                "WHITELIST": True,
                "BANNED": False
            }
        }
        with open(path, 'w+') as fl:
            json.dump(empty_dict, fl, indent=4)

    return {}


class UserControl:
    def __init__(self):
        self.WORD_DICT_PATH = 'config/learning.json'
        self.USER_DICT_PATH = 'config/users.json'

        self.answer_dict = _init_data(self.WORD_DICT_PATH)

        self.user_settings_db_path = 'data/db/user_settings.db'
        self.user_settings_db = sqlite3.connect(self.user_settings_db_path)
        self._init_user_settings_db()
        self._import_user_privilege_from_json_if_needed(self.USER_DICT_PATH)
        self._ensure_super_user_seed()

        self.last_question = {}
        self.user_repeat_question_count = {}

    def _init_user_settings_db(self):
        self.user_settings_db.execute(
            """
            create table if not exists user_settings (
                user_id varchar(20) unique on conflict ignore,
                is_owner boolean not null default false,
                is_admin boolean not null default false,
                is_whitelist boolean not null default false,
                is_banned boolean not null default false
            )
            """
        )
        self.user_settings_db.commit()

    def _import_user_privilege_from_json_if_needed(self, json_path: str):
        if not exists(json_path):
            return

        try:
            raw = _init_data(json_path)
        except (OSError, json.JSONDecodeError) as err:
            logger.error(f'Failed to read legacy user privilege json at {json_path}: {err}')
            return

        if not raw:
            return

        try:
            for user_id, settings in raw.items():
                if not user_id:
                    continue

                is_owner = bool(OptionalDict(settings).map('OWNER').or_else(False))
                is_admin = bool(OptionalDict(settings).map('ADMIN').or_else(False))
                is_whitelist = bool(OptionalDict(settings).map('WHITELIST').or_else(False))
                is_banned = bool(OptionalDict(settings).map('BANNED').or_else(False))

                self.user_settings_db.execute(
                    """
                    insert into user_settings (user_id, is_owner, is_admin, is_whitelist, is_banned)
                    values (?, ?, ?, ?, ?)
                    on conflict(user_id) do update set
                        is_owner = excluded.is_owner,
                        is_admin = excluded.is_admin,
                        is_whitelist = excluded.is_whitelist,
                        is_banned = excluded.is_banned
                    """,
                    (str(user_id), int(is_owner), int(is_admin), int(is_whitelist), int(is_banned)),
                )

            self.user_settings_db.commit()
        except OperationalError as err:
            logger.error(f'Failed to import legacy privileges from {json_path}: {err}')
            return

        try:
            remove(json_path)
            logger.info(f'Legacy user privilege json migrated and deleted: {json_path}')
        except OSError as err:
            logger.error(f'Imported legacy privileges but failed to delete {json_path}: {err}')

    def _ensure_super_user_seed(self):
        if SUPER_USER == 0:
            logger.error('请配置config的SUPER_USER参数')
            from time import sleep
            sleep(8)
            exit(-1)

        super_user_id = str(SUPER_USER)
        self.user_settings_db.execute(
            """
            insert into user_settings (user_id, is_owner, is_admin, is_whitelist, is_banned)
            values (?, 1, 1, 1, 0)
            on conflict(user_id) do update set
                is_owner = 1,
                is_admin = 1,
                is_whitelist = 1,
                is_banned = coalesce(user_settings.is_banned, 0)
            """,
            (super_user_id,),
        )
        self.user_settings_db.commit()

    @staticmethod
    def _tag_to_column(tag: USER_T) -> Optional[str]:
        match tag:
            case 'OWNER':
                return 'is_owner'
            case 'ADMIN':
                return 'is_admin'
            case 'WHITELIST':
                return 'is_whitelist'
            case 'BANNED':
                return 'is_banned'
            case _:
                return None

    def set_user_privilege(self, user_id: Union[int, str], tag: USER_T, stat: bool):
        if isinstance(user_id, int):
            user_id = str(user_id)

        column = self._tag_to_column(tag)
        if not column:
            logger.error(f'Unknown privilege tag: {tag}')
            return

        columns_to_set: list[str] = [column]
        match column:
            case 'is_admin':
                columns_to_set.append('is_whitelist')
            case 'is_owner':
                columns_to_set.extend(['is_admin', 'is_whitelist'])

        columns_to_set = list(dict.fromkeys(columns_to_set))

        try:
            self.user_settings_db.execute(
                """
                insert into user_settings (user_id) values (?)
                on conflict(user_id) do nothing
                """,
                (user_id,),
            )

            value_to_set = int(bool(stat))
            set_clause = ", ".join([f"{c} = {value_to_set}" for c in columns_to_set])
            self.user_settings_db.execute(
                f"""
                update user_settings
                set {set_clause}
                where user_id = ?
                """,
                (user_id,),
            )

            self.user_settings_db.commit()
        except OperationalError as err:
            logger.error(f'Failed to set privilege {tag} for user {user_id}: {err}')

    def get_user_privilege(self, user_id: Union[int, str], tag: USER_T) -> bool:
        if isinstance(user_id, int):
            user_id = str(user_id)

        column = self._tag_to_column(tag)
        if not column:
            logger.error(f'Unknown privilege tag: {tag}')
            return False

        try:
            result = self.user_settings_db.execute(
                f"""
                select {column} from user_settings where user_id = ?
                """,
                (user_id,),
            ).fetchone()
        except OperationalError as err:
            logger.error(f'Failed to get privilege {tag} for user {user_id}: {err}')
            return False

        if not result:
            return False

        return bool(result[0])

    def set_user_repeat_question(self, user_id):
        if user_id not in self.user_repeat_question_count:
            self.user_repeat_question_count[user_id] = 1
        else:
            self.user_repeat_question_count[user_id] += 1

    def get_user_repeat_question(self, user_id):
        return OptionalDict(self.user_repeat_question_count).map(user_id).or_else(0)

    def get_last_question(self) -> dict:
        return self.last_question

    def get_last_question_by_group(self, group_id: Union[str, int]) -> Optional[str]:
        if isinstance(group_id, int):
            group_id = str(group_id)

        return OptionalDict(self.last_question).map(group_id).or_else(None)

    def set_last_question_by_group(self, group_id: Union[str, int], msg: str):
        if isinstance(group_id, int):
            group_id = str(group_id)

        self.last_question[group_id] = msg

    def add_response(self, question, answer_dict):
        self.answer_dict[question] = answer_dict
        self.make_a_json(self.WORD_DICT_PATH)

    def rewrite_file(self, question, answer_dict):
        if question not in self.answer_dict:
            return False

        if 'restriction' not in self.answer_dict[question] or not self.answer_dict[question]['restriction']:
            self.answer_dict[question] = answer_dict
            self.make_a_json(self.WORD_DICT_PATH)
            return True

        return False

    def delete_response(self, key_word):
        if key_word in self.answer_dict:
            del self.answer_dict[key_word]
            self.make_a_json(self.WORD_DICT_PATH)
            return True

        return False

    def get_user_response_dict(self):
        return self.answer_dict

    def get_user_response(self, question):
        return self.answer_dict[question]['answer']

    def make_a_json(self, path: str):
        import json
        if path == self.WORD_DICT_PATH:
            with open(path, 'w+') as f:
                json.dump(self.answer_dict, f, indent=4)

    def get_response_info(self, question):
        if question in self.answer_dict:
            return f'关键词{question}的加入情况如下：\n' \
                   f'加入者QQ：{self.answer_dict[question]["from_user"]}\n' \
                   f'加入人QQ昵称：{self.answer_dict[question]["user_nickname"]}\n' \
                   f'录入回答：{self.answer_dict[question]["answer"]}'

        return '该关键词我还没有学习过哦~'
