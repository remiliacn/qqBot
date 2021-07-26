import json

import requests


class Bilibilistats:
    def __init__(self, uuid):
        self.base_url = 'https://api.bilibili.com/x/relation/stat?vmid=%s' % uuid
        self.data_url = 'https://api.bilibili.com/x/space/acc/info?mid=%s' % uuid
        self.uuid = uuid
        self.stats_dict = self._get_stats_dict()

    def _get_stats_dict(self):
        page = requests.get(self.base_url).text
        json_data = json.loads(page)
        if 'code' in json_data and json_data['code'] == -400 or json_data['code'] == -404:
            return {'-1': '查询内容不存在'}

        return json_data['data']

    def get_user_name(self):
        page = requests.get(self.data_url).text
        json_data = json.loads(page)
        if 'code' in 'json_data' and json_data['code'] == -404 or json_data['code'] == -400:
            return ''

        return json_data['data']['name']

    def get_following(self):
        if '-1' in self.stats_dict:
            return '信息不可用'

        return str(self.stats_dict['following'])

    def get_follower(self):
        if '-1' in self.stats_dict:
            return '信息不可用'
        return str(self.stats_dict['follower'])

    def __str__(self):
        nick_name = self.get_user_name()
        if nick_name == '':
            return '未查到UUID为%s的用户信息' % self.uuid

        return 'UID为%s的b站名为%s的用户数据如下：\n' \
               '关注者：%s人\n' \
               '正在关注：%s人' % (self.uuid, self.get_user_name(), self.get_follower(), self.get_following())
