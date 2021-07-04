import random
import time


class Pokergame:
    def __init__(self):
        self.playerDict = {}
        self.playerGroupList = {}
        self.pokerList = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 21]
        self.faceList = ["梅花", "方片", "红心", "黑桃"]

    def get_random_card(self, userID, groupID, rigged=-1) -> (str, str):
        timeNow = time.time_ns()
        random.seed(timeNow)
        timeNow = str(timeNow)
        point = random.choice(self.pokerList)
        face = random.choice(self.faceList)
        if rigged > 0:
            point = 21

        if groupID not in self.playerDict:
            self.playerDict[groupID] = {}

        if groupID not in self.playerGroupList:
            self.playerGroupList[groupID] = []

        if userID not in self.playerDict[groupID]:
            self.playerGroupList[groupID].append(point)

        self.playerDict[groupID][userID] = point

        if point == 21:
            return face + "A", timeNow

        if point == 11:
            return face + "J", timeNow

        if point == 12:
            return face + "Q", timeNow

        if point == 13:
            return face + "K", timeNow

        return face + str(point), timeNow

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
