from json import dump
from logging import getLogger, ERROR
from os import path, getcwd, mkdir, environ
from time import sleep

import nonebot
from loguru import logger
from nonebot.adapters.onebot.v11 import Adapter as OneBotdapter

# 如果下面这行报错，请暂时注释掉这行然后运行下面的main()
from awesome.adminControl import group_control

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
    _create_dir(f'{getcwd()}/config/')
    _create_dir(f'{getcwd()}/data/')
    _create_dir(f'{getcwd()}/data/biaoqing')
    _create_dir(f'{getcwd()}/data/bilibiliPic')
    _create_dir(f'{getcwd()}/data/bot')
    _create_dir(f'{getcwd()}/data/db')
    _create_dir(f'{getcwd()}/data/live')
    _create_dir(f'{getcwd()}/data/pixivPic')
    _create_dir(f'{getcwd()}/data/lol')
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
        logger.warning('未检测到配置文件，请按照sample_config.py中的说明进行配置！')
        sleep(10)

        exit(1)

    _init_bot_resources()
    main()
