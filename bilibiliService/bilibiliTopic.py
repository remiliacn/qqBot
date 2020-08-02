import requests, re, json, os


class Bilibilitopic:
    def __init__(self, topic):
        self.baseUrl = 'https://api.vc.bilibili.com/topic_svr/v1/topic_svr/fetch_dynamics?topic_name=%s&sortby=2' % topic
        self.contentList = self._getContent()
        self.ifPic = self.checkIfPic()
        self.picList = self._getPicList()

    def _getContent(self):
        response = requests.get(self.baseUrl, timeout=10)
        contentDict = response.json()
        if contentDict['code'] != 0:
            return {'-1': 'Invalid Content'}

        return json.loads(contentDict['data']['cards'][0]['card'])

    def checkIfPic(self):
        if 'item' in self.contentList and 'pictures' in self.contentList['item']:
            if len(self.contentList['item']['pictures']) >= 1:
                return True

        return False

    def _getPicList(self):
        imgList = []
        if self.ifPic:
            filepath = 'E:/bTopic/'
            json_data = self.contentList['item']['pictures']
            for pic in json_data:
                try:
                    img_src = pic['img_src']
                    pictureName = re.findall(r'\w+\.[jpgnif]{3}', img_src)[0]
                    path = filepath + pictureName

                    resp = requests.get(img_src, timeout=10)
                    resp.raise_for_status()

                    if not os.path.exists(path):
                        with open(path, 'wb') as f:
                            f.write(resp.content)

                    imgList.append(path)

                except Exception as e:
                    print('Error when getting picture: %s' % e)

        return imgList

    def getLastContent(self):
        response = ''
        try:
            uploadTime = self.contentList['item']['upload_time']
        except KeyError:
            return response

        import time
        currentTime = time.time()
        if currentTime - uploadTime < 100:
            response += self.get_content()

        return response

    def get_content(self):
        response = ''
        if '-1' in self.contentList:
            return response

        if 'user' in self.contentList:
            user = self.contentList['user']['name']
        elif 'author' in self.contentList:
            user = self.contentList['author']['name']
        else:
            user = self.contentList['owner']['name']

        response += '发布者：%s\n' % user

        if 'item' in self.contentList:
            if 'description' in self.contentList['item']:
                response += self.contentList['item']['description']

            elif 'content' in self.contentList['item']:
                response += self.contentList['item']['content']

            if self.ifPic:
                for elements in self.picList:
                    response += '[CQ:image,file=file://%s] ' % elements

        elif 'videos' in self.contentList and self.contentList['videos'] >= 1:
            response += '发布了一个视频，标题为：%s' % self.contentList['title']

        elif 'intro' in self.contentList and len(self.contentList['intro']) > 0:
            response += '发布了一个音乐作品：标题为:%s' % self.contentList['title']

        elif 'sketch' in self.contentList and len(self.contentList['sketch']) != 0:
            response += '发布了一个企划，标题为:%s' % self.contentList['sketch']['title']

        elif 'title' in self.contentList:
            response += '发布了一个资源，标题为%s' % self.contentList['title']

        return response
