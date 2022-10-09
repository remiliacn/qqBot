import json
import re

from Services.util.common_util import HttpxHelperClient


class BilibiliDynamic:
    def __init__(self, uuid):
        self.uid = uuid
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/75.0.3770.142 Safari/537.36"
        }
        self.client = HttpxHelperClient()
        self.base_url = f'https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/' \
                        f'space_history?visitor_uid=0&host_uid={uuid}&offset_dynamic_id=0'

        self.content_dict = None
        self.last_content = None
        self.dynamic_pictures = None

    async def _get_content_dict(self) -> dict:
        try:
            page = await self.client.get(self.base_url)
            page = page.content.decode('utf-8')
        except Exception as e:
            print('Error occurred when getting dynamic %s' % e)
            self.content_dict = {'-1': ''}
            return

        json_data = json.loads(page)
        if len(json_data['data']) == 0 or json_data['data']['has_more'] == 0:
            self.content_dict = {'-1': ''}
        else:
            self.content_dict = json.loads(json_data['data']['cards'][0]['card'])

    async def _get_last_content(self):
        response = ''

        if self.content_dict is None:
            await self._get_content_dict()

        if '-1' in self.content_dict:
            response += f'emmmm这个uid为{self.uid}的人好像没有发布任何动态呢'

        elif 'videos' in self.content_dict and self.content_dict['videos'] >= 1:
            response += '发布了一个视频，标题为：%s' % self.content_dict['title']

        elif 'intro' in self.content_dict and len(self.content_dict['intro']) > 0:
            response += '发布了一个音乐作品：标题为:%s' % self.content_dict['title']

        elif 'sketch' in self.content_dict and len(self.content_dict['sketch']) != 0:
            response += '发布了一个企划，标题为:%s' % self.content_dict['sketch']['title']

        elif 'content' in self.content_dict['item']:
            content = self.content_dict['item']['content']
            response += content
            origin_content = await self._get_origin_dict()
            if origin_content != '':
                if 'item' in origin_content and 'description' in origin_content['item']:
                    response += '\n转发的原文：\n' + origin_content['item']['description']
                elif 'title' in origin_content:
                    response += '\n转发的视频标题：\n' + origin_content['title']
                else:
                    response += '\n转发的原文：\n' + origin_content['item']['content']

        else:
            if 'description' in self.content_dict['item']:
                response += self.content_dict['item']['description']
            else:
                response += self.content_dict['item']['content']

        if response == '':
            response += 'emmmm这个uid为%d的人好像没有发布任何动态呢' % self.uid
        return response

    async def _get_dynamic_pictures(self):
        img_path = []
        try:
            pictures = self.content_dict['item']['pictures']
        except KeyError:
            return img_path

        for picture in pictures:
            img_src = picture['img_src']
            filepath = 'E:/bilibiliPic/'
            try:
                picture_name = re.findall(r'\w+\.[jpgnif]{3}', img_src)[0]
                file_name = filepath + picture_name

                file_name = await self.client.download(img_src, file_name, timeout=15.0)
                img_path.append(file_name)

            except Exception as e:
                print('Error occurred when getting picture %s' % e)

        return img_path

    async def _get_origin_dict(self) -> dict:
        try:
            return json.loads(self.content_dict['origin'])
        except KeyError:
            return {}

    async def get_last_content(self):
        if self.dynamic_pictures is None:
            await self._get_dynamic_pictures()

        if not self.dynamic_pictures:
            if self.last_content is None:
                await self._get_last_content()
            if self.last_content:
                return self.last_content

        for elements in self.dynamic_pictures:
            self.last_content += '[CQ:image,file=file:///%s]' % elements

        return self.last_content
