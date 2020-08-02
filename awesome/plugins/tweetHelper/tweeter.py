import twitter, config, logging, re, requests, os, time

try:
    api = twitter.Api(consumer_key=config.consumerKey,
                      consumer_secret=config.consumerSecret,
                      access_token_key=config.accessToken,
                      access_token_secret=config.accessSecret)

except Exception as e:
    print("getTweet init failed %s" % e)

class tweeter:
    def __init__(self):
        self.path = 'E:/twitterPic/'

        self.tweet_list_init = {}
        self.tweet_new_temp = {}
        self.INFO_NOT_AVAILABLE = '请检查推特用户名， 该输入应该是@后面的那一部分'
        self.screen_name_dict = {
           'shiroganenoel' : '白銀',
           'komori_chiyu' : '古守',
           'nakiriayame' : '百鬼',
           'nana_kaguraaa' : '狗妈',
           'Vtuber_Moe' : '萌惠',
           'ui_shig' : '时雨妈',
           'msbsqn' : 'むすぶ',
           'norioo_' : '犬山哥',
           'sifiresirer' : '茜菲'
        }
        self.ch_name_to_group_id = {
            '白銀': [794877920, 539199998],
            '古守': [526238439],
            '百鬼': [693010774],
            '狗妈': [463769153, 756540140],
            '萌惠': [940461555],
            '时雨妈': [599748718],
            'むすぶ': [462819337],
            '犬山哥': [915383361],
            '茜菲': [101790160]
        }

        for screen_name in self.screen_name_dict:
            resp_text = self.get_time_line_from_screen_name(screen_name=screen_name)
            self.tweet_list_init[self.screen_name_dict[screen_name]] = resp_text

        self.index = 0

    def get_group_id_dict(self):
        return self.ch_name_to_group_id

    def get_new_tweet_by_index(self, index):
        return self.tweet_list_init[index]

    def get_tweet_list(self):
        return self.tweet_list_init

    def get_every_new_tweet_in_list(self):
        for screen_name in self.screen_name_dict:
            try:
                new_tweet = self.get_time_line_from_screen_name(screen_name=screen_name)
                self.tweet_new_temp[self.screen_name_dict[screen_name]] = new_tweet

            except Exception as err:
                logging.warning(f'error occurred while getting new tweet for screen_name = {screen_name}\n'
                                f'{err}')

        return self.tweet_new_temp

    def set_new_tweet_by_ch_name(self, ch_name, tweet):
        self.tweet_list_init[ch_name] = tweet

    def get_new_tweet_by_ch_name(self, name):
        if name in self.screen_name_dict.values():
            return self.tweet_new_temp[name]

        return ''

    def get_time_line_from_screen_name(self, screen_name, fetch_count=1):
        if re.match('[A-Za-z0-9_]+$', screen_name):
            return self.matched_screen_name(screen_name, fetch_count)

        else:
            search_term = screen_name
            name_list = api.GetUsersSearch(term=screen_name)
            if name_list:
                screen_name = name_list[0].screen_name
                tweet = f'{search_term}发推说：\n' + \
                        self.matched_screen_name(screen_name, fetch_count)

                return tweet

            else:
                return self.INFO_NOT_AVAILABLE

    def matched_screen_name(self, screen_name, fetch_count):
        response_main = []
        resp_text = ''
        fetch_count = int(fetch_count)
        try:
            response_main = api.GetUserTimeline(screen_name=screen_name)
        except Exception as err:
            logging.warning('连接出错！%s' % err)
            resp_text += self.INFO_NOT_AVAILABLE

        if fetch_count >= len(response_main):
            return self.INFO_NOT_AVAILABLE

        for i in range(fetch_count):
            response = response_main[i]
            if response.full_text is None:
                response_text = response.text
            else:
                response_text = response.full_text

            if response_text[0] == '@' and fetch_count != 1:
                continue

            resp_text += response_text

            resp_user = re.findall(r'^@(.*?)\s', resp_text)
            if resp_user:
                try:
                    reply_content = api.GetStatus(status_id=response.in_reply_to_status_id)
                    resp_text += '\n-----回复内容正文：-----\n' + reply_content.text
                except Exception as err:
                    logging.warning('Not authorized reply %s' % err)

            if response.media is not None:
                media = response.media
                for idx in range(0, len(media)):
                    img_src = media[idx].media_url
                    if img_src:
                        pic_name = re.findall(r'[A-Za-z0-9\-_]+\.[jpgnif]{3}', img_src)[0]
                        file_name = self.path + pic_name
                        if not os.path.exists(file_name):
                            try:
                                resp = requests.get(img_src, timeout=10)
                                with open(file_name, 'wb') as f:
                                    f.write(resp.content)

                            except Exception as err:
                                logging.warning('Something went wrong when getting twitter picture. %s' % err)

                        resp_text += '\n[CQ:image,file=file:///%s]' % file_name

            resp_text += '\n====================\n' if fetch_count != 1 else ''

        return resp_text


'''
class bilibliHelper:
    def __init__(self):
        self.uidList = {
            '鹿乃' : 316381099,
            '野野宫' : 441403698,
            '花丸' : 441381282,
            '小东' : 441382432
        }

        self.dynamicListInit = []
        self.dynamicList = []
        for key, elements in self.uidList.items():
            aapi = bilibiliDynamic.BilibiliDynamic(uuid=elements)
            self.dynamicListInit.append(aapi.getLastContent())

    def getInitDynamicList(self):
        return self.dynamicListInit

    def getNewDynamicList(self):
        index = 0
        self.dynamicList.clear()
        for key, elements in self.uidList.items():
            aapi = bilibiliDynamic.BilibiliDynamic(uuid=elements)
            newContent = aapi.getLastContent()
            if newContent == 'emmmm这个uid为%d的人好像没有发布任何动态呢' % elements:
                self.dynamicList.append(self.dynamicListInit[index])
            else:
                self.dynamicList.append(newContent)
            index += 1

        return self.dynamicList
'''