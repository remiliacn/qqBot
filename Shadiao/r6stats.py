import requests, json

statsUrl = 'https://r6tab.com/api/search.php?platform=uplay&search='
INFO_NOT_AVAILABLE = "信息暂不可用。"
USER_NOT_FOUND = "用户不存在。"

headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36",
}
operatorsJson = 'https://game-rainbow6.ubi.com/assets/data/operators.24b865895.json'

class r6Stats:
    def __init__(self, userName):
        global statsUrl
        self.userName = userName
        self.baseUrl = statsUrl + userName
        self.p_id = self.getPID()
        self.detailJson = self.getPlayerDetailedData()

    def getPID(self):
        global headers, INFO_NOT_AVAILABLE
        p_id = USER_NOT_FOUND
        try:
            page = requests.get(self.baseUrl, headers=headers, timeout=10)
        except Exception as e:
            print("error occurred: \n%s" % e)
            return p_id

        json_data = json.loads(page.text)
        if json_data['totalresults'] >= 1:
            p_id = json_data['results'][0]['p_id']

        return p_id

    def getPlayerDetailedData(self):
        global headers
        json_data = None
        if self.p_id != USER_NOT_FOUND:
            try:
                page = requests.get('https://r6tab.com/api/player.php?p_id=%s' % self.p_id, headers=headers, timeout=10)
            except Exception as e:
                print("Error occurred in getPlayerDetailedData, Error: %s" % e)
                return json_data

            json_data = json.loads(page.text)

            if json_data['playerfound']:
                return json_data

        return None

    def getFavoredOperator(self):
        global INFO_NOT_AVAILABLE
        global operatorsJson
        json_data = self.detailJson
        try:
            page = requests.get(operatorsJson, timeout=10)
        except Exception as e:
            print("Error occurred in getPlayerDetailedData, Error: %s" % e)
            return INFO_NOT_AVAILABLE

        json_Operator = json.loads(page.text)

        maxHour = 0
        key = INFO_NOT_AVAILABLE
        if json_data is not None:
            json_data = json_data['operators']
            json_stats = json.loads(json_data)[4]
            for keys, playingTime in json_stats.items():
                if playingTime > maxHour:
                    maxHour = playingTime
                    key = keys

        if key is not None:
            for data in json_Operator:
                if json_Operator[data]['index'] == key:
                    key = data
                    break

        return key

    def getMMR(self):
        global INFO_NOT_AVAILABLE
        na_mmr = INFO_NOT_AVAILABLE
        eu_mmr = INFO_NOT_AVAILABLE
        as_mmr = INFO_NOT_AVAILABLE

        if self.detailJson is not None:
            json_stats = self.detailJson['seasonal']
            na_mmr = json_stats['current_NA_mmr']
            eu_mmr = json_stats['current_EU_mmr']
            as_mmr = json_stats['current_AS_mmr']

        return "\n北美MMR：%d\n欧服MMR：%d\n亚服MMR：%d" % (na_mmr, eu_mmr, as_mmr)

    def getDetailedStats(self):
        global USER_NOT_FOUND
        stats = USER_NOT_FOUND
        if self.detailJson is not None:
            json_stats = self.detailJson['data']
            rankKill = json_stats[2]
            rankTotal = json_stats[4]
            casualKill = json_stats[7]
            casualTotal = json_stats[9]

            if rankKill == 0:
                rankKill = 1

            if rankTotal == 0:
                rankTotal = 1

            if casualKill == 0:
                casualKill = 1

            if casualTotal == 0:
                casualTotal = 1

            stats = "以下是关于玩家%s的R6战绩：\n" \
                     "排位kda： %.1f\n" \
                     "排位胜率：%.1f\n" \
                     "休闲kda：%.1f\n" \
                     "休闲胜率：%.1f\n" \
                     "常用干员：%s\n" \
                     "\n排位分信息：%s" % (self.userName,
                                      json_stats[1] / rankKill,
                                      json_stats[3] / rankTotal,
                                      json_stats[6] / casualKill,
                                      json_stats[8] / casualTotal,
                                      self.getFavoredOperator(),
                                      self.getMMR())

        return stats