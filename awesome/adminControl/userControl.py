class Grouplearning:
    def __init__(self):
        file = open('config/learning.json', 'r+')
        fl = file.read()
        import json
        self.user_dict = json.loads(str(fl))
        file = open('config/bannedUser.json', 'r+')
        fl = file.read()
        self.banned_dict = json.loads(str(fl))
        self.last_question = {}
        print('Done getting stuffs')
        self.user_repeat_question_count = {}

    def set_user_repeat_question(self, user_id):
        if user_id not in self.user_repeat_question_count:
            self.user_repeat_question_count[user_id] = 1
        else:
            self.user_repeat_question_count[user_id] += 1

    def get_user_repeat_question(self, user_id):
        if user_id not in self.user_repeat_question_count:
            return 0

        return self.user_repeat_question_count[user_id]

    def add_banned(self, user_id):
        self.banned_dict[user_id] = True
        self.make_a_banned_json()

    def delete_banned(self, user_id):
        if user_id in self.banned_dict:
            self.banned_dict[user_id] = False
            self.make_a_banned_json()

    def get_if_user_banned(self, user_id):
        user_id = str(user_id)
        if user_id in self.banned_dict:
            return self.banned_dict[user_id]

        return False

    def add_response(self, question, answer_dict):
        self.user_dict[question] = answer_dict
        self.make_a_json()

    def rewrite_file(self, question, answer_dict):
        if question not in self.user_dict:
            return False

        if 'restriction' not in self.user_dict[question] or not self.user_dict[question]['restriction']:
            self.user_dict[question] = answer_dict
            self.make_a_json()
            return True

        return False

    def delete_response(self, key_word):
        if key_word in self.user_dict:
            del self.user_dict[key_word]
            self.make_a_json()
            return True

        return False

    def get_user_dict(self):
        return self.user_dict

    def get_user_response(self, question):
        return self.user_dict[question]['answer']

    def make_a_json(self):
        import json
        with open('config/learning.json', 'w+') as f:
            json.dump(self.user_dict, f, indent=4)

    def make_a_banned_json(self):
        import json
        with open('config/bannedUser.json', 'w+') as f:
            json.dump(self.banned_dict, f, indent=4)

    def get_response_info(self, question):
        if question in self.user_dict:
            return '关键词%s的加入情况如下：\n' \
                   '加入者QQ：%d\n' \
                   '加入人QQ昵称：%s\n' \
                   '录入回答：%s' % (question, self.user_dict[question]['from_user'],
                                self.user_dict[question]['user_nickname'], self.user_dict[question]['answer'])

        return '该关键词我还没有学习过哦~'