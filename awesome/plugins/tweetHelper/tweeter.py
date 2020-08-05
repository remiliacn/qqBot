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


def get_info_in_json(json_result, ch_name: str) -> str:
    live_title = json_result['data']['title']
    live_desc: str = json_result['data']['description']
    live_desc = re.sub('<.*?>', '', live_desc)
    live_cover = json_result['data']['user_cover']

    image = requests.get(live_cover, timeout=10)
    image.raise_for_status()

    file_name = live_cover.split('/')[-1]
    path = f'E:/bilibiliPic/{file_name}'
    with open(path, 'wb') as file:
        file.write(image.content)

    return f'{ch_name}开播啦！\n' \
           f'直播间标题：{live_title}\n' \
           f'直播间描述：{live_desc}\n' \
           f'封面\n' \
           f'[CQ:image,file=file:///{file_name}]'


class tweeter:
    def __init__(self):
        self.path = 'E:/twitterPic/'
        self.config = 'config/tweet.json'
        self.INFO_NOT_AVAILABLE = '请检查推特用户名， 该输入应该是@后面的那一部分'

        self.tweet_list_init = {}
        self.tweet_config = self._get_tweet_config()

        self.live_stat = {}
        self.live_stat = self.get_live_room_info()

        for ch_name in self.tweet_config:
            if self.tweet_config[ch_name]['enabled']:
                if self.tweet_config[ch_name]['screen_name'] == '_':
                    continue

                resp_text = self.get_time_line_from_screen_name(screen_name=self.tweet_config[ch_name]['screen_name'])
                self.tweet_list_init[ch_name] = resp_text

    def get_tweet_config(self) -> dict:
        return self.tweet_config

    def add_to_config(self, args : list, group_id) -> str:
        ch_name = args[0]
        screen_name = args[1]
        bilibili = args[2]
        enabled = args[3].upper()

        if ch_name not in self.tweet_config:
            self.tweet_config[ch_name] = {
                'screen_name' : screen_name,
                'group' : [group_id],
                'enabled' : True,
                'bilibili' : bilibili
            }

        else:
            group: list = self.tweet_config[ch_name]['group']
            screen_name = self.tweet_config[ch_name]['screen_name'] if screen_name == '_' else screen_name
            bilibili = self.tweet_config[ch_name]['bilibili'] if bilibili == '_' else bilibili
            self.tweet_config[ch_name] = {
                'screen_name': screen_name,
                'group': group.append(group_id) if group_id not in group else group,
                'enabled': True if enabled == 'Y' else False,
                'bilibili': bilibili
            }

        self.save_config()
        return '已完成更改！'

    def save_config(self):
        with open(self.config, 'w+', encoding='utf8') as file:
            json.dump(self.tweet_config, file, indent=4)

    def get_live_room_info(self):
        live_temp_dict = {}
        for ch_name in self.tweet_config:
            if not 'bilibili' in self.tweet_config[ch_name]:
                continue

            if not self.tweet_config[ch_name]['enabled']:
                continue

            if self.tweet_config[ch_name]['bilibili'] == '_':
                continue

            live_room_cid = self.tweet_config[ch_name]['bilibili']
            api_url = f'https://api.live.bilibili.com/room/v1/Room/get_info?room_id={live_room_cid}'
            page = requests.get(api_url, timeout=10)
            if not page.status_code == 200:
                logging.warning(f'API connection failed to bilibili live room update for {ch_name}')
                continue

            json_result = page.json()
            live_stat = json_result['data']['live_status']
            if live_stat == 1:
                if ch_name not in self.live_stat:
                    info = get_info_in_json(json_result, ch_name)
                    live_temp_dict[ch_name] = info
                    self.live_stat = live_temp_dict
            else:
                if ch_name in self.live_stat:
                    del self.live_stat[ch_name]

        return live_temp_dict

    async def check_update(self):
        temp_dict = {}
        diff_dict = {}
        print(f'Original: {self.tweet_list_init}')
        for ch_name in self.tweet_config:
            if self.tweet_config[ch_name]['enabled']:
                if self.tweet_config[ch_name]['screen_name'] == '_':
                    continue

                try:
                    resp_text = self.get_time_line_from_screen_name(screen_name=self.tweet_config[ch_name]['screen_name'])
                except Exception as err:
                    logging.warning(err)
                    resp_text = ''

                temp_dict[ch_name] = resp_text

        for element in temp_dict:
            if element not in self.tweet_list_init or \
            (self.tweet_list_init[element] != temp_dict[element]):

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
