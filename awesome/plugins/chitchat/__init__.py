from os import getcwd, listdir
from os.path import exists
from random import choice

from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.internal.matcher import Matcher
from nonebot.internal.params import Arg
from nonebot.log import logger

from Services import global_rate_limiter
from Services.rate_limiter import UserLimitModifier
from Services.util.download_helper import download_image
from awesome.Constants import user_permission as perm
from awesome.Constants.plugins_command_constants import ADD_PIC_PROMPT, CHITCHAT_PIC_TYPES, CHITCHAT_PIC_DICT
from awesome.adminControl import get_privilege

add_more_pic_cmd = on_command('添加图片')


@add_more_pic_cmd.handle()
async def add_more_pic(_event: GroupMessageEvent, matcher: Matcher, args: Message = Arg()):
    if not (key_word := args.extract_plain_text()):
        matcher.finish(ADD_PIC_PROMPT)
    user_arg = key_word.split()

    if user_arg[0] not in CHITCHAT_PIC_TYPES:
        await matcher.finish('不是说了必须是其中一个了kora')

    path = CHITCHAT_PIC_DICT[args[0]]
    extracted_image_url = extract_image_urls(args)
    if extracted_image_url:
        _ = await download_image(extracted_image_url[0], path)
        await matcher.finish('图片已添加！')

    await matcher.finish('你发的smjb玩意……')


heartbeat_general_cmd = on_command('?', aliases={'？'})


@heartbeat_general_cmd.handle()
async def change_question_mark(event: GroupMessageEvent, matcher: Matcher):
    if not get_privilege(event.get_user_id(), perm.ADMIN):
        return

    await matcher.finish('¿?¿?')


useless_cmd = on_command('我什么都不行', aliases={'什么都不行', '都不行', '不行', '流泪猫猫头'})


@useless_cmd.handle()
async def useless_send(event: GroupMessageEvent, matcher: Matcher):
    await _chitchat_global_limit_check(event, matcher)
    file = await get_random_file(f'{getcwd()}/data/dl/useless')
    await matcher.send(MessageSegment.image(file=file))


threat_cmd = on_command('威胁')


@threat_cmd.handle()
async def threat_send(event: GroupMessageEvent, matcher: Matcher):
    await _chitchat_global_limit_check(event, matcher)
    file = await get_random_file(f'{getcwd()}/data/dl/weixie')
    await matcher.send(MessageSegment.image(file))


lemon_cmd = on_command('恰柠檬', aliases={'吃柠檬'})


@lemon_cmd.handle()
async def lemon_send(event: GroupMessageEvent, matcher: Matcher):
    await _chitchat_global_limit_check(event, matcher)
    file = await get_random_file(f'{getcwd()}/data/dl/lemon')
    await matcher.send(MessageSegment.image(file=file))


pohai_cmd = on_command('迫害')


@pohai_cmd.handle()
async def send_pohai(event: GroupMessageEvent, matcher: Matcher):
    await _chitchat_global_limit_check(event, matcher)
    file = await get_random_file(f'{getcwd()}/data/dl/pohai')
    await matcher.send(MessageSegment.image(file=file))


bksn_cmd = on_command('不愧是你', aliases={'bukui'})


@bksn_cmd.handle()
async def bu_kui_send(event: GroupMessageEvent, matcher: Matcher):
    await _chitchat_global_limit_check(event, matcher)
    file = await get_random_file(f'{getcwd()}/data/dl/bukui')
    await matcher.send(MessageSegment.image(file=file))


peach_cmd = on_command('恰桃', aliases={'恰peach'})


@peach_cmd.handle()
async def send_peach(event: GroupMessageEvent, matcher: Matcher):
    await _chitchat_global_limit_check(event, matcher)
    file = await get_random_file(f'{getcwd()}/data/dl/peach')
    await matcher.send(MessageSegment.image(file=file))


shebao_cmd = on_command('社保', aliases={'awsl'})


@shebao_cmd.handle()
async def she_bao(event: GroupMessageEvent, matcher: Matcher):
    await _chitchat_global_limit_check(event, matcher)
    file = await get_random_file(f'{getcwd()}/data/dl/shebao')
    await matcher.send(MessageSegment.image(file=file))


otsukare_cmd = on_command('otsukare', aliases={'おつかれ', '辛苦了'})


@otsukare_cmd.handle()
async def otsukare(event: GroupMessageEvent, matcher: Matcher):
    await _chitchat_global_limit_check(event, matcher)
    file = await get_random_file(f'{getcwd()}/data/dl/otsukare')
    await matcher.send(MessageSegment.image(file=file))


async def get_random_file(path: str) -> str:
    if not exists(path):
        raise FileNotFoundError(f'No image found in default location: {path}')

    file = listdir(path)
    return path + '/' + choice(file)


async def _chitchat_global_limit_check(event: GroupMessageEvent, matcher: Matcher):
    user_limit = UserLimitModifier(60, 1, True)
    user_id = event.get_user_id()
    rate_limiter_check_temp = await global_rate_limiter.user_limit_check(
        "CHITCHAT_GLOBAL", user_id, user_limit
    )
    if isinstance(rate_limiter_check_temp, str):
        logger.warning(f'User {user_id} has hit the rate limit: {rate_limiter_check_temp}')
        await matcher.finish('别刷了')
