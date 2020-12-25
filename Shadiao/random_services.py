import json
import os
import re
from datetime import datetime
from nonebot.log import logger

import aiohttp

import random
import requests
import time

with open('config/downloader_data.json', 'r') as f:
    JSON_DATA = json.loads(f.read())

class Earthquakeinfo:
    def __init__(self):
        random.seed(time.time_ns())
        self.base_url = 'http://news.ceic.ac.cn/ajax/google?rand=%d' % random.randint(0, 5)
        self.earth_dict = self._get_earth_dict()

    def _get_earth_dict(self):
        page = requests.get(self.base_url, timeout=10).json()
        return page[len(page) - 1]

    def get_newest_info(self):
        return '最新地震情况：\n' \
               '地震强度：%s级\n' \
               '发生时间（UTC+8)：%s\n' \
               '纬度：%s°\n' \
               '经度：%s°\n' \
               '震源深度：%skm\n' \
               '震源位置：%s' % (self.earth_dict['M'], self.earth_dict['O_TIME'], self.earth_dict['EPI_LAT'],
                            self.earth_dict['EPI_LON'], self.earth_dict['EPI_DEPTH'],
                            self.earth_dict['LOCATION_C'])


class YouTubeLiveTracker:
    def __init__(self, channel: str, ch_name: str):
        self.headers = {
            'User-Agent' : 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36',
            'Referer' : 'https://www.youtube.com/'
        }
        self.base_url = f'https://www.youtube.com/channel/{channel}/live'
        self.ch_name = ch_name
        self.json_data = {}
        self.live_data = {}
        self.new_video_id = ''

    async def get_json_data(self):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(self.base_url) as r:
                text = await r.text()
                content_live = re.findall(r'ytInitialPlayerResponse = ({.*?});', text)

                if not content_live:
                    json_data = {'videoDetails' : {}}
                else:
                    content_live = content_live[0]
                    try:
                        json_data = json.loads(content_live)
                    except json.JSONDecodeError:
                        json_data = {'videoDetails' : {}}

                self.json_data = json_data

    def get_upcoming_status(self) -> bool:
        live_stat = self.json_data['videoDetails']
        if not 'isUpcoming' in live_stat:
            return False

        self.new_video_id = live_stat['videoId']
        return live_stat['isUpcoming']

    def get_live_status(self) -> bool:
        live_stat = self.json_data['videoDetails']
        if not 'isLive' in live_stat:
            return False

        self.new_video_id = live_stat['videoId']
        return live_stat['isLive']

    async def get_live_details(self) -> str:
        live_stat = self.json_data['videoDetails']
        get_data = lambda x, y: y[x] if x in y else ''

        title = get_data('title', live_stat)

        thumbnail_url = live_stat['thumbnail'] if 'thumbnail' in live_stat else {}
        image_data_in_qcode = ''

        try:
            live_time = self.json_data['playabilityStatus']['liveStreamability']
            live_time = live_time['liveStreamabilityRenderer']['offlineSlate']
            live_time = live_time['liveStreamOfflineSlateRenderer']['scheduledStartTime']
            live_time = datetime.fromtimestamp(int(live_time)).strftime('%Y-%m-%d %H:%M:%S')
        except KeyError:
            logger.warning(f'No live_time param for the live for {self.ch_name}')
            live_time = self.json_data['playabilityStatus']['liveStreamability']
            live_time = live_time['liveStreamabilityRenderer']
            if self.get_live_status():
                live_time = 'LIVE NOW'
            else:
                live_time = live_time['offlineSlate']['liveStreamOfflineSlateRenderer']
                if 'mainText' in live_time:
                    live_time = live_time['mainText']['runs'][0]['text']
                    if 'offline' in live_time:
                        live_time = ''
                    else:
                        live_time = 'Unknown Status'
                else:
                    live_time = 'Unknown Status'

        if thumbnail_url:
            thumbnail = live_stat['thumbnail']['thumbnails'][-1]['url']
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(thumbnail) as image:
                    file_name = f'{os.getcwd()}/data/live/{live_stat["videoId"]}.jpg'
                    # Redownload the thumbnail when going live just in case a thumbnail change.
                    if not os.path.exists(file_name) or self.get_live_status():
                        with open(file_name, 'wb') as file:
                            while True:
                                chunk = await image.content.read(1024 ** 2)
                                if not chunk:
                                    break
                                file.write(chunk)

            image_data_in_qcode = f'[CQ:image,file=file:///{file_name}]'

        if live_time:
            result = f'标题 {title}\n\n' \
                     f'=== 封面 ===\n' \
                     f'{image_data_in_qcode}\n' \
                     f'开播时间：{live_time}\n' \
                     f'观看地址：https://www.youtube.com/watch?v={self.new_video_id}'

            self.live_data = {
                "title": title,
                "thumbnail": image_data_in_qcode,
                "live_time": live_time,
                "videoID": self.new_video_id
            }
        else:
            result = ''

        return result

    async def update_live_id(self, is_checking_live: bool) -> (int, str):
        if not os.path.exists(f'config/downloader.json'):
            raise FileNotFoundError()

        with open(f'config/downloader.json', 'r', encoding='utf8') as file:
            json_data = json.loads(file.read())

        # if live
        if is_checking_live:
            # self.get_live_status()
            if 'liveID' not in json_data[self.ch_name] or self.new_video_id != json_data[self.ch_name]['liveID']:
                json_data[self.ch_name]['liveID'] = self.new_video_id
                with open(f'{os.getcwd()}/config/downloader.json', 'w+', encoding='utf8') as file:
                    json.dump(json_data, file, indent=4)

                return 1, ''

        #if not live
        else:
            # self.get_upcoming_status()
            await self.get_live_details()
            if 'upcomingID' not in json_data[self.ch_name] or self.new_video_id != json_data[self.ch_name]['upcomingID']:
                json_data[self.ch_name]['upcomingID'] = self.new_video_id
                with open(f'{os.getcwd()}/config/downloader.json', 'w+', encoding='utf8') as file:
                    json.dump(json_data, file, indent=4)

                self.save_vtuber_stat()
                return 1, ''

            elif self.new_video_id == json_data[self.ch_name]['upcomingID']:
                loaded_data = self.load_vtuber_saved_stat()
                if loaded_data != self.live_data:
                    self.save_vtuber_stat()
                    result = ''
                    if loaded_data['title'] != self.live_data['title']:
                        result += f'- 标题 {loaded_data["title"]}\n'
                        result += f'+ 标题 {self.live_data["title"]}\n\n'
                    else:
                        result += f'标题 {self.live_data["title"]}\n'

                    result += f'=== 封面 ===\n'
                    if loaded_data['thumbnail'] != self.live_data['thumbnail']:
                        result += f'- {loaded_data["thumbnail"]}\n'
                        result += f'+ {self.live_data["thumbnail"]}\n'
                    else:
                        result += self.live_data["thumbnail"] + '\n'

                    if loaded_data['live_time'] != self.live_data['live_time']:
                        result += f'- 开播时间：{loaded_data["live_time"]}\n'
                        result += f'+ 开播时间：{self.live_data["live_time"]}\n'
                    else:
                        result += f'开播时间：{self.live_data["live_time"]}\n'

                    if loaded_data["videoID"] != self.live_data["videoID"]:
                        result += f'- 观看地址：https://www.youtube.com/watch?v={loaded_data["videoID"]}\n'
                        result += f'+ 观看地址：https://www.youtube.com/watch?v={self.live_data["videoID"]}\n'
                    else:
                        result += f'观看地址：https://www.youtube.com/watch?v={self.live_data["videoID"]}\n'

                    return 2, result

        return 0, ''

    def load_vtuber_saved_stat(self):
        if self.ch_name not in JSON_DATA:
            return {}

        return JSON_DATA[self.ch_name]

    def save_vtuber_stat(self):
        JSON_DATA[self.ch_name] = self.live_data
        with open('config/downloader_data.json', 'w+') as file:
            json.dump(JSON_DATA, file, indent=4)


if __name__ == '__main__':
    api = YouTubeLiveTracker('UC9pYOJPB5UYlMlGKKZWo-Bw', 'test')
    if api.get_live_status():
        print(api.get_live_details())
