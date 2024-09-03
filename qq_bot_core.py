from json import dump
from logging import getLogger, ERROR
from os import path, getcwd, mkdir, environ
from time import sleep

import nonebot
from loguru import logger
from nonebot.adapters.onebot.v11 import Adapter as OneBotdapter

# 如果下面这行报错，请暂时注释掉这行然后运行下面的main()
from awesome.adminControl import group_control

config_file = \
    """
from os import getcwd

NICKNAME = {}

PIXIV_REFRESH_TOKEN = '' # 选填，用于搜图功能

DANMAKU_PROCESS = f'' # 选填，如果需要b站开播追踪功能

PATH_TO_ONEDRIVE = '' # 选填，如果需要twitch下载功能
PATH_TEMP_DOWNLOAD = '' # 选填，如果需要YouTube下载功能
FFMPEG_PATH = '' # 选填，如果需要twitch或YouTube下载功能
SHARE_LINK = '' # 选填，如果需要twitch或YouTube下载功能

SAUCE_API_KEY = '' # 选填，如果需要sauceNAO逆向图片搜索
DISCORD_AUTH = '' # 选填，如果需要discord跟踪功能

COMMAND_START = {'/', '!', '／', '！', '#'}

HOST = '127.0.0.1' # 必填
PORT = 5700 # 必填
SUPER_USER = 0 # 必填

CLOUD_STORAGE_SIZE_LIMIT_GB = 90

BILI_SESS_DATA = "" # 选填，如果需要b站开播追踪功能

    """
nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotdapter)

nonebot.load_plugins("awesome/plugins")


def _remove_unused_files_from_db():
    group_control.group_quote_startup_sanity_check()


def _init_bot_resources():
    try:
        _create_necessary_folders()
        _remove_unused_files_from_db()
    except IOError:
        raise IOError(
            'Error occurred while creating directory for biaoqing, and bilibiliPic.'
        )


def _create_necessary_folders():
    _create_dir(f'{getcwd()}/logs/')
    _create_dir(f'{getcwd()}/data/biaoqing')
    _create_dir(f'{getcwd()}/data/bilibiliPic')
    _create_dir(f'{getcwd()}/data/pixivPic/')
    _create_dir(f'{getcwd()}/data/lol/')
    _create_dir(f'{getcwd()}/data/live/')
    _create_dir(f'{getcwd()}/config/')
    _create_dir(f'{getcwd()}/data/')
    _create_dir(f'{getcwd()}/data/bot')
    _create_dir(f'{getcwd()}/data/temp')
    _create_dir(f'{getcwd()}/data/bot/stock')


def _create_dir(path_to_check: str):
    if not path.exists(path_to_check):
        mkdir(path_to_check)


def _create_file(path_to_check: str, dump_data=None):
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

    _init_bot_resources()
    main()
