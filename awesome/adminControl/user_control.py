import json
from os.path import exists
from typing import Union
from awesome.adminControl.permission import *

USER_T = Union[OWNER, ADMIN, WHITELIST, BANNED]

def _init_data(path: str) -> dict:
    if exists(path):
        with open(path, 'r', encoding='utf8') as file:
            fl = file.read()
            return json.loads(str(fl))

    else:
        empty_dict = {}
        with open(path, 'w+') as fl:
            json.dump(empty_dict, fl, indent=4)

    return {}


class UserControl:
    def __init__(self):
        self.WORD_DICT_PATH = 'config/learning.json'
        self.USER_DICT_PATH = 'config/users.json'

        self.answer_dict = _init_data(self.WORD_DICT_PATH)
        self.user_privilege = _init_data(self.USER_DICT_PATH)

        self.last_question = {}
        self.user_repeat_question_count = {}

    def set_user_privilege(self, user_id: Union[int, str], tag: USER_T, stat: bool):
        if isinstance(user_id, int):
            user_id = str(user_id)

        if user_id not in self.user_privilege:
            self.user_privilege[user_id] = {}

        self.user_privilege[user_id][tag] = stat
        self.make_a_json(self.USER_DICT_PATH)

    def get_user_privilege(self, user_id: Union[int, str], tag: USER_T) -> bool:
        if isinstance(user_id, int):
            user_id = str(user_id)

        if user_id not in self.user_privilege:
            return False

        if tag not in self.user_privilege[user_id]:
            return False

        return self.user_privilege[user_id][tag]

    def set_user_repeat_question(self, user_id):
        if user_id not in self.user_repeat_question_count:
            self.user_repeat_question_count[user_id] = 1
        else:
            self.user_repeat_question_count[user_id] += 1

    def get_user_repeat_question(self, user_id):
        if user_id not in self.user_repeat_question_count:
            return 0

        return self.user_repeat_question_count[user_id]

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

        elif path == self.USER_DICT_PATH:
            with open(path, 'w+') as f:
                json.dump(self.user_privilege, f, indent=4)

    def get_response_info(self, question):
        if question in self.answer_dict:
            return f'关键词{question}的加入情况如下：\n' \
                   f'加入者QQ：{self.answer_dict[question]["from_user"]}\n' \
                   f'加入人QQ昵称：{self.answer_dict[question]["user_nickname"]}\n' \
                   f'录入回答：{self.answer_dict[question]["answer"]}'

        return '该关键词我还没有学习过哦~'