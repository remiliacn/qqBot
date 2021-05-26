from json import dump
from os import path, getcwd, mkdir
from time import sleep

import nonebot
from nonebot.log import logger

import config
from Shadiao.cangku_api import CangkuApi
from awesome.adminControl import alarm, user_control, setu, group_admin
from awesome.adminControl.weeb_controller import WeebController

config_file = \
    """
    from nonebot.default_config import *
    
    NICKNAME = {}
    CONSUMER_KEY = ''    # Twitter consumer key
    CONSUMER_SECRET = '' # Twitter Secret Token
    ACCESS_TOKEN = ''    # Twitter Access Token
    ACCESS_SECRET = ''   # Twitter Access Secret Token
    
    PIXIV_REFRESH_TOKEN = '' # Pixiv refresh token (upbit/pixivpy的issue#158有获取方式)
    DOWNLODER_FILE_NAME = 'forDownload.py'
    
    ITPK_KEY = ''        # 茉莉机器人API KEY
    ITPK_SECRET = ''     # 茉莉机器人API SECRET
    
    SAUCE_API_KEY = ''   # Sauce API key.
    
    HOST = '127.0.0.1'
    PORT = 5700
    SUPER_USER = 0       # 超级管理员qq号 (int)
    
    # 如果需要YouTube自动扒源功能可保留下面的参数，否则可以删除
    # 删除后可移除forDownload.py文件以及do_youtube_update_fetch()方法
    # 该方法存在于./awesome/plugins/get_tweet.py
    
    PATH_TO_ONEDRIVE = ''    # OneDrive盘路径，或服务器文件路径终点
    PATH_TEMP_DOWNLOAD = ''  # 视频下载的缓存地址
    FFMPEG_PATH = ''         # FFMPEG路径
    SHARE_LINK = ''          # OneDrive分享地址，或服务器目录根地址。
    
    """

alarm_api = alarm.Alarm()
user_control_module = user_control.UserControl()
sanity_meter = setu.SetuFunction()
admin_control = group_admin.Shadiaoadmin()
weeb_learning = WeebController()
cangku_api = CangkuApi()


def register_true():
    if not path.exists('data/started.json'):
        with open('data/started.json', 'w+') as f:
            dump({}, f, indent=4)

    if not path.exists('config/downloader_data.json'):
        with open('config/downloader_data.json', 'w+') as f:
            dump({}, f, indent=4)

    with open('data/started.json', 'w+') as f:
        dump({'status': True}, f, indent=4)

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
        raise IOError(
            'Error occurred while creating directory for biaoqing, and bilibiliPic.'
        )


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
