from Services.util.common_util import HttpxHelperClient


class Bilibilistats:
    def __init__(self, uuid):
        self.base_url = f'https://api.bilibili.com/x/relation/stat?vmid={uuid}'
        self.data_url = 'https://api.bilibili.com/x/space/acc/info?mid={uuid'
        self.uuid = uuid
        self.client = HttpxHelperClient()

        self.stats_dict = None

    async def _get_stats_dict(self):
        page = await self.client.get(self.base_url)
        json_data = page.json()
        if 'code' in json_data and json_data['code'] == -400 or json_data['code'] == -404:
            return {'-1': '查询内容不存在'}

        return json_data['data']

    async def get_user_name(self):
        page = await self.client.get(self.data_url)
        json_data = page.json()
        if 'code' in 'json_data' and json_data['code'] == -404 or json_data['code'] == -400:
            return ''

        return json_data['data']['name']

    async def get_following(self):
        if self.stats_dict is None:
            await self._get_stats_dict()

        if '-1' in self.stats_dict:
            return '信息不可用'

        return str(self.stats_dict['following'])

    async def get_follower(self):
        if self.stats_dict is None:
            await self._get_stats_dict()

        if '-1' in self.stats_dict:
            return '信息不可用'
        return str(self.stats_dict['follower'])

    async def get_result(self):
        nick_name = await self.get_user_name()
        if nick_name == '':
            return '未查到UUID为%s的用户信息' % self.uuid

        return f'UID为{self.uuid}的b站名为{await self.get_user_name()}的用户数据如下：\n' \
               f'关注者：{await self.get_follower()}人\n' \
               f'正在关注：{await self.get_following()}人'
