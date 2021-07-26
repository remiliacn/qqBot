from json import loads, dump
from os.path import exists


class SetuFunction:
    def __init__(self):
        self.max_sanity = 10
        self.sanity_dict = {}
        self.happy_hours = False
        self.remind_dict = {}
        self.stat_dict = {}
        self.ordered_stat = {}
        self.updated = False
        self.config_file = 'config/stats.json'
        self._get_user_data()
        self.setu_config_path = 'config/setu.json'
        self.setu_config = {}
        self._init_bad_word()

    def get_setu_usage(self) -> int:
        total = 0
        for element in self.stat_dict:
            personal_stat = self.stat_dict[element]
            total += personal_stat['setu'] if 'setu' in personal_stat else 0

        return total

    def track_keyword(self, key_word):
        if 'keyword' not in self.setu_config:
            self.setu_config['keyword'] = {}

        if key_word not in self.setu_config['keyword']:
            self.setu_config['keyword'][key_word] = 0

        self.setu_config['keyword'][key_word] += 1
        self.make_a_json(self.setu_config_path)

    def get_keyword_track(self) -> list:
        if 'keyword' not in self.setu_config:
            return []

        if not self.setu_config['keyword']:
            return []

        sort_orders = sorted(
            self.setu_config['keyword'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sort_orders

    def get_max_sanity(self) -> int:
        return self.max_sanity

    def get_bad_word_dict(self) -> dict:
        return self.setu_config['bad_words']

    def add_bad_word_dict(self, key_word, multiplier):
        if multiplier == 1:
            if key_word in self.setu_config['bad_words']:
                del self.setu_config['bad_words'][key_word]
        else:
            self.setu_config['bad_words'][key_word] = multiplier

    def _init_bad_word(self):
        if exists(self.setu_config_path):
            with open(self.setu_config_path, 'r', encoding='utf-8') as file:
                fl = file.read()
                self.setu_config = loads(str(fl))
                if 'bad_words' not in self.setu_config:
                    self.setu_config['bad_words'] = {}
                    self.make_a_json(self.setu_config_path)

        else:
            with open(self.setu_config_path, 'w+') as f:
                dump({'bad_words': {}}, f, indent=4)

    def get_monitored_keywords(self) -> dict:
        return self.stat_dict['xp']

    def set_new_xp(self, key_word):
        if key_word not in self.stat_dict['xp']:
            self.stat_dict['xp'][key_word] = 0

    def _get_user_data(self):
        if exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as file:
                fl = file.read()
                self.stat_dict = loads(str(fl))
                if 'users' not in self.stat_dict:
                    self.stat_dict['users'] = {}
                    self.make_a_json(self.config_file)

        else:
            with open(self.config_file, 'w+') as f:
                dump({'users': {}}, f, indent=4)

    def set_xp_data(self, tag: str):
        if tag in self.stat_dict['xp']:
            self.stat_dict['xp'][tag] += 1
        else:
            return

    def get_xp_data(self) -> dict:
        return self.stat_dict['xp']

    def set_user_data(
            self,
            user_id,
            tag: str,
            hit_marks=1,
            is_global=False
    ):
        if isinstance(user_id, int):
            user_id = str(user_id)

        if user_id not in self.stat_dict['users']:
            self.stat_dict['users'][user_id] = {
                tag: 0
            }

        if is_global:
            if 'global' not in self.stat_dict:
                self.stat_dict['global'] = {}

            if tag not in self.stat_dict['global']:
                self.stat_dict['global'][tag] = 0

            self.stat_dict['global'][tag] += 1

        else:
            user_dict = self.stat_dict['users'][user_id]
            if tag not in user_dict:
                self.stat_dict['users'][user_id][tag] = hit_marks
            else:
                self.stat_dict['users'][user_id][tag] += hit_marks

    def get_global_stat(self):
        return self.stat_dict['global']

    def get_user_data_by_tag(self, user_id, tag: str):
        if isinstance(user_id, int):
            user_id = str(user_id)

        if user_id not in self.stat_dict['users']:
            return 0
        if tag not in self.stat_dict['users'][user_id]:
            return 0

        return self.stat_dict['users'][user_id][tag]

    def get_user_data(self, user_id):
        if isinstance(user_id, int):
            user_id = str(user_id)

        if user_id not in self.stat_dict['users']:
            return {}

        return self.stat_dict['users'][user_id]

    def get_sanity_dict(self):
        return self.sanity_dict

    def set_usage(self, group_id, tag, data=None):
        group_id = str(group_id)
        if group_id not in self.stat_dict:
            self.stat_dict[group_id] = {
                "setu": 0,
                "yanche": 0,
                "pulls": {},
                "pull": 0
            }

        if tag == 'setu' or tag == 'yanche':
            self.stat_dict[group_id][tag] += 1

        elif tag == 'pulls':
            if '3' in self.stat_dict[group_id][tag] or '4' in self.stat_dict[group_id][tag] \
                    or '5' in self.stat_dict[group_id][tag] or '6' in self.stat_dict[group_id][tag]:

                self.stat_dict[group_id]['pulls']['3'] += data['3']
                self.stat_dict[group_id]['pulls']['4'] += data['4']
                self.stat_dict[group_id]['pulls']['5'] += data['5']
                self.stat_dict[group_id]['pulls']['6'] += data['6']

            else:
                self.stat_dict[group_id]['pulls'] = data
        elif tag == 'pull':
            self.stat_dict[group_id]['pull'] += 1

        self.updated = False

    def get_usage(self, group_id) -> (int, int, int, dict, int):
        group_id = str(group_id)
        if group_id not in self.stat_dict:
            return 0, -1, 0, {}, 0
        else:
            if 'setu' not in self.stat_dict[group_id] and 'yanche' not in self.stat_dict[group_id]:
                return 0, -1, 0, {}, 0
            if 'setu' not in self.stat_dict[group_id]:
                return 0, -1, self.stat_dict[group_id]['yanche'], {}, 0

        times = self.stat_dict[group_id]['setu']
        if self.updated:
            sorted_item = self.ordered_stat
        else:
            sorted_item = sorted(self.stat_dict.items(), key=lambda x: x[1]["setu"] if 'setu' in x[1] else 0,
                                 reverse=True)
            self.ordered_stat = sorted_item
            self.updated = True

        rank = -1
        delta = -1
        for idx, item in enumerate(sorted_item):
            if item[0] == group_id:
                rank = idx + 1
                break

        if rank != -1:
            rank_temp = rank - 1
            if rank == 1:
                delta = abs(sorted_item[rank_temp][1]['setu'] - sorted_item[rank_temp + 1][1]['setu'])
            else:
                delta = abs(sorted_item[rank_temp - 1][1]['setu'] - sorted_item[rank_temp][1]['setu'])

        pulls_dict = self.stat_dict[group_id]['pulls']
        return times, rank, \
               self.stat_dict[group_id]['yanche'] if 'yanche' in self.stat_dict[group_id] else -1, \
               delta, pulls_dict, self.stat_dict[group_id]['pull']

    def set_remid_dict(self, group_id, stats):
        self.remind_dict[group_id] = stats

    def set_sanity(self, group_id, sanity=2000):
        self.sanity_dict[group_id] = sanity

    def drain_sanity(self, group_id, sanity=1):
        self.sanity_dict[group_id] -= sanity

    def get_sanity(self, group_id):
        return self.sanity_dict[group_id]

    def fill_sanity(self, group_id=None, sanity=1):
        if group_id is None:
            for elements in self.sanity_dict:
                if self.sanity_dict[elements] + sanity > 0:
                    self.remind_dict[elements] = False
                if self.happy_hours:
                    if not self.sanity_dict[elements] >= self.max_sanity * 2:
                        self.sanity_dict[elements] += sanity
                else:
                    if not self.sanity_dict[elements] >= self.max_sanity:
                        self.sanity_dict[elements] += sanity
        else:
            if self.sanity_dict[group_id] + sanity > 0:
                self.remind_dict[group_id] = False
            self.sanity_dict[group_id] += sanity

    def make_a_json(self, file_name):
        if file_name == 'config/stats.json':
            with open(file_name, 'w+', encoding='utf-8') as f:
                dump(self.stat_dict, f, indent=4, ensure_ascii=False)
        elif file_name == 'config/setu.json':
            with open(file_name, 'w+', encoding='utf-8') as f:
                dump(self.setu_config, f, indent=4, ensure_ascii=False)
