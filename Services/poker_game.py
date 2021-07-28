import random
import time


class Pokergame:
    def __init__(self):
        self.playerDict = {}
        self.playerGroupList = {}
        self.pokerList = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 21]
        self.faceList = ["梅花", "方片", "红心", "黑桃"]

    def get_random_card(self, user_id, group_id, rigged=-1) -> (str, str):
        time_now = time.time_ns()
        random.seed(time_now)
        time_now = str(time_now)
        point = random.choice(self.pokerList)
        face = random.choice(self.faceList)
        if rigged > 0:
            point = 21

        if group_id not in self.playerDict:
            self.playerDict[group_id] = {}

        if group_id not in self.playerGroupList:
            self.playerGroupList[group_id] = []

        if user_id not in self.playerDict[group_id]:
            self.playerGroupList[group_id].append(point)

        self.playerDict[group_id][user_id] = point

        if point == 21:
            return face + "A", time_now

        if point == 11:
            return face + "J", time_now

        if point == 12:
            return face + "Q", time_now

        if point == 13:
            return face + "K", time_now

        return face + str(point), time_now

    def compare_two(self, group_id):
        if len(self.playerDict[group_id]) < 2:
            return False, -1

        if self.playerGroupList[group_id][0] > self.playerGroupList[group_id][1]:
            return True, list(self.playerDict[group_id])[0]

        elif self.playerGroupList[group_id][0] < self.playerGroupList[group_id][1]:
            return True, list(self.playerDict[group_id])[1]

        return False, -2

    def clear_result(self, group_id):
        self.playerGroupList[group_id] = []
        self.playerDict[group_id] = {}
