import re
from asyncio.log import logger
from datetime import datetime
from random import choice

import nonebot
from aiohttp import ClientConnectionError

from Services.stock import Crypto, Stock, text_to_image
from config import SUPER_USER
from qq_bot_core import virtual_market

ATTENTION = [
    '虚拟交易为仅供娱乐，实盘请注意风险控制。',
    '先求知，再投资，少损失。',
    '不跟风、不迷信、不盲从。',
    '多一分谨慎，少一分风险；多一分了解，少一分损失。',
    '保障基本生活，切勿冒险投资。'
]


def get_attention():
    return f'【{choice(ATTENTION)}】\n\n'


@nonebot.on_command('虚拟货币', aliases={'okex'}, only_to_me=False)
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
        logger.warning(f'{err} - Crypto error.')
        await session.finish('这货币真的上架了么……')


@nonebot.on_command('把钱还我', only_to_me=False)
async def reset_user_stock_data(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = ctx['user_id']

    user_response = session.get('user_response', prompt='您确定要重置持仓么？该操作不能撤回！（回复Y，YES 或 是确认）').strip()
    if user_response.upper() in ('Y', 'YES', '是'):
        await session.finish(virtual_market.reset_user(user_id))

    await session.finish('已取消')


@nonebot.on_command('K线', aliases={'股票', '股票代码', 'k线'}, only_to_me=False)
async def k_line(session: nonebot.CommandSession):
    key_word: str = session.get(
        'key_word',
        prompt='请输入股票代码！'
    )

    if len(key_word) < 2:
        await session.finish('你太短了')

    stock = Stock(key_word, keyword=key_word)
    try:
        market_type = virtual_market.get_type_by_stock_code(key_word)
        if market_type is None:
            current_price, stock_name, _ = await stock.get_purchase_price()
            virtual_market.set_stock_cache(key_word, stock_name, stock.type, current_price, False)
        else:
            stock.set_type(market_type)

        file_name, market_will = await stock.get_kline_map()
        if file_name:
            await session.send(
                f'[CQ:image,file=file:///{file_name}]\n' +
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


@nonebot.on_command('购买', aliases={'buy', '买入'}, only_to_me=False)
async def buy_stonk(session: nonebot.CommandSession):
    args = session.current_arg_text
    args = args.split()

    ctx = session.ctx.copy()
    if len(args) != 2:
        await session.finish('用法是！购买 股票名称/代码/缩写 数量')

    user_id = ctx['user_id']
    message_id = ctx['message_id']
    await session.finish(
        f'[CQ:reply,id={message_id}]'
        f'{get_attention()}'
        f'{await virtual_market.buy_with_code_and_amount(user_id, args[0], args[1], ctx=ctx)}'
    )


@nonebot.on_command('卖出', aliases={'sell', '售出', '卖出股票', '出售'}, only_to_me=False)
async def sell_stonk(session: nonebot.CommandSession):
    args = session.current_arg_text
    args = args.split()
    if len(args) != 2:
        await session.finish('用法是！卖出 股票代码 数量')

    ctx = session.ctx.copy()
    user_id = ctx['user_id']
    message_id = ctx['message_id']
    await session.finish(
        f'[CQ:reply,id={message_id}]'
        f'{get_attention()}' +
        await virtual_market.sell_stock(user_id, args[0], args[1], ctx=ctx)
    )


@nonebot.on_command('持仓', only_to_me=False)
async def my_stonks(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = ctx['user_id']

    arg = ctx['raw_message']
    is_same_guy = True
    if arg:
        try:
            user_id = re.findall(r'CQ:at,qq=(\d+)', arg)[0]
            is_same_guy = False
        except IndexError:
            user_id = user_id

    message_id = ctx['message_id']
    try:
        user_hold = await virtual_market.get_all_stonk_log_by_user(user_id, ctx=ctx if is_same_guy else None)
    except ClientConnectionError:
        await session.finish('加载失败，请重试。')
        return

    await session.finish(
        f'[CQ:reply,id={message_id}]' +
        f'[CQ:image,file=file:///'
        f'{await text_to_image(get_attention() + user_hold)}]'
    )


@nonebot.on_command('战绩', aliases={'炒股战绩', '龙虎榜'}, only_to_me=False)
async def stonk_stat_send(session: nonebot.CommandSession):
    try:
        leaderboard = await virtual_market.get_all_user_info(valid_time=60 * 60)
    except Exception as err:
        logger.error(f'战绩功能出错{err}')
        await session.finish('查询出错， 请重试。')
        return

    await session.finish(
        f'[CQ:image,file=file:///{await text_to_image(get_attention() + leaderboard)}]'
    )


@k_line.args_parser
@crypto_search.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('词呢！词呢！！KORA！！！')
