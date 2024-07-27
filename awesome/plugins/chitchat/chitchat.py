from os import getcwd, listdir
from os.path import exists
from random import seed, randint, choice
from time import time_ns

import nonebot
from loguru import logger

from Services.rate_limiter import UserLimitModifier
from Services.util.ctx_utility import get_user_id, get_nickname
from awesome.Constants import user_permission as perm
from awesome.plugins.util.helper_util import get_downloaded_image_qr_code
from qq_bot_core import user_control_module, global_rate_limiter

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)


@nonebot.on_command('添加图片', only_to_me=False)
async def add_more_pic(session: nonebot.CommandSession):
    types = ('恰柠檬', '流泪猫猫头', '迫害', '辛苦了', '不愧是你', '威胁', '社保', '恰桃')
    prompt_info = f'请输入要加入的类型，类型应该为这其中的一个：{types}\n' \
                  f'然后添加一个空格再加上需要添加的图'

    key_word = session.get('key_word', prompt=prompt_info)
    args = key_word.split()

    if args[0] not in types:
        await session.finish('不是说了必须是其中一个了kora')

    key_dict = {
        '恰柠檬': f'{getcwd()}/data/dl/lemon/',
        '流泪猫猫头': f'{getcwd()}/data/dl/useless/',
        '迫害': f'{getcwd()}/data/dl/pohai/',
        '辛苦了': f'{getcwd()}/data/dl/otsukare/',
        '不愧是你': f'{getcwd()}/data/dl/bukui/',
        '威胁': f'{getcwd()}/data/dl/weixie/',
        '社保': f'{getcwd()}/data/dl/shebao/',
        '恰桃': f'{getcwd()}/data/dl/peach/',
    }

    path = key_dict[args[0]]
    if session.current_arg_images:
        _ = get_downloaded_image_qr_code(session.current_arg_images[0], path)
        await session.finish('图片已添加！')

    await session.finish('你发的smjb玩意……')


@nonebot.on_command('?', aliases='？', only_to_me=False)
async def change_question_mark(session: nonebot.CommandSession):
    user_id = get_user_id(session.ctx.copy())
    if not get_privilege(user_id, perm.ADMIN):
        return

    await session.finish('¿?¿?')


@nonebot.on_command('你好', only_to_me=False)
async def send_hello_world(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(get_user_id(ctx), perm.OWNER):
        await session.send('妈妈好~')
    else:
        await session.send('你好呀~' + get_nickname(ctx))


@nonebot.on_command('内鬼', aliases='有没有内鬼', only_to_me=False)
async def nei_gui_response(session: nonebot.CommandSession):
    seed(time_ns())
    rand_num = randint(0, 50)
    ctx = session.ctx.copy()
    if rand_num >= 26 and not get_privilege(get_user_id(ctx), perm.OWNER):
        qq_num = get_user_id(ctx)
        await session.send(f'哦屑！有内鬼！终止交易！！ \n'
                           f'TA的QQ号是：{qq_num}！！！ \n'
                           f'QQ昵称是：{get_nickname(ctx)}')

    else:
        await session.send('一切安全！开始交易！')


@nonebot.on_command('我什么都不行', aliases={'什么都不行', '都不行', '不行', '流泪猫猫头'}, only_to_me=False)
async def useless_send(session: nonebot.CommandSession):
    await _chitchat_global_limit_check(session)
    file = await get_random_file(f'{getcwd()}/data/dl/useless')
    await session.send(f'[CQ:image,file=file:///{file}]')


@nonebot.on_command('威胁', only_to_me=False)
async def threat_send(session: nonebot.CommandSession):
    await _chitchat_global_limit_check(session)
    file = await get_random_file(f'{getcwd()}/data/dl/weixie')
    await session.send(f'[CQ:image,file=file:///{file}]')


@nonebot.on_command('恰柠檬', aliases='吃柠檬', only_to_me=False)
async def lemon_send(session: nonebot.CommandSession):
    await _chitchat_global_limit_check(session)
    file = await get_random_file(f'{getcwd()}/data/dl/lemon')
    await session.send(f'[CQ:image,file=file:///{file}]')


@nonebot.on_command('迫害', only_to_me=False)
async def send_pohai(session: nonebot.CommandSession):
    await _chitchat_global_limit_check(session)
    file = await get_random_file(f'{getcwd()}/data/dl/pohai')
    await session.send(f'[CQ:image,file=file:///{file}]')


@nonebot.on_command('不愧是你', aliases='bukui', only_to_me=False)
async def bu_kui_send(session: nonebot.CommandSession):
    await _chitchat_global_limit_check(session)
    file = await get_random_file(f'{getcwd()}/data/dl/bukui')
    await session.send(f'[CQ:image,file=file:///{file}]')


@nonebot.on_command('恰桃', aliases='恰peach', only_to_me=False)
async def send_peach(session: nonebot.CommandSession):
    await _chitchat_global_limit_check(session)
    file = await get_random_file(f'{getcwd()}/data/dl/peach')
    await session.send(f'[CQ:image,file=file:///{file}]')


@nonebot.on_command('社保', aliases='awsl', only_to_me=False)
async def she_bao(session: nonebot.CommandSession):
    await _chitchat_global_limit_check(session)
    file = await get_random_file(f'{getcwd()}/data/dl/shebao')
    await session.send(f'[CQ:image,file=file:///{file}]')


@nonebot.on_command('otsukare', aliases=('おつかれ', '辛苦了'), only_to_me=False)
async def otsukare(session: nonebot.CommandSession):
    await _chitchat_global_limit_check(session)
    file = await get_random_file(f'{getcwd()}/data/dl/otsukare')
    await session.send(f'[CQ:image,file=file:///{file}]')


async def get_random_file(path: str) -> str:
    if not exists(path):
        raise FileNotFoundError(f'No image found in default location: {path}')

    file = listdir(path)
    return path + '/' + choice(file)


async def _chitchat_global_limit_check(session: nonebot.CommandSession):
    user_limit = UserLimitModifier(60, 1, True)
    user_id = get_user_id(session.ctx.copy())
    rate_limiter_check_temp = await global_rate_limiter.user_limit_check(
        "CHITCHAT_GLOBAL", user_id, user_limit
    )
    if isinstance(rate_limiter_check_temp, str):
        logger.warning(f'User {user_id} has hit the rate limit: {rate_limiter_check_temp}')
        await session.finish('别刷了')
