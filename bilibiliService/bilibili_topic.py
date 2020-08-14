import requests, re, json, os


class BilibiliTopic:
    def __init__(self, topic):
        self.base_url = 'https://api.vc.bilibili.com/topic_svr/v1/topic_svr/fetch_dynamics?topic_name=%s&sortby=2' % topic
        self.content_dict = self._get_content()
        self.if_pic = self.check_if_pic()
        self.pic_list = self._get_pic_list()

    def _get_content(self):
        response = requests.get(self.base_url, timeout=10)
        content_dict = response.json()
        if content_dict['code'] != 0:
            return {'-1': 'Invalid Content'}

        return json.loads(content_dict['data']['cards'][0]['card'])

    def check_if_pic(self):
        if 'item' in self.content_dict and 'pictures' in self.content_dict['item']:
            if 'pictures' in self.content_dict['item']:
                inner_list: dict = self.content_dict['item']
                if inner_list['pictures']:
                    return True

        return False

    def _get_pic_list(self):
        img_list = []
        if self.if_pic:
            filepath = f'{os.getcwd()}/data/bilibiliPic/'
            json_data_item: dict = self.content_dict['item']
            json_data = json_data_item['pictures']
            for pic in json_data:
                try:
                    img_src = pic['img_src']
                    picture_name = re.findall(r'\w+\.[jpgnif]{3}', img_src)[0]
                    path = filepath + picture_name

                    resp = requests.get(img_src, timeout=10)
                    resp.raise_for_status()

                    if not os.path.exists(path):
                        with open(path, 'wb') as f:
                            f.write(resp.content)

                    img_list.append(path)

                except Exception as e:
                    print('Error when getting picture: %s' % e)

        return img_list

    def get_last_content(self):
        response = ''
        try:
            upload_time_inner: dict = self.content_dict['item']
            upload_time = upload_time_inner['upload_time']
        except KeyError:
            return response

        import time
        current_time = time.time()
        if current_time - upload_time < 100:
            response += self.get_content()

        return response

    def get_content(self):
        response = ''
        if '-1' in self.content_dict:
            return response

        if 'user' in self.content_dict:
            user_dict: dict = self.content_dict['user']
            user = user_dict['name']
        elif 'author' in self.content_dict:
            user_dict = self.content_dict['author']
            user = user_dict['name']
        else:
            user_dict = self.content_dict['owner']
            user = user_dict['name']

        response += '发布者：%s\n' % user

        if 'item' in self.content_dict:
            item_dict: dict = self.content_dict['item']
            if 'description' in self.content_dict['item']:
                response += item_dict['description']

            elif 'content' in self.content_dict['item']:
                response += item_dict['content']

            if self.if_pic:
                for elements in self.pic_list:
                    response += '[CQ:image,file=file://%s] ' % elements

        elif 'videos' in self.content_dict and self.content_dict['videos'] >= 1:
            response += '发布了一个视频，标题为：%s' % self.content_dict['title']

        elif 'intro' in self.content_dict and len(self.content_dict['intro']) > 0:
            response += '发布了一个音乐作品：标题为:%s' % self.content_dict['title']

        elif 'sketch' in self.content_dict and len(self.content_dict['sketch']) != 0:
            sketch_dict: dict = self.content_dict['sketch']
            response += '发布了一个企划，标题为:%s' % sketch_dict['title']

        elif 'title' in self.content_dict:
            response += '发布了一个资源，标题为%s' % self.content_dict['title']

        return response
