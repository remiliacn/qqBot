# 关于	
一个功能很杂的人工智障机器人

说明文档在[这里](https://github.com/remiliacn/Lingye-Bot)

# Config
建议进行以下设置：
```python3
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
```
