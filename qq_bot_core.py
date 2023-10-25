from json import dump
from os import path, getcwd, mkdir
from time import sleep

import nonebot
from nonebot.log import logger

# 如果下面这行报错，请暂时注释掉这行然后运行下面的main()
import config
from Services.cangku_api import CangkuApi
from Services.rate_limiter import RateLimiter
from Services.simulate_stock import SimulateStock
from awesome.adminControl import user_control, setu, group_control
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
    DOWNLODER_FILE_NAME = 'for_download.py'
    
    ITPK_KEY = ''        # 茉莉机器人API KEY
    ITPK_SECRET = ''     # 茉莉机器人API SECRET
    
    SAUCE_API_KEY = ''   # Sauce API key.
    
    HOST = '127.0.0.1'
    PORT = 5700
    SUPER_USER = 0       # 超级管理员qq号 (int)
    
    BUFF_SESSION_ID = ''
    STEAM_UTIL_GROUP_NUM = []
    
    # 如果需要YouTube自动扒源功能可保留下面的参数，否则可以删除
    # 删除后可移除forDownload.py文件以及do_youtube_update_fetch()方法
    # 该方法存在于./awesome/plugins/vtuber_functions.py
    
    PATH_TO_ONEDRIVE = ''    # OneDrive盘路径，或服务器文件路径终点
    PATH_TEMP_DOWNLOAD = ''  # 视频下载的缓存地址
    FFMPEG_PATH = ''         # FFMPEG路径
    SHARE_LINK = ''          # OneDrive分享地址，或服务器目录根地址。
    
    CANGKU_USERNAME = ''
    CANGKU_PASSWORD = ''
    
    OKEX_API_KEY  = ""
    OKEX_SECRET_KEY= ""
    OKEX_PASSPHRASE = ""
    
    """

user_control_module = user_control.UserControl()
setu_control = setu.SetuFunction()
admin_group_control = group_control.GroupControlModule()
weeb_learning = WeebController()

global_rate_limiter = RateLimiter()

cangku_api = CangkuApi()
virtual_market = SimulateStock()


def register_true():
    try:
        create_dir(f'{getcwd()}/data/biaoqing')
        create_dir(f'{getcwd()}/data/bilibiliPic')
        create_dir(f'{getcwd()}/data/pixivPic/')
        create_dir(f'{getcwd()}/data/pixivPic/')
        create_dir(f'{getcwd()}/data/lol/')
        create_dir(f'{getcwd()}/data/live/')
        create_dir(f'{getcwd()}/config/')
        create_dir(f'{getcwd()}/data/')
        create_dir(f'{getcwd()}/data/bot')
        create_dir(f'{getcwd()}/data/bot/stock')

    except IOError:
        raise IOError(
            'Error occurred while creating directory for biaoqing, and bilibiliPic.'
        )

    create_file('data/started.json')
    create_file('config/downloader_data.json')
    create_file('config/YouTubeNotify.json')
    create_file('data/started.json', {'status': True})
    create_file('config/downloader.json', {
        '_comment': {
            '_comment': '示例downloader配置请见downloader_sample.json', "channel": "UCyIcOCH-VWaRKH9IkR8hz7Q",
            'qqGroup': 123456789,
            'videoID': '',
            'enabled': False,
            'notify': False,
            'upcomingID': '',
            'liveID': ''}
    })

    with open('data/started.json', 'w+') as f:
        dump({'status': True}, f, indent=4)


def create_dir(path_to_check: str):
    if not path.exists(path_to_check):
        mkdir(path_to_check)


def create_file(path_to_check: str, dump_data=None):
    if dump_data is None:
        dump_data = {}
    if not path.exists(path_to_check):
        with open(path_to_check, 'w+', encoding='utf-8') as f:
            dump(dump_data, f, indent=4, ensure_ascii=False)


def main():
    # 记着生成config文件后把本文件的import config去掉注释
    nonebot.init(config)
    nonebot.log.logger.setLevel('WARNING')

    nonebot.load_plugins(
        path.join(path.dirname(__file__), 'awesome', 'plugins'),
        'awesome.plugins'
    )

    logger.warning('Plugins successfully installed.')
    nonebot.run()


if __name__ == '__main__':
    if not path.exists(f'{getcwd()}/config.py'):
        logger.warning('未检测到配置文件，尝试生成模板中……')

        with open('config.py', 'w+', encoding='utf-8') as file:
            file.write(config_file)

        logger.warning('模板生成完毕！请修改config.py中的参数！')
        sleep(10)

        exit(1)

    register_true()
    main()
