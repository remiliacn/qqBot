import sqlite3
from json import dump
from logging import getLogger, ERROR
from os import path, getcwd, mkdir, environ
from time import sleep

import nonebot
from loguru import logger
from nonebot.adapters.onebot.v11 import Adapter as OneBotdapter

# 如果下面这行报错，请暂时注释掉这行然后运行下面的main()
from Services.simulate_stock import SimulateStock

config_file = \
    """
NICKNAME = {}
CONSUMER_KEY = ''    # Twitter consumer key
CONSUMER_SECRET = '' # Twitter Secret Token
ACCESS_TOKEN = ''    # Twitter Access Token
ACCESS_SECRET = ''   # Twitter Access Secret Token

PIXIV_REFRESH_TOKEN = '' # Pixiv refresh token (upbit/pixivpy的issue#158有获取方式)

ITPK_KEY = ''        # 茉莉机器人API KEY
ITPK_SECRET = ''     # 茉莉机器人API SECRET

SAUCE_API_KEY = ''   # Sauce API key.

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

    """

temp_message_db = sqlite3.connect(f'{getcwd()}/data/db/temp_messages.db')

virtual_market = SimulateStock()

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotdapter)

nonebot.load_plugins("awesome/plugins")


def register_true():
    try:
        create_dir(f'{getcwd()}/logs/')
        create_dir(f'{getcwd()}/data/biaoqing')
        create_dir(f'{getcwd()}/data/bilibiliPic')
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
    create_file('data/started.json', {'status': True})

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
    logger.warning('Plugins successfully installed.')
    getLogger('asyncio').setLevel(ERROR)
    nonebot.run()


if __name__ == '__main__':
    logger.warning(f'Working directory: {getcwd()}')
    environ['PYTHONUTF8'] = '1'
    if not path.exists(f'{getcwd()}/config.py'):
        logger.warning('未检测到配置文件，尝试生成模板中……')

        with open('config.py', 'w+', encoding='utf-8') as file:
            file.write(config_file)

        logger.warning('模板生成完毕！请修改config.py中的参数！')
        sleep(10)

        exit(1)

    register_true()
    main()
