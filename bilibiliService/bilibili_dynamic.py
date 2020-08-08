import requests, json, os, re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"
}


class BilibiliDynamic:
    def __init__(self, uuid):
        self.uid = uuid
        self.baseUrl = 'https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history?visitor_uid=0&host_uid=%s&offset_dynamic_id=0' % uuid
        self.contentDict = self._getDict()
        self.lastContent = self._getLastContent()
        self.dynamicPictures = self._getDynamicPictures()

    def _getDict(self) -> dict:
        try:
            page = requests.get(self.baseUrl, headers=headers).content.decode('utf-8')
        except Exception as e:
            print('Error occurred when getting dynamic %s' % e)
            return {'-1': ''}

        json_data = json.loads(page)
        if len(json_data['data']) == 0 or json_data['data']['has_more'] == 0:
            return {'-1': ''}

        return json.loads(json_data['data']['cards'][0]['card'])

    def _getLastContent(self):
        response = ''

        if '-1' in self.contentDict:
            response += 'emmmm这个uid为%d的人好像没有发布任何动态呢' % self.uid

        elif 'videos' in self.contentDict and self.contentDict['videos'] >= 1:
            response += '发布了一个视频，标题为：%s' % self.contentDict['title']

        elif 'intro' in self.contentDict and len(self.contentDict['intro']) > 0:
            response += '发布了一个音乐作品：标题为:%s' % self.contentDict['title']

        elif 'sketch' in self.contentDict and len(self.contentDict['sketch']) != 0:
            response += '发布了一个企划，标题为:%s' % self.contentDict['sketch']['title']

        elif 'content' in self.contentDict['item']:
            content = self.contentDict['item']['content']
            response += content
            originContent = self._getOriginDict()
            if originContent != '':
                if 'item' in originContent and 'description' in originContent['item']:
                    response += '\n转发的原文：\n' + originContent['item']['description']
                elif 'title' in originContent:
                    response += '\n转发的视频标题：\n' + originContent['title']
                else:
                    response += '\n转发的原文：\n' + originContent['item']['content']

        else:
            if 'description' in self.contentDict['item']:
                response += self.contentDict['item']['description']
            else:
                response += self.contentDict['item']['content']

        if response == '':
            response += 'emmmm这个uid为%d的人好像没有发布任何动态呢' % self.uid
        return response

    def _getDynamicPictures(self):
        img_path = []
        try:
            pictures = self.contentDict['item']['pictures']
        except KeyError:
            return img_path

        for picture in pictures:
            img_src = picture['img_src']
            filepath = 'E:/bilibiliPic/'
            try:
                response = requests.get(img_src, headers=headers, timeout=15)
                pictureName = re.findall(r'\w+\.[jpgnif]{3}', img_src)[0]
                response.raise_for_status()
                fileName = filepath + pictureName
                if not os.path.exists(fileName):
                    with open(fileName, 'wb') as f:
                        f.write(response.content)

                img_path.append(fileName)

            except Exception as e:
                print('Error occurred when getting picture %s' % e)

        return img_path

    def _getOriginDict(self) -> dict:
        try:
            return json.loads(self.contentDict['origin'])
        except KeyError:
            return {}

    def getLastContent(self):
        if not self.dynamicPictures:
            return self.lastContent

        for elements in self.dynamicPictures:
            self.lastContent += '[CQ:image,file=file:///%s]' % elements

        return self.lastContent