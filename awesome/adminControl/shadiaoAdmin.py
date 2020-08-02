import json
class Shadiaoadmin:
    def __init__(self):
        self.enabled  = True
        self.trusted_user = {}
        self.access_token = 'PLACEHOLDER'
        self.auth_stat = False
        self.i_know = False
        self.repeat_dict = {}

        file = open('config/trustedUser.json', 'r+')
        fl = file.read()
        self.trusted_user = json.loads(str(fl))

        file = open('config/adminUser.json', 'r+')
        fl = file.read()
        self.admin_user = json.loads(str(fl))

        file = open('config/group.json', 'r+')
        fl = file.read()
        self.group_setting = json.loads(str(fl))

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

    def get_admin_users(self):
        return self.admin_user

    def set_access_token(self, access_token):
        self.access_token = access_token

    def get_access_token(self):
        return self.access_token

    def get_if_authed(self):
        return self.auth_stat

    def set_if_authed(self, stats):
        self.auth_stat = stats

    def add_trusted_user(self, user_id):
        if isinstance(user_id, int):
            user_id = str(user_id)

        self.trusted_user[user_id] = True
        self.make_a_json('config/trustedUser.json')

    def delete_trusted_user(self, user_id):
        if isinstance(user_id, int):
            user_id = str(user_id)

        self.trusted_user[user_id] = False
        self.make_a_json('config/trustedUser.json')

    def add_admin_user(self, user_id):
        if isinstance(user_id, int):
            user_id = str(user_id)

        self.admin_user[user_id] = True
        self.trusted_user[user_id] = True
        self.make_a_json('config/adminUser.json')

    def delete_admin_user(self, user_id):
        if isinstance(user_id, int):
            user_id = str(user_id)

        self.admin_user[user_id] = False
        self.trusted_user[user_id] = False
        self.make_a_json('config/adminUser.json')

    def get_trusted_user(self):
        return self.trusted_user

    def make_a_json(self, file_name):
        if file_name == 'config/trustedUser.json':
            with open('config/trustedUser.json', 'w+') as f:
                json.dump(self.trusted_user, f, indent=4)

        elif file_name == 'config/adminUser.json':
            with open('config/adminUser.json', 'w+') as f:
                json.dump(self.admin_user, f, indent=4)

        elif file_name == 'config/group.json':
            with open('config/group.json', 'w+') as f:
                json.dump(self.group_setting, f, indent=4)