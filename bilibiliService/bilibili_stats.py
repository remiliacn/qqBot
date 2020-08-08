import requests, json

class bilibiliStats:
    def __init__(self, uuid):
        self.baseUrl = 'https://api.bilibili.com/x/relation/stat?vmid=%s' % uuid
        self.dataUrl = 'https://api.bilibili.com/x/space/acc/info?mid=%s' % uuid
        self.uuid = uuid
        self.statsDict = self._getStatsDict()

    def _getStatsDict(self):
        page = requests.get(self.baseUrl).text
        json_data = json.loads(page)
        if 'code' in json_data and json_data['code'] == -400 or json_data['code'] == -404:
            return {'-1' : '查询内容不存在'}

        return json_data['data']

    def getUserName(self):
        page = requests.get(self.dataUrl).text
        json_data = json.loads(page)
        if 'code' in 'json_data' and json_data['code'] == -404 or json_data['code'] == -400:
            return ''

        return json_data['data']['name']

    def getFollowing(self):
        if '-1' in self.statsDict:
            return '信息不可用'

        return str(self.statsDict['following'])

    def getFollower(self):
        if '-1' in self.statsDict:
            return '信息不可用'
        return str(self.statsDict['follower'])

    def __str__(self):
        nickName = self.getUserName()
        if nickName == '':
            return '未查到UUID为%s的用户信息' % self.uuid

        return 'UID为%s的b站名为%s的用户数据如下：\n' \
               '关注者：%s人\n' \
               '正在关注：%s人'   % (self.uuid, self.getUserName(), self.getFollower(), self.getFollowing())


