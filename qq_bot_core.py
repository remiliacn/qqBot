from json import dump
from os import path, getcwd, mkdir
from time import sleep

import nonebot
from nonebot.log import logger

import config
from awesome.adminControl import alarm, user_control, setu, group_admin
from awesome.adminControl.weeb_controller import WeebController

config_file = \
"""
from nonebot.default_config import *

NICKNAME = {}
consumer_key = '' # twitter API consumer key
consumer_secret = '' # twitter API consumer secret
access_token = '' # twitter API access token
access_secret = '' # twitter API access secret
sauce_nao_API_key = ''

pixiv_refresh_token = '' # See issues #158 in repo upbit/pixivpy for retrieving method.

downloader = 'forDownload.py'

path_export = ''                # OneDrive path for downloaded video.
path_temp = ''                  # Temp saving path for downloaded video.
ffmpeg_path = ''                # If ffmpeg is not in $path, here should be set.
share_link = ''                 # OneDrive share link.

SUPER_USER = 0 # Report will be sent to this qq.

itpk_key = '' # 茉莉机器人API key
itpk_secret = '' # 茉莉机器人API secret

HOST = '127.0.0.1'
PORT = 5700
"""

alarm_api = alarm.Alarm()
user_control_module = user_control.UserControl()
sanity_meter = setu.SetuFunction()
admin_control = group_admin.Shadiaoadmin()
weeb_learning = WeebController()

def register_true():
    if not path.exists('data/started.json'):
        with open('data/started.json', 'w+') as f:
            dump({}, f, indent=4)

    if not path.exists('config/downloader_data.json'):
        with open('config/downloader_data.json', 'w+') as f:
            dump({}, f, indent=4)

    with open('data/started.json', 'w+') as f:
        dump({'status' : True}, f, indent=4)

    if not path.exists('config.py'):
        logger.warning('No config file detected. Generating a template...')

        with open('config.py', 'w+', encoding='utf-8') as file:
            file.write(config_file)

        logger.warning('Generation completed... Exiting the program. Please edit it!')
        sleep(10)

        exit(1)

    try:
        if not path.exists(f'{getcwd()}/data/biaoqing'):
            mkdir(f'{getcwd()}/data/biaoqing')

        if not path.exists(f'{getcwd()}/data/bilibiliPic'):
            mkdir(f'{getcwd()}/data/bilibiliPic')

        if not path.exists(f'{getcwd()}/data/pixivPic/'):
            mkdir(f'{getcwd()}/data/pixivPic/')

        if not path.exists(f'{getcwd()}/data/lol/'):
            mkdir(f'{getcwd()}/data/lol/')

        if not path.exists(f'{getcwd()}/data/live/'):
            mkdir(f'{getcwd()}/data/live/')

        if not path.exists(f'{getcwd()}/config/'):
            mkdir(f'{getcwd()}/config/')

        if not path.exists(f'{getcwd()}/Waifu/'):
            mkdir(f'{getcwd()}/Waifu')

    except IOError:
        raise IOError('Error occurred while creating directory for biaoqing, and bilibiliPic.')


def main():
    nonebot.init(config)
    nonebot.log.logger.setLevel('INFO')

    nonebot.load_plugins(
        path.join(path.dirname(__file__), 'awesome', 'plugins'),
        'awesome.plugins'
    )

    logger.warning('Plugins successfully installed.')
    nonebot.run()

if __name__ == '__main__':
    register_true()
    main()







