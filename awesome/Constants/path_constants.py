from os import path, getcwd

_B_PIC = 'bilibiliPic'
_DATA = 'data'
_DL = 'dl'
_OTHERS = 'others'
_PIXIV_PIC = 'pixivPic'

BILIBILI_PIC_PATH = path.join(getcwd(), _DATA, _B_PIC)
DL_PATH = path.join(getcwd(), _DATA, _DL, _OTHERS)
PIXIV_PIC_PATH = path.join(getcwd(), _DATA, _PIXIV_PIC)
