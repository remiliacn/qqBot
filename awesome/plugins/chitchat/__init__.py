from os import getcwd, listdir
from os.path import exists
from random import choice

from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.internal.matcher import Matcher
from nonebot.internal.params import Arg

from Services import global_rate_limiter
from Services.rate_limiter import RateLimitConfig
from Services.util.download_helper import download_image
from awesome.Constants import user_permission as perm
from awesome.Constants.function_key import CHITCHAT_GLOBAL
from awesome.Constants.plugins_command_constants import ADD_PIC_PROMPT, CHITCHAT_PIC_TYPES, CHITCHAT_PIC_DICT
from awesome.adminControl import get_privilege

add_more_pic_cmd = on_command('添加图片')

CHITCHAT_RATE_LIMIT = RateLimitConfig(user_time=60, user_count=1)


@add_more_pic_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def add_more_pic(_event: GroupMessageEvent, matcher: Matcher, args: Message = Arg()):
    if not (key_word := args.extract_plain_text()):
        await matcher.finish(ADD_PIC_PROMPT)

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
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def change_question_mark(event: GroupMessageEvent, matcher: Matcher):
    if not get_privilege(event.get_user_id(), perm.ADMIN):
        return

    await matcher.finish('¿?¿?')


useless_cmd = on_command('我什么都不行', aliases={'什么都不行', '都不行', '不行', '流泪猫猫头'})


@useless_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def useless_send(_event: GroupMessageEvent, matcher: Matcher):
    file = await get_random_file(f'{getcwd()}/data/dl/useless')
    await matcher.send(MessageSegment.image(file=file))


threat_cmd = on_command('威胁')


@threat_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def threat_send(_event: GroupMessageEvent, matcher: Matcher):
    file = await get_random_file(f'{getcwd()}/data/dl/weixie')
    await matcher.send(MessageSegment.image(file))


lemon_cmd = on_command('恰柠檬', aliases={'吃柠檬'})


@lemon_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def lemon_send(_event: GroupMessageEvent, matcher: Matcher):
    file = await get_random_file(f'{getcwd()}/data/dl/lemon')
    await matcher.send(MessageSegment.image(file=file))


pohai_cmd = on_command('迫害')


@pohai_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def send_pohai(_event: GroupMessageEvent, matcher: Matcher):
    file = await get_random_file(f'{getcwd()}/data/dl/pohai')
    await matcher.send(MessageSegment.image(file=file))


bksn_cmd = on_command('不愧是你', aliases={'bukui'})


@bksn_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def bu_kui_send(_event: GroupMessageEvent, matcher: Matcher):
    file = await get_random_file(f'{getcwd()}/data/dl/bukui')
    await matcher.send(MessageSegment.image(file=file))


peach_cmd = on_command('恰桃', aliases={'恰peach'})


@peach_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def send_peach(_event: GroupMessageEvent, matcher: Matcher):
    file = await get_random_file(f'{getcwd()}/data/dl/peach')
    await matcher.send(MessageSegment.image(file=file))


shebao_cmd = on_command('社保', aliases={'awsl'})


@shebao_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def she_bao(_event: GroupMessageEvent, matcher: Matcher):
    file = await get_random_file(f'{getcwd()}/data/dl/shebao')
    await matcher.send(MessageSegment.image(file=file))


otsukare_cmd = on_command('otsukare', aliases={'おつかれ', '辛苦了'})


@otsukare_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=CHITCHAT_GLOBAL, config=CHITCHAT_RATE_LIMIT, show_prompt=True, override_prompt='别刷了')
async def otsukare(_event: GroupMessageEvent, matcher: Matcher):
    file = await get_random_file(f'{getcwd()}/data/dl/otsukare')
    await matcher.send(MessageSegment.image(file=file))


async def get_random_file(path: str) -> str:
    if not exists(path):
        raise FileNotFoundError(f'No image found in default location: {path}')

    file = listdir(path)
    return path + '/' + choice(file)
