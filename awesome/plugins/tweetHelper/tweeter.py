import config
import json
import logging
import os
import re
import requests
import twitter

try:
    api = twitter.Api(consumer_key=config.consumer_key,
                      consumer_secret=config.consumer_secret,
                      access_token_key=config.access_token,
                      access_token_secret=config.access_secret, tweet_mode='extended')

except Exception as e:
    print("getTweet init failed %s" % e)

class tweeter:
    def __init__(self):
        self.path = 'E:/twitterPic/'
        self.config = 'config/tweet.json'

        self.tweet_list_init = {}
        self.INFO_NOT_AVAILABLE = '请检查推特用户名， 该输入应该是@后面的那一部分'

        self.tweet_config = self._get_tweet_config()

        for ch_name in self.tweet_config:
            if self.tweet_config[ch_name]['enabled']:
                resp_text = self.get_time_line_from_screen_name(screen_name=self.tweet_config[ch_name]['screen_name'])
                self.tweet_list_init[ch_name] = resp_text

    def get_tweet_config(self) -> dict:
        return self.tweet_config

    async def check_update(self):
        temp_dict = {}
        diff_dict = {}
        print(f'Original: {self.tweet_list_init}')
        for ch_name in self.tweet_config:
            if self.tweet_config[ch_name]['enabled']:
                try:
                    resp_text = self.get_time_line_from_screen_name(screen_name=self.tweet_config[ch_name]['screen_name'])
                except Exception as err:
                    logging.warning(err)
                    resp_text = ''

                temp_dict[ch_name] = resp_text

        for element in temp_dict:
            if self.tweet_list_init[element] != temp_dict[element]:
                if not (temp_dict[element] == '' or temp_dict[element] == '转发动态'):
                    diff_dict[element] = temp_dict[element]

        self.tweet_list_init = temp_dict
        print(f'Changed: {self.tweet_list_init}')
        return diff_dict

    def _get_tweet_config(self) -> dict:
        if not os.path.exists(self.config):
            with open(self.config, 'w+') as file:
                json.dump({}, file, indent=4)

            return {}

        else:
            with open(self.config, 'r', encoding='utf8') as file:
                return json.loads(file.read())

    def get_time_line_from_screen_name(self, screen_name, fetch_count=1):
        if re.match('[A-Za-z0-9_]+$', screen_name):
            return self.fetch_user_screen_name(screen_name, fetch_count)

        else:
            search_term = screen_name
            name_list = api.GetUsersSearch(term=screen_name)
            if name_list:
                screen_name = name_list[0].screen_name
                tweet = f'{search_term}发推说：\n' + \
                        self.fetch_user_screen_name(screen_name, fetch_count)

                return tweet

            else:
                return self.INFO_NOT_AVAILABLE

    def fetch_user_screen_name(self, screen_name, fetch_count):
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
                    resp_text += '\n-----回复内容正文：-----\n' + reply_content.full_text \
                        if reply_content.full_text is not None else reply_content.text

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
