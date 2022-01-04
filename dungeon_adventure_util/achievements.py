import time
from json import loads
from os import getcwd


class Achievements:
    def __init__(self, user_achievement_record=None):
        if user_achievement_record is None:
            self.achievement_dict = self._get_achievement_info()['achievements']
        else:
            self.achievement_dict = user_achievement_record

    @staticmethod
    def _get_achievement_info() -> dict:
        with open(f'{getcwd()}/data/adventure_data/achievements.json', encoding='utf-8-sig') as file:
            json_data = loads(file.read())

        return json_data

    def win_achievement(self, ach_id):
        ach_id = str(ach_id)
        if ach_id not in self.achievement_dict:
            return False

        if 'unlock_time' in self.achievement_dict[ach_id]:
            return False

        self.achievement_dict[ach_id]['unlock_time'] = int(time.time())
        return self.achievement_dict[ach_id]
