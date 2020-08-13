import asyncio
import json
import os
import re

import requests
import twitter
from nonebot.log import logger

import config
from bilibiliService import bilibili_live as live_api

try:
    api = twitter.Api(consumer_key=config.consumer_key,
                      consumer_secret=config.consumer_secret,
                      access_token_key=config.access_token,
                      access_token_secret=config.access_secret, tweet_mode='extended')

except Exception as e:
    logger.error("getTweet init failed %s" % e)


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

    def add_to_config(self, args: list, group_id) -> str:
        ch_name = args[0]
        screen_name = args[1]
        bilibili = args[2]
        enabled = args[3].upper()

        if ch_name not in self.tweet_config:
            self.tweet_config[ch_name] = {
                'screen_name': screen_name,
                'group': [group_id],
                'enabled': True,
                'bilibili': bilibili
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

    def remove_from_config(self, key):
        if key in self.tweet_config:
            del self.tweet_config[key]
            del self.tweet_list_init[key]
            if key in self.live_stat:
                del self.live_stat[key]

            self.save_config()
            return True

        return False

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
            live = live_api.BilibiliLive(live_room_cid, ch_name)
            if not live.get_status():
                if ch_name in self.live_stat:
                    del self.live_stat[ch_name]

            else:
                if ch_name not in self.live_stat:
                    live_temp_dict.update(live.get_info())
                    self.live_stat = live_temp_dict

        return live_temp_dict

    async def check_update(self):
        temp_dict = {}
        diff_dict = {}
        logger.info(f'Original: {self.tweet_list_init}')
        tasks = []
        for ch_name in self.tweet_config:
            tasks.append(self._check_update_helper(ch_name))

        results = await asyncio.gather(
            *tasks
        )

        for element in results:
            temp_dict.update(element)

        for element in temp_dict:
            if element not in self.tweet_list_init or \
                    (self.tweet_list_init[element] != temp_dict[element]):

                if not (temp_dict[element] == '' or
                        temp_dict[element] == '转发动态' or
                        temp_dict[element] == self.INFO_NOT_AVAILABLE or 
                        element not in self.tweet_list_init or
                        self.tweet_list_init[element] == ''):

                    diff_dict[element] = temp_dict[element]

        self.tweet_list_init = temp_dict
        logger.info(f'Changed: {self.tweet_list_init}')
        return diff_dict

    async def _check_update_helper(self, ch_name) -> dict:
        temp_dict = {}
        if self.tweet_config[ch_name]['enabled']:
            if self.tweet_config[ch_name]['screen_name'] == '_':
                temp_dict[ch_name] = ''
                return temp_dict

            try:
                resp_text = self.get_time_line_from_screen_name(
                    screen_name=self.tweet_config[ch_name]['screen_name'])
                if resp_text == self.INFO_NOT_AVAILABLE:
                    temp_dict[ch_name] = ''
                    return temp_dict

            except Exception as err:
                logger.warning(err)
                temp_dict[ch_name] = ''
                return temp_dict

            temp_dict[ch_name] = resp_text

        return temp_dict

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
            logger.warning('连接出错！%s' % err)
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
                    logger.warning('Not authorized reply %s' % err)

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
                                    for chunk in resp.iter_content(chunk_size=1024 ** 3):
                                        f.write(chunk)

                            except Exception as err:
                                logger.warning('Something went wrong when getting twitter picture. %s' % err)

                        resp_text += '\n[CQ:image,file=file:///%s]' % file_name

            resp_text += '\n====================\n' if fetch_count != 1 else ''

        return resp_text
