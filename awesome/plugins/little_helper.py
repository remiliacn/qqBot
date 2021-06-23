import time
from datetime import datetime

import aiohttp
import nonebot
from nonebot.log import logger

from Services import random_services
from Services.stock import Stock, Crypto
from awesome.adminControl import permission as perm
from awesome.plugins.shadiao import sanity_meter
from awesome.plugins.util import helper_util
from config import SUPER_USER
from qq_bot_core import user_control_module
from youdaoService import youdao

cache = helper_util.HhshCache()

HHSHMEANING = 'meaning'
FURIGANAFUNCTION = 'furigana'


@nonebot.on_command('help', only_to_me=False)
async def send_help(session: nonebot.CommandSession):
    await session.send(
        '请移步\n'
        'https://github.com/remiliacn/Lingye-Bot/blob/master/README.md\n'
        '如果有新功能想要添加，请提交issue!'
    )


@nonebot.on_command('虚拟货币', only_to_me=False)
async def crypto_search(session: nonebot.CommandSession):
    key_word = session.get(
        'key_word',
        prompt='请输入货币缩写！'
    )

    crypto = Crypto(key_word)
    try:
        file_name, market_will = crypto.get_kline()
        if file_name:
            await session.send(
                f'[CQ:image,file=file:///{file_name}]\n'
                f'{market_will}'
            )
        else:
            await session.send(
                f'好像出问题了（\n'
            )

    except Exception as err:
        logger.log(f'{err} - Crypto error.')
        await session.finish('这货币真的上架了么……')


@nonebot.on_command('K线', aliases={'股票', '股票代码', 'k线'}, only_to_me=False)
async def k_line(session: nonebot.CommandSession):
    key_word = session.get(
        'key_word',
        prompt='请输入股票代码！'
    )

    if len(key_word) < 2:
        await session.finish('你太短了')

    stock = Stock(key_word, keyword=key_word)
    try:
        file_name, market_will = await stock.get_kline_map()
        if file_name:
            await session.send(
                f'[CQ:image,file=file:///{file_name}]' +
                f'{market_will}'
            )
        else:
            file_name = await stock.get_stock_codes()
            await session.send(
                f'好像出问题了（\n'
                f'灵夜机器人帮助你找到了以下备选搜索结果~\n'
                f'[CQ:image,file=file:///{file_name}]\n'
                f'请使用数字代码查询！'
            )

    except Exception as err:
        await session.send('出问题了出问题了~')
        bot = nonebot.get_bot()
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                    f'股票查询出错{err}, 股票代码：{key_word}'
        )


@nonebot.on_command('翻译', only_to_me=False)
async def translate(session: nonebot.CommandSession):
    trans = helper_util.translation()
    ctx = session.ctx.copy()
    if user_control_module.get_user_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    key_word = session.get('key_word', prompt='翻译的内容呢？')
    get_result = ''

    try:
        get_result = trans.getTranslationResult(sentence=key_word)
    except Exception as e:
        logger.warning('翻译出错！%s' % e)
        await session.finish('翻译出错了！请重试！')

    await session.send('以下来自于谷歌翻译的结果，仅供参考：\n%s' % get_result)


@nonebot.on_command('日语词典', only_to_me=False)
async def get_you_dao_service(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if user_control_module.get_user_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    key_word = session.get('key_word', prompt='词呢！词呢！！KORA！！！')
    if key_word != '':
        you = youdao.Youdaodict(keyWord=key_word)
        await session.send('以下是%s的查询结果\n%s' % (key_word, you.explain_to_string()))

    else:
        await session.send('...')


@nonebot.on_command('最新地震', only_to_me=False)
async def send_earth_quake_info(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if user_control_module.get_user_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    earth_quake_api_new = random_services.Earthquakeinfo()
    new_earthquake_info = earth_quake_api_new.get_newest_info()
    await session.send(new_earthquake_info)


@nonebot.on_command('日日释义', only_to_me=False)
async def jp_to_jp_dict(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if user_control_module.get_user_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    key_word = session.get('key_word', prompt='请输入一个关键字！')
    goo_api = None
    try:
        goo_api = youdao.Goodict(keyWord=key_word)
    except Exception as e:
        logger.warning('something went wrong in jptojpdict %s' % e)
        await session.finish('悲！连接出错惹')

    result, okay_or_not = goo_api.get_title_string()
    if okay_or_not:
        number = session.get('number', prompt='%s\n请输入要查询的部分的序号！' % result)
        try:
            number = int(number)
        except ValueError:
            await session.send('序号出错！')
            return

        goo_api.get_list(index=number)
        result = goo_api.get_explaination()
        await session.send('你查询的关键字%s的结果如下：\n%s' % (key_word, result))

    else:
        await session.send('出大错惹！！尝试新算法中……')
        goo_api.get_list(index=0, page='exception')
        result = goo_api.get_explaination()
        await session.send('你查询的关键字%s的结果如下：\n%s' % (key_word, result))


@nonebot.on_command('释义nico', only_to_me=False)
async def nico_send(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if user_control_module.get_user_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    keyWord = session.get('keyWord', prompt='歪？我的关键字呢？')
    api = youdao.Nicowiki(keyWord=keyWord)
    await session.send(api.__str__())
    if 'group_id' in ctx:
        sanity_meter.set_user_data(ctx['user_id'], 'nico')


@nonebot.on_command('反码', only_to_me=False)
async def reverseCode(session: nonebot.CommandSession):
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
        idNum = ctx['group_id']
    else:
        idNum = ctx['user_id']

    bot = nonebot.get_bot()

    if if_group:
        await bot.send_msg(message_type='group', group_id=idNum, message=key_word, auto_escape=True)
    else:
        await bot.send_msg(message_type='private', user_id=idNum, message=key_word, auto_escape=True)


@nonebot.on_command('好好说话', only_to_me=False)
async def can_you_be_fucking_normal(session: nonebot.CommandSession):
    start_time = time.time()
    ctx = session.ctx.copy()
    key_word = session.get('key_word', prompt='请输入一个关键词！')
    key_word = str(key_word)
    try:
        await session.send(await hhsh(key_word) + '\n本次查询耗时： %.2fs' % (time.time() - start_time))
        if 'group_id' in ctx:
            sanity_meter.set_user_data(ctx['user_id'], 'hhsh')

    except Exception as e:
        logger.debug('Something went wrong %s' % e)


@can_you_be_fucking_normal.args_parser
@get_you_dao_service.args_parser
@jp_to_jp_dict.args_parser
@nico_send.args_parser
@translate.args_parser
@k_line.args_parser
@crypto_search.args_parser
async def _youDaoServiceArgs(session: nonebot.CommandSession):
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36',
        'Origin': 'https://lab.magiconch.com',
        'referer': 'https://lab.magiconch.com/nbnhhsh/'
    }

    guess_url = 'https://lab.magiconch.com/api/nbnhhsh/guess'

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as client:
            async with client.post(guess_url, data={"text": entry}) as page:
                json_data = await page.json()

    except Exception as e:
        print(e)
        return '出问题了，请重试！'

    result = '这个缩写可能的意味有：\n'
    try:
        for idx, element in enumerate(json_data[0]['trans']):
            result += element + ', ' if idx + 1 != len(json_data[0]['trans']) else element

    except KeyError:
        try:
            return result + json_data[0]['inputting'][0]
        except KeyError:
            return '这……我也不懂啊草，能不能好好说话（'

    cache.store_result(entry, result, HHSHMEANING)
    return result
