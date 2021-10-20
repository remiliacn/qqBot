# 关于	

## 目前进度

由于我目前有个全职工作的原因，更新将会放缓。如果有想要添加的功能的话请直接提交pull request，或者issue。

感谢理解！

## 需求

* Python版本为 3.7+
* 安装requirements.txt中的所有依赖 `pip install -r requirements.txt`
* 运行Go-CQHTTP[具体文档清参考这里](https://github.com/Mrs4s/go-cqhttp)
* 参考[nonebot](https://github.com/nonebot/nonebot)的配置文档按需在qq_bot_core.py中配置机器人

## 主要功能

* YouTube频道监控（可通知直播间设置以及开播）
* Twitter监控（可通知新推、转推、和回推）
* 多种娱乐功能（轮盘赌、明日方舟十连寻访模拟、嘴臭等）
* YouTube自动/手动下源
* 色图功能！（需要Pixiv账号）
* 搜图功能（支持使用“回复”并直接输入搜图来进行搜图，或者！搜图 [图片]（详见说明文档）
* 警报系统（在高网络延迟的情况下停用部分功能）
* 权限系统（想要什么群，什么用户使用什么功能均可进行自定义）

说明文档在[这里](https://github.com/remiliacn/Lingye-Bot)

### 重要
* 为了更好的使用机器人，请在config.py文件中的`SUPER_USER`参数上设置好自己的QQ号，并使用`添加管理`命令将自己的qq号添加上管理员权限


# Config
建议进行以下设置：

```python3
from nonebot.default_config import *

NICKNAME = {}
CONSUMER_KEY = ''  # Twitter consumer key
CONSUMER_SECRET = ''  # Twitter Secret Token
ACCESS_TOKEN = ''  # Twitter Access Token
ACCESS_SECRET = ''  # Twitter Access Secret Token

PIXIV_REFRESH_TOKEN = ''  # Pixiv refresh token (upbit/pixivpy的issue#158有获取方式)
DOWNLODER_FILE_NAME = 'for_download.py'

ITPK_KEY = ''  # 茉莉机器人API KEY
ITPK_SECRET = ''  # 茉莉机器人API SECRET

SAUCE_API_KEY = ''  # Sauce API key.

HOST = '127.0.0.1'
PORT = 5700
SUPER_USER = 0  # 超级管理员qq号 (int)

# 如果需要YouTube自动扒源功能可保留下面的参数，否则可以删除
# 删除后可移除forDownload.py文件以及do_youtube_update_fetch()方法
# 该方法存在于./awesome/plugins/get_tweet.py

PATH_TO_ONEDRIVE = ''  # OneDrive盘路径，或服务器文件路径终点
PATH_TEMP_DOWNLOAD = ''  # 视频下载的缓存地址
FFMPEG_PATH = ''  # FFMPEG路径
SHARE_LINK = ''  # OneDrive分享地址，或服务器目录根地址。

CANGKU_USERNAME = ''
CANGKU_PASSWORD = ''

OKEX_API_KEY = ""
OKEX_SECRET_KEY = ""
OKEX_PASSPHRASE = ""
```

在配置后可能会出现部分文件缺失的情况，请按需删除不需要的参数。（因为有些功能是为某些群的需求特供的，所以可能不适合大部分用户）

您可以参考`sample_config`的配置方式对您的机器人进行配置。
