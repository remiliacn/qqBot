import nonebot
from nonebot.log import logger
from os import path
import config
from json import loads, dump

def register_true():
    if not path.exists('D:/dl/started.json'):
        with open('D:/dl/started.json', 'w+') as f:
            dump({}, f, indent=4)

    with open('D:/dl/started.json', 'r') as file:
        statusDict = loads(str(file.read()))
        statusDict['status'] = True

        with open('D:/dl/started.json', 'w+') as f:
            dump(statusDict, f, indent=4)

    if not path.exists('config.py'):
        logger.warning('No config file detected. Generating a template...')
        config_file = \
        """
        from nonebot.default_config import *
        
        NICKNAME = {}
        consumer_key = '' # twitter API consumer key
        consumer_secret = '' # twitter API consumer secret
        access_token = '' # twitter API access token
        access_secret = '' # twitter API access secret
        user_name = '' # Pixiv login username
        password = '' # Pixiv login password
        
        itpk_key = '' # 茉莉机器人API key
        itpk_secret = '' # 茉莉机器人API secret
        
        SESSION_EXPIRE_TIMEOUT = timedelta(minutes=1)
        
        HOST = '127.0.0.1'
        PORT = 5700
        """

        with open('config.py', 'w+') as file:
            file.write(config_file)

if __name__ == '__main__':
    register_true()
    nonebot.init(config)
    nonebot.log.logger.setLevel('INFO')
    nonebot.load_plugins(
        path.join(path.dirname(__file__), 'awesome', 'plugins'),
        'awesome.plugins'
    )

    logger.warning('Plugins successfully installed.')
    nonebot.run()







