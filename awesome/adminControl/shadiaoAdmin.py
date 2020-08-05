import json
class Shadiaoadmin:
    def __init__(self):
        self.enabled  = True
        self.access_token = 'PLACEHOLDER'
        self.auth_stat = False
        self.i_know = False
        self.repeat_dict = {}

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

    def set_access_token(self, access_token):
        self.access_token = access_token

    def get_access_token(self):
        return self.access_token

    def get_if_authed(self):
        return self.auth_stat

    def set_if_authed(self, stats):
        self.auth_stat = stats

    def make_a_json(self, file_name):
        if file_name == 'config/group.json':
            with open('config/group.json', 'w+') as f:
                json.dump(self.group_setting, f, indent=4)