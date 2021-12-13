import random
import time


class Russianroulette:
    def __init__(self, bullet_in_gun=6):
        self.game_dict = {

        }
        self.notified = False
        self.bullet_in_gun = bullet_in_gun

    def change_notification(self, stats):
        self.notified = stats

    def modify_bullets_in_gun(self, count: int):
        self.bullet_in_gun = count

    def if_notified(self):
        return self.notified

    def set_up_dict_by_group(self, user_id):
        self.game_dict[user_id] = {
            "theLowerBound": 1,
            "theHighestBound": self.bullet_in_gun,
            "theLastDeath": 1,
            "playerDict": {}
        }

    def add_player_in(self, group_id, user_id):
        self.game_dict[group_id]["playerDict"][user_id] = 1

    def add_player_play_time(self, group_id, user_id):
        self.game_dict[group_id]["playerDict"][user_id] += 1

    def get_play_time_with_user_id(self, group_id, user_id):
        return self.game_dict[group_id]["playerDict"][user_id]

    def pull_trigger(self, group_id):
        self.game_dict[group_id]["theLowerBound"] += 1
        self.game_dict[group_id]["theLastDeath"] += 1

    def get_rest_bullets(self, group_id):
        return self.game_dict[group_id]["theHighestBound"] - self.game_dict[group_id]["theLowerBound"]

    def reset_gun(self, group_id):
        if group_id not in self.game_dict:
            self.game_dict[group_id] = {}

        if 'playerDict' not in self.game_dict[group_id]:
            self.game_dict[group_id]['playerDict'] = {}

        self.game_dict[group_id]["theLastDeath"] = 1
        self.game_dict[group_id]["theLowerBound"] = 1

    def get_death(self, group_id):
        last_death = self.game_dict[group_id]["theLastDeath"]
        self.reset_gun(group_id)
        return last_death

    def get_result(self, group_id):
        random.seed(time.time_ns())
        draw = random.randint(self.game_dict[group_id]["theLowerBound"], self.game_dict[group_id]["theHighestBound"])
        if draw >= self.bullet_in_gun:
            return True

        self.pull_trigger(group_id)
        return False
