import random, time

class Russianroulette:
    def __init__(self):
        self.game_dict = {

        }
        self.notified = False

    def changeNotification(self, stats):
        self.notified = stats

    def ifNotified(self):
        return self.notified

    def setUpDictByGroup(self, user_id):
        self.game_dict[user_id] = {
            "theLowerBound": 1,
            "theHighestBound": 6,
            "theLastDeath": 1,
            "playerDict" : {}
        }

    def add_player_in(self, group_id, user_id):
        self.game_dict[group_id]["playerDict"][user_id] = 1

    def add_player_play_time(self, group_id, user_id):
        self.game_dict[group_id]["playerDict"][user_id] += 1

    def get_play_time_with_user_id(self, group_id, user_id):
        return self.game_dict[group_id]["playerDict"][user_id]

    def pullTrigger(self, group_id):
        self.game_dict[group_id]["theLowerBound"] += 1
        self.game_dict[group_id]["theLastDeath"] += 1

    def getRestBullets(self, group_id):
        return self.game_dict[group_id]["theHighestBound"] - self.game_dict[group_id]["theLowerBound"]

    def get_death(self, group_id):
        lastDeath = self.game_dict[group_id]["theLastDeath"]
        self.game_dict[group_id]["theLastDeath"] = 1
        return lastDeath

    def get_result(self, group_id):
        random.seed(time.time_ns())
        draw = random.randint(self.game_dict[group_id]["theLowerBound"], self.game_dict[group_id]["theHighestBound"])
        if draw >= 6:
            self.game_dict[group_id]["theLowerBound"] = 1
            return True

        self.pullTrigger(group_id)
        return False