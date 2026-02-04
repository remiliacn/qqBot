from os import getcwd, listdir, path
from random import choice

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent, Message, ActionFailed, Bot
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from nonebot.params import CommandArg

from Services import global_rate_limiter, sail_data
from Services import youtube_music_main_api
from Services.deepinfra import DeepInfraAPI
from Services.live_notification import GuardCheckResult
from Services.rate_limiter import RateLimitConfig
from Services.util.common_util import HttpxHelperClient
from Services.util.ctx_utility import get_user_id
from Services.util.download_helper import download_image
from awesome.Constants import user_permission as perm
from awesome.Constants.function_key import AI_SING_DAILY
from awesome.Constants.user_permission import OWNER
from awesome.adminControl import get_privilege
from util.helper_util import construct_message_chain

CHUNK_SIZE = 450

deepinfra_api = DeepInfraAPI()
client = HttpxHelperClient()

sail_check = on_command('查上海')


@sail_check.handle()
async def check_sail_data(_bot: Bot, event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    key_word = args.extract_plain_text()
    uid, medal_name = key_word.split(' ', 1)
    result: GuardCheckResult = await sail_data.check_if_uid_has_guard(uid, medal_name)

    message_id = event.message_id

    try:
        icon_message_segment = result.icon_url if result.icon_url else None
        await matcher.send(construct_message_chain(
            MessageSegment.reply(message_id),
            '用户头像：\n', icon_message_segment, '\n', result.text))
    except Exception as err:
        logger.error(f'Failed to send sail check result message, '
                     f'we are going to try without the icon image. {err.__class__}')

        await matcher.finish(construct_message_chain(
            MessageSegment.reply(message_id), result.text))


add_meme_cmd = on_command('加表情')


@add_meme_cmd.handle()
async def add_biaoqing(_bot: Bot, event: GroupMessageEvent, matcher: Matcher):
    user_id = get_user_id(event)
    if not get_privilege(user_id, OWNER):
        return

    image_is = extract_image_urls(event.original_message)
    if not image_is:
        await matcher.finish('我图呢？')
    try:
        for image in image_is:
            await download_image(image, f'{getcwd()}/data/biaoqing')
        else:
            await matcher.finish('搞定~')
    except ActionFailed as err:
        logger.error(f'Download meme failed: {err.__class__}')
        await matcher.finish('出问题力')


sing_lingye_cmd = on_command('灵夜唱歌')


@sing_lingye_cmd.handle()
@global_rate_limiter.rate_limit(func_name=AI_SING_DAILY, config=RateLimitConfig(user_time=60 * 10, user_count=1))
async def lingye_sing(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    user_id = event.get_user_id()

    if not get_privilege(user_id, perm.ADMIN):
        return

    if not args.extract_plain_text():
        file = choice(listdir(f'{getcwd()}/data/sing'))
    else:
        file = listdir(f'{getcwd()}/data/sing')[int(args.extract_plain_text())]

    await matcher.send(f'那就唱一首{file.split(".")[0]}')
    await matcher.finish(MessageSegment.record(file=path.join(getcwd(), 'data', 'sing', file)))


ytm_now_playing_cmd = on_command('在听啥')


@ytm_now_playing_cmd.handle()
async def ytm_now_playing(event: GroupMessageEvent, matcher: Matcher):
    message_id = event.message_id
    result = await youtube_music_main_api.what_ya_listening()
    if result.is_success:
        await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), result.message))

    await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), str(result.message)))


yt_next_cmd = on_command('切歌')


@yt_next_cmd.handle()
async def ytm_next_song(event: GroupMessageEvent, matcher: Matcher):
    message_id = event.message_id
    result = await youtube_music_main_api.cut_song()
    if result.is_success:
        await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), result.message))

    await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), str(result.message)))


yt_pick_cmd = on_command('点歌')


@yt_pick_cmd.handle()
async def ytm_pick_song(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    message_id = event.message_id
    search_term = args.extract_plain_text().strip()
    if not search_term:
        await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), '请输入歌名'))

    result = await youtube_music_main_api.search_and_add_to_next_queue(search_term)
    if result.is_success:
        await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), result.message))

    await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), str(result.message)))
