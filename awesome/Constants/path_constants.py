from os import path, getcwd

_B_PIC = 'bilibiliPic'
_BOT = 'bot'
_DATA = 'data'
_DB = 'db'
_DL = 'dl'
_FOLDER_LOL = 'lol'
_OTHERS = 'others'
_PIXIV_PIC = 'pixivPic'
_RESPONSE = 'response'

BILIBILI_PIC_PATH = path.join(getcwd(), _DATA, _B_PIC)
DB_PATH = path.join(getcwd(), _DATA, _DB)
DL_PATH = path.join(getcwd(), _DATA, _DL, _OTHERS)
LOL_FOLDER_PATH = path.join(getcwd(), _DATA, _FOLDER_LOL)
PIXIV_PIC_PATH = path.join(getcwd(), _DATA, _PIXIV_PIC)
BOT_RESPONSE_PATH = path.join(getcwd(), _DATA, _BOT, _RESPONSE)
