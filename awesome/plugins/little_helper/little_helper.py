import time

import nonebot
from loguru import logger

from Services import random_services
from Services.currency import Currency
from Services.keylol_update import KeylolFreeGame
from Services.util.common_util import HttpxHelperClient
from Services.util.ctx_utility import get_nickname, get_user_id, get_group_id
from awesome.Constants import user_permission as perm
from awesome.Constants.function_key import HHSH_FUNCTION
from awesome.plugins.shadiao.shadiao import setu_control
from awesome.plugins.util import helper_util, search_helper
from qq_bot_core import user_control_module

cache = helper_util.HhshCache()

HHSHMEANING = 'meaning'
FURIGANAFUNCTION = 'furigana'


@nonebot.on_command('搜索', only_to_me=False)
async def search_command(session: nonebot.CommandSession):
    arg = session.current_arg
    if not arg:
        await session.finish('你在干神魔？')

    result = await search_helper.get_definition(arg)
    if result:
        await session.finish(result)

    await session.finish('找不到，自己查罢。')


@nonebot.on_command('help', only_to_me=False)
async def send_help(session: nonebot.CommandSession):
    await session.send(
        '请移步\n'
        'https://github.com/remiliacn/Lingye-Bot/blob/master/README.md\n'
        '如果有新功能想要添加，请提交issue!'
    )


@nonebot.on_command('免费游戏', only_to_me=False)
async def get_free_game(session: nonebot.CommandSession):
    keylol = KeylolFreeGame()
    await keylol.get_update()
    await session.send(keylol.get_free_game_list())


@nonebot.on_command('最新地震', only_to_me=False)
async def send_earth_quake_info(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if user_control_module.get_user_privilege(get_user_id(ctx), perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    earth_quake_api_new = random_services.Earthquakeinfo()
    new_earthquake_info = await earth_quake_api_new.get_newest_info()
    await session.send(new_earthquake_info)


@nonebot.on_command('反码', only_to_me=False)
async def reverse_code(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    key_word = ctx['raw_message']
    message_list = key_word.split()
    if len(message_list) == 1:
        await session.send('没有可反码内容！')
        return

    key_word = message_list[1]
    if_group = False
    if 'group_id' in ctx:
        if_group = True
        id_num = get_group_id(ctx)
    else:
        id_num = get_user_id(ctx)

    bot = nonebot.get_bot()

    if if_group:
        await bot.send_msg(message_type='group', group_id=id_num, message=key_word, auto_escape=True)
    else:
        await bot.send_msg(message_type='private', user_id=id_num, message=key_word, auto_escape=True)


@nonebot.on_command('汇率', aliases={'汇率换算'}, only_to_me=False)
async def get_currency_and_send(session: nonebot.CommandSession):
    arg = session.current_arg_text
    arg_parse = arg.split()
    if len(arg_parse) <= 1:
        await session.finish('正确用法：！汇率 数额 来源货币（例：！汇率 12.5 CNY）')

    amount = arg_parse[0]
    source = arg_parse[1]

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await session.finish('第一参数必须为正数')

    c = Currency(amount, source)
    result = await c.get_currency_result()
    await session.send('无数据' if not result else result)


@nonebot.on_command('好好说话', only_to_me=False)
async def can_you_be_fucking_normal(session: nonebot.CommandSession):
    start_time = time.time()
    ctx = session.ctx.copy()
    key_word = session.get('key_word', prompt='请输入一个关键词！')
    key_word = str(key_word)
    nickname = get_nickname(ctx)
    try:
        await session.send(await hhsh(key_word) + '\n本次查询耗时： %.2fs' % (time.time() - start_time))
        if 'group_id' in ctx:
            setu_control.set_user_data(get_user_id(ctx), HHSH_FUNCTION, nickname)

    except Exception as e:
        logger.debug('Something went wrong %s' % e)


@can_you_be_fucking_normal.args_parser
async def _you_dao_service_args(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('词呢！词呢！！KORA！！！')


async def hhsh(entry: str) -> str:
    if cache.check_exist(entry, HHSHMEANING):
        return cache.get_result(entry, HHSHMEANING)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/81.0.4044.138 Safari/537.36',
        'Origin': 'https://lab.magiconch.com',
        'referer': 'https://lab.magiconch.com/nbnhhsh/'
    }

    guess_url = 'https://lab.magiconch.com/api/nbnhhsh/guess'

    try:
        client = HttpxHelperClient()
        page = await client.post(guess_url, json={"text": entry}, headers=headers)
        json_data = page.json()

    except Exception as e:
        print(e)
        return ''

    result = '这个缩写可能的意味有：\n'
    try:
        for element in json_data:
            result += f'当缩写为{element["name"]}时，其意味可以是：\n{"，".join(element["trans"])}\n'

    except KeyError:
        try:
            return result + json_data[0]['inputting'][0]
        except KeyError:
            return '这……我也不懂啊草，能不能好好说话（'
    except Exception as err:
        logger.info(f'hhsh err: {err}')
        return ''

    cache.store_result(entry, result, HHSHMEANING)
    return result.strip()
