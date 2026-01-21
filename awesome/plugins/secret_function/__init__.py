from os import getcwd, listdir, path
from random import choice

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent, Message, ActionFailed, Bot
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from nonebot.params import CommandArg

from Services import global_rate_limiter, sail_data
from Services.deepinfra import DeepInfraAPI
from Services.rate_limiter import UserLimitModifier
from Services.util.common_util import HttpxHelperClient
from Services.util.ctx_utility import get_user_id
from Services.util.download_helper import download_image
from awesome.Constants import user_permission as perm
from awesome.Constants.user_permission import OWNER
from awesome.adminControl import get_privilege, user_control
from util.helper_util import construct_message_chain

CHUNK_SIZE = 450

deepinfra_api = DeepInfraAPI()
client = HttpxHelperClient()

sail_check = on_command('查上海')


@sail_check.handle()
async def check_sail_data(_bot: Bot, event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    key_word = args.extract_plain_text()
    uid, medal_name = key_word.split(' ', 1)
    _, text = await sail_data.check_if_uid_has_guard(uid, medal_name)

    message_id = event.message_id
    await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), text))


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
async def lingye_sing(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    user_id = event.get_user_id()

    if not get_privilege(user_id, perm.ADMIN):
        return

    if not user_control.get_user_privilege(user_id, perm.ADMIN):
        user_limit = UserLimitModifier(60 * 10, 1, True)
        rate_limiter_check_temp = await global_rate_limiter.user_limit_check(
            "AI_SING_DAILY", user_id, user_limit
        )
        if isinstance(rate_limiter_check_temp, str):
            logger.warning(f'User {user_id} has hit the rate limit: {rate_limiter_check_temp}')
            return

    if not args.extract_plain_text():
        file = choice(listdir(f'{getcwd()}/data/sing'))
    else:
        file = listdir(f'{getcwd()}/data/sing')[int(args.extract_plain_text())]

    await matcher.send(f'那就唱一首{file.split(".")[0]}')
    await matcher.finish(MessageSegment.record(file=path.join(getcwd(), 'data', 'sing', file)))
