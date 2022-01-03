from json import loads
from os import getcwd
from random import randint, choice
from typing import List

from remilia_adventure_util.utils import get_data, get_data_nested_int


class Talent:
    def __init__(self, data: dict, talent_id: str):
        self.data = data

        self.talent_id = talent_id
        self.title = get_data(data, 'title')
        self.status = get_data(data, 'status')
        self.description = get_data(data, 'description')

        self.preq_health = get_data_nested_int(data, ['preq', 'health'])
        self.preq_death = get_data_nested_int(data, ['preq', 'death'])
        self.preq_attack = get_data_nested_int(data, ['preq', 'attack'])
        self.preq_luck = get_data_nested_int(data, ['preq', 'luck'])
        self.preq_playtime = get_data_nested_int(data, ['preq', 'playtime'])

        # if has activate, set/change will be activated by condition inside, not added when the game started.
        """
        activater is a list of list where:
            condition: ==, >=, <=, %
            title: talent title
            decider: decider for changes to be applied
            result: list of dict where:
                action: set/change/random
                prop: what prop to use in set/change
                
                when action not set and change, split action with '[!]' to get first execution command, and set/change:
                    choose random key in prop to execute.
        """
        self.activate_need: list = get_data(data, 'activate')

        self.change_health = get_data_nested_int(data, ['change', 'health'])
        self.change_attack = get_data_nested_int(data, ['change', 'attack'])
        self.change_luck = get_data_nested_int(data, ['change', 'luck'])
        self.change_life = get_data_nested_int(data, ['change', 'life'])

        self.set_health = get_data_nested_int(data, ['set', 'health'], True)
        self.set_attack = get_data_nested_int(data, ['set', 'attack'], True)
        self.set_luck = get_data_nested_int(data, ['set', 'luck'], True)
        self.set_life = get_data_nested_int(data, ['set', 'life'], True)
        self.set_step = get_data_nested_int(data, ['set', 'step'], True)

        self.exclude_talent = get_data(data, 'exclude_talent')
        self.need_achievement = get_data(data, 'need_achievement')
        self.unlock_achievement = get_data(data, 'achievement')
        self.item_add = get_data(data, 'items')
        self.event_to_add = get_data(data, 'add_event')


class Talents:
    def __init__(self, is_debug=False):
        self.is_debug = is_debug
        self.talent_full_list = {}

        self.normal_talent = []
        self.rare_talent = []
        self.legendar_talent = []

        self._read_talent_data_file()

    def _read_talent_data_file(self):
        if self.is_debug:
            with open('data/adventure_data/talents.json', 'r', encoding='utf-8-sig') as file:
                json_data = loads(file.read())

        else:
            with open(f'{getcwd()}/data/adventure_data/talents.json', 'r', encoding='utf-8-sig') as file:
                json_data = loads(file.read())

        if json_data:
            json_data = json_data['talents']
            self.talent_full_list = json_data

            for element in json_data:
                if json_data[element]['grade'] == 0:
                    self.normal_talent.append(Talent(json_data[element], element))
                elif json_data[element]['grade'] == 1:
                    self.rare_talent.append(Talent(json_data[element], element))
                else:
                    self.legendar_talent.append(Talent(json_data[element], element))

    def get_talents_by_id(self, talent_id: str) -> Talent:
        return Talent(self.talent_full_list[talent_id], talent_id) if talent_id in self.talent_full_list else None

    def get_random_talent(self) -> Talent:
        rand_num = randint(0, 100)

        if rand_num < 50:
            talent = choice(self.normal_talent)
        elif rand_num < 95:
            talent = choice(self.rare_talent)
        else:
            talent = choice(self.legendar_talent)

        return talent

    @staticmethod
    def get_talent_message_by_list(random_talent: List[Talent]):
        response = ''
        for talent in random_talent:
            response += f'{talent.talent_id}: {talent.title}【{talent.description}】\n'

        return response
