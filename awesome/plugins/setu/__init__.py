from os import path
from random import choice
from re import split
from time import time
from typing import Union, List

from nonebot import get_plugin_config, on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, PrivateMessageEvent, MessageSegment, Bot
from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from nonebot.params import CommandArg
from pixivpy3 import PixivError
from pixivpy3.utils import ParsedJson

from Services import global_rate_limiter
from Services.pixiv_word_cloud import get_word_cloud_img
from Services.util.common_util import compile_forward_message, autorevoke_message, get_if_has_at_and_qq, \
    slight_adjust_pic_and_get_path
from Services.util.ctx_utility import get_group_id, get_user_id, get_nickname
from Services.util.download_helper import download_image
from Services.util.sauce_nao_helper import sauce_helper
from awesome.Constants import user_permission as perm, group_permission
from awesome.Constants.function_key import SETU, TRIGGER_BLACKLIST_WORD, HIT_XP, WORDCLOUD
from awesome.Constants.path_constants import DL_PATH, PIXIV_PIC_PATH
from awesome.Constants.plugins_command_constants import PROMPT_FOR_KEYWORD
from awesome.adminControl import setu_function_control, get_privilege, group_control, user_control
from awesome.plugins.setu.pixiv_service import pixiv_service
from awesome.plugins.setu.rate_limit_helper import SETU_RATE_LIMIT, XP_CHECK_RATE_LIMIT, \
    WORDCLOUD_RATE_LIMIT
from awesome.plugins.setu.setu_utilties import download_gif
from awesome.plugins.setu.setuconfig import SetuConfig
from config import SUPER_USER
from util.helper_util import anime_reverse_search_response, set_group_permission, construct_message_chain

config = get_plugin_config(SetuConfig)

FRIENDLY_REMINDER = '\n你知道么~你可以使用你的p站uid丢人了（不是w\n' \
                    '使用方式：!设置P站 P站数字ID \n' \
                    '（进入自己的用户页面，你会看到url后面跟着一串数字）'


class SetuRequester:
    def __init__(
            self, event: GroupMessageEvent, has_id: bool,
            pixiv_id: Union[str, int], xp_result: list,
            requester_qq: Union[str, int], request_search_qq: Union[str, int]
    ):
        self.nickname = get_nickname(event)
        self.group_id = get_group_id(event)
        self.pixiv_id = pixiv_id
        self.has_id = has_id
        self.xp_result = xp_result
        self.requester_qq = str(requester_qq)
        self.search_target_qq = str(request_search_qq)


set_pixiv_cmd = on_command('设置P站', aliases={'设置p站', 'p站设置'})


@set_pixiv_cmd.handle()
async def set_user_pixiv(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    arg = args.extract_plain_text()
    if not arg:
        await matcher.finish('把你P站数字ID给我交了kora！')

    user_id = get_user_id(event)
    nickname = get_nickname(event)

    try:
        arg = int(arg)
    except ValueError:
        await matcher.finish('要的数字ID谢谢~')

    if setu_function_control.set_user_pixiv(user_id, arg, nickname):
        await matcher.finish('已设置！')

    await matcher.finish('不得劲啊你这……')


check_setu_stat_cmd = on_command('色图数据')


@check_setu_stat_cmd.handle()
async def get_setu_stat(_event: GroupMessageEvent, matcher: Matcher):
    setu_stat = setu_function_control.get_setu_usage()
    setu_high_freq_keyword = setu_function_control.get_high_freq_keyword()
    setu_high_freq_keyword_to_string = "\n".join(f"{x[0]}: {x[1]}次" for x in setu_high_freq_keyword)
    await matcher.finish(f'色图功能共被使用了{setu_stat}次\n'
                         f'被查最多的关键词前10名为：\n{setu_high_freq_keyword_to_string}')


check_group_xp_cmd = on_command('查询本群xp', aliases={'查询本群XP', '本群XP'})


@check_group_xp_cmd.handle()
async def fetch_group_xp(event: GroupMessageEvent, matcher: Matcher):
    group_id = get_group_id(event)
    group_xp = setu_function_control.get_group_xp(group_id)

    if not group_xp:
        await matcher.finish('本群还无数据哦~')

    await matcher.finish(f'本群XP查询第一名为{group_xp[0][0]} -> {group_xp[0][1]}')


get_setu_freq_cmd = on_command('词频')


@get_setu_freq_cmd.handle()
async def get_setu_stat(_event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not (arg := args.extract_plain_text()):
        await matcher.finish('查啥词啊喂！！')

    await matcher.finish(setu_function_control.get_keyword_usage_literal(arg))


set_blacklist_group_cmd = on_command('设置色图禁用')


@set_blacklist_group_cmd.handle()
async def set_black_list_group(
        event: GroupMessageEvent | PrivateMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    user_id = get_user_id(event)
    if not get_privilege(user_id, perm.ADMIN):
        await matcher.finish('无权限')

    message = args.extract_plain_text()
    if isinstance(event, PrivateMessageEvent):
        args = message.split()
        if len(args) != 2:
            await matcher.finish('参数错误，应为！设置色图禁用 群号 设置，或在本群内做出设置')

        group_id = args[0]
        if not str(group_id).isdigit():
            await matcher.finish('提供的参数非qq群号')

        message = args[1]

    else:
        group_id = get_group_id(event)

    setting = set_group_permission(message, group_id, group_permission.BANNED)
    await matcher.finish(f'Done! {setting}')


pixiv_send_cmd = on_command('色图', aliases={'来张色图', '涩图'})


@pixiv_send_cmd.handle()
@global_rate_limiter.rate_limit(
    func_name=SETU, config=SETU_RATE_LIMIT, show_prompt=True, override_prompt='别色了，休息会儿吧。')
async def pixiv_send(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, matcher: Matcher,
                     args: Message = CommandArg()):
    nickname = get_nickname(event)
    message_id, allow_r18, user_id, group_id = _get_info_for_setu(event)

    if not get_privilege(user_id, perm.OWNER):
        if group_control.get_group_permission(group_id, group_permission.BANNED):
            await matcher.finish('管理员已设置禁止该群接收色图。如果确认这是错误的话，请联系bot制作者')

    monitored = False
    if group_id == -1 and not get_privilege(user_id, perm.WHITELIST):
        await matcher.finish('我主人还没有添加你到信任名单哦。请找BOT制作者要私聊使用权限~')

    if not pixiv_service.ensure_auth():
        await matcher.finish('Pixiv认证失败，请稍后再试')

    if not (key_word := args.extract_plain_text()):
        await matcher.finish(PROMPT_FOR_KEYWORD)

    multiplier = setu_function_control.get_bad_word_penalty(key_word)
    if multiplier > 0:
        await _do_blacklist_keyword_process(bot, key_word, matcher, nickname, user_id)
        await matcher.finish()

    if key_word in setu_function_control.get_monitored_keywords():
        monitored = True
        if group_id == -1:
            setu_function_control.set_user_data(user_id, HIT_XP, nickname)
            setu_function_control.set_user_xp(user_id, key_word, nickname)

    await _handle_special_keyword(key_word, matcher)

    json_result = await pixiv_service.search_illust(key_word)
    if json_result is None:
        await matcher.finish('pixiv连接出错了！')

    if 'error' in json_result:
        if not pixiv_service.reset_auth():
            await matcher.finish('pixiv认证失败，请稍后再试')
        json_result = await pixiv_service.search_illust(key_word)
        if json_result is None:
            await matcher.finish('pixiv连接出错了！')

    if key_word.isdigit():
        illust = pixiv_service.get_illust_detail(key_word)
        if illust is None:
            await matcher.finish('获取图片详情失败')
        json_result = None
    else:
        json_result, key_word = await _setu_analyze_user_input(key_word, matcher)

        setu_function_control.track_keyword(key_word)
        illust = choice(json_result.illusts)

    is_work_r18 = illust.sanity_level == 6
    if not allow_r18:
        if key_word.isdigit() and is_work_r18:
            await matcher.finish('太色了发不了（')

        if json_result is not None:
            illust, is_work_r18 = \
                await _attempt_to_extract_sfw_pixiv_img(illust, json_result, key_word, matcher)

    start_time = time()
    setu_file_path = await _download_pixiv_image_helper(illust)

    if not setu_file_path:
        await matcher.finish('开摆！')

    if not is_work_r18:
        message = construct_message_chain(
            MessageSegment.reply(message_id),
            f'Pixiv ID: {illust.id}\n',
            MessageSegment.image(setu_file_path),
            f'Download Time: {(time() - start_time):.2f}s')

    elif is_work_r18 and (group_id == -1 or allow_r18):
        message = construct_message_chain(
            MessageSegment.reply(message_id),
            f'芜湖~好图来了ww\n'
            f'Pixiv ID: {illust.id}\n'
            f'关键词：{key_word}\n',
            MessageSegment.image(setu_file_path),
            f'Download Time: {(time() - start_time):.2f}s')

    else:
        message = construct_message_chain('图片发送失败！')

    if is_work_r18:
        await autorevoke_message(
            bot, event.group_id, 'normal', construct_message_chain(message), 30)
    else:
        await matcher.send(message)

    logger.info(f"sent image on path: {setu_file_path}")
    await _setu_data_collection(event, key_word, monitored, setu_file_path, illust, bot=bot)


async def _handle_special_keyword(key_word: str, matcher: Matcher):
    if '色图' in key_word:
        await matcher.finish(
            MessageSegment.image(
                path.join(DL_PATH, 'QQ图片20191013212223.jpg')
            )
        )
    elif '屑bot' in key_word:
        await matcher.finish('你屑你🐴呢')


async def _attempt_to_extract_sfw_pixiv_img(
        illust, json_result: ParsedJson | list, key_word: str, matcher: Matcher):
    is_work_r18 = getattr(illust, 'sanity_level', 0) == 6

    if is_work_r18 and key_word.isdigit():
        await matcher.finish('太色了发不了（')

    illusts = json_result.illusts if hasattr(json_result, 'illusts') else (json_result or [])

    if is_work_r18:
        safe_illusts = [x for x in illusts if getattr(x, 'sanity_level', 0) < 6]
        if not safe_illusts:
            await matcher.finish('太色了发不了（')

        illust = choice(safe_illusts)
        is_work_r18 = getattr(illust, 'sanity_level', 0) == 6

    return illust, is_work_r18


async def _setu_analyze_user_input(key_word: str, matcher: Matcher) -> tuple[ParsedJson, str]:
    if 'user=' in key_word:
        json_result, key_word = pixiv_service.search_by_username(key_word)
        if isinstance(json_result, str):
            await matcher.finish(json_result)
    else:
        json_result = await pixiv_service.search_illust(key_word)
        if json_result is None:
            await matcher.finish('pixiv连接出错了！')

    if not json_result.illusts or len(json_result.illusts) < 4:
        logger.warning(f"未找到图片, keyword = {key_word}")
        await matcher.finish(f"{key_word}无搜索结果或图片过少……")

    return json_result, key_word


async def _do_blacklist_keyword_process(bot: Bot, key_word: str, matcher: Matcher, nickname: str, user_id: str):
    setu_function_control.set_user_data(user_id, TRIGGER_BLACKLIST_WORD, nickname)
    if setu_function_control.get_user_data_by_tag(
            user_id, TRIGGER_BLACKLIST_WORD) >= config.IF_REPEAT_BAN_COUNT:
        user_control.set_user_privilege(user_id, 'BANNED', True)
        await matcher.send(f'用户{user_id}已被封停机器人使用权限')
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=f'User {user_id} has been banned for triggering prtection. Keyword = {key_word}'
        )

    else:
        await matcher.send('我劝这位年轻人好自为之，管理好自己的XP，不要污染图池')
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=f'User {user_id} triggered protection mechanism. Keyword = {key_word}'
        )


async def _setu_data_collection(
        event: GroupMessageEvent | PrivateMessageEvent, key_word: str,
        monitored: bool, setu_file_path: str, illust=None, bot=None):
    is_group = isinstance(event, GroupMessageEvent)
    group_id = get_group_id(event) if is_group else -1

    if is_group:
        setu_function_control.set_group_data(group_id, SETU)

    nickname = get_nickname(event)
    user_id = get_user_id(event)
    setu_function_control.set_user_data(user_id, SETU, nickname)

    key_word_list = [
        k.strip() for k in split(r'[\s\u3000,]+', key_word or '')
        if k.strip() and not k.strip().isdigit()
    ]
    for keyword in key_word_list:
        setu_function_control.set_user_xp(user_id, keyword, nickname)
        if is_group:
            setu_function_control.set_group_xp(group_id, keyword)

    if illust is not None:
        raw_tags = getattr(illust, 'tags', []) or []
        tags_to_process = []
        for tag in raw_tags:
            tag_name = (tag.get('name') if isinstance(tag, dict) else getattr(tag, 'name', '')) or ''
            tag_name = tag_name.strip()
            if tag_name and tag_name not in setu_function_control.blacklist_freq_keyword:
                tags_to_process.append(tag_name)
            if len(tags_to_process) >= 5:
                break

        for tag_name in tags_to_process:
            if is_group:
                setu_function_control.set_group_xp(group_id, tag_name)
            setu_function_control.set_user_xp(user_id, tag_name, nickname)

    if monitored and not get_privilege(user_id, perm.OWNER):
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=construct_message_chain(
                f'图片来自：{nickname}\n'
                f'查询关键词:{key_word}\n'
                f'Pixiv ID: {illust.id}\n',
                MessageSegment.image(setu_file_path))
        )


def _validate_user_pixiv_id_exists_and_return_id(
        event: GroupMessageEvent | PrivateMessageEvent,
        session: Message = CommandArg()):
    arg = session.extract_plain_text()
    has_at_qq, at_qq = get_if_has_at_and_qq(event)

    if arg.isdigit():
        search_target_qq = arg
    elif has_at_qq:
        search_target_qq = at_qq
    else:
        search_target_qq = get_user_id(event)

    search_target_qq = int(search_target_qq)
    pixiv_id = setu_function_control.get_user_pixiv(search_target_qq)

    return pixiv_id != -1, search_target_qq, pixiv_id


get_user_xp_wordcloud_cmd = on_command('P站词云')


@get_user_xp_wordcloud_cmd.handle()
@global_rate_limiter.rate_limit(func_name=WORDCLOUD, config=WORDCLOUD_RATE_LIMIT, show_prompt=False)
async def get_user_xp_wordcloud(bot: Bot, event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    group_id = get_group_id(event)

    if not pixiv_service.ensure_auth():
        await matcher.finish('Pixiv认证失败，请稍后再试')

    has_id, search_target_qq, pixiv_id = _validate_user_pixiv_id_exists_and_return_id(event, args)
    if not has_id:
        await matcher.finish('无法生成词云，请设置P站ID，设置方法：!设置P站 P站数字ID')

    await matcher.send('少女祈祷中……生成词云可能会占用大概1分钟的时间……')

    cloud_img_path = ''
    try:
        cloud_img_path = await get_word_cloud_img(pixiv_service.api, pixiv_id)
    except PixivError:
        await matcher.finish('P站请求失败！请重新使用本指令！')

    if not cloud_img_path:
        await matcher.finish('生成词云失败！')

    message_id = event.message_id
    messages = compile_forward_message(
        event.self_id, [MessageSegment.reply(message_id),
                        MessageSegment.image(cloud_img_path)])

    await bot.send_group_forward_msg(group_id=group_id, messages=messages)


check_someone_xp_cmd = on_command('看看XP', aliases={'看看xp'})


@check_someone_xp_cmd.handle()
@global_rate_limiter.rate_limit(func_name=HIT_XP, config=XP_CHECK_RATE_LIMIT, show_prompt=False)
async def get_user_xp_data_with_at(
        bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    group_id = get_group_id(event)
    user_id = get_user_id(event)

    if group_id != -1 and not get_privilege(user_id, perm.OWNER):
        if group_control.get_group_permission(group_id, group_permission.BANNED):
            return

    if group_id == -1 and not get_privilege(user_id, perm.WHITELIST):
        await matcher.finish('我主人还没有添加你到信任名单哦。请找BOT制作者要私聊使用权限~')

    message_id = event.message_id
    has_id, search_target_qq, pixiv_id = _validate_user_pixiv_id_exists_and_return_id(event, args)
    xp_result = setu_function_control.get_user_xp(search_target_qq)
    if not has_id and not xp_result:
        await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), FRIENDLY_REMINDER))

    xp_information = SetuRequester(event, has_id, pixiv_id, xp_result, user_id, search_target_qq)
    result = await _get_xp_information(xp_information, matcher)

    messages = construct_message_chain(([MessageSegment.reply(message_id)]
                                        + result
                                        + MessageSegment.text(f'\n{FRIENDLY_REMINDER if not has_id else ""}')))
    await autorevoke_message(bot, group_id, 'normal', messages, 30)


async def _get_xp_information(xp_information: SetuRequester, matcher: Matcher) -> List[MessageSegment]:
    response: List[MessageSegment] = []
    json_result = []
    try:
        if xp_information.has_id:
            json_result = pixiv_service.get_user_bookmark_random(int(xp_information.pixiv_id))

        if not json_result or not json_result.illusts:
            json_result = await pixiv_service.search_illust(xp_information.xp_result[0])
    except PixivError:
        return [MessageSegment.text('P站抽风了，请重试。')]

    json_result = json_result.illusts
    if not json_result:
        return [MessageSegment.text('不是吧~你P站都不收藏图的么（')]

    illust = choice(json_result)
    start_time = time()
    setu_file_path = await _download_pixiv_image_helper(illust)
    allow_r18 = xp_information.group_id != -1 and group_control.get_group_permission(
        xp_information.group_id, group_permission.ALLOW_R18)

    if not allow_r18:
        illust, is_r18 = await _attempt_to_extract_sfw_pixiv_img(illust, json_result, '', matcher)

    nickname = xp_information.nickname
    is_group = xp_information.group_id != -1

    if is_group:
        setu_function_control.set_group_data(xp_information.group_id, SETU)

    target_user_id = str(xp_information.search_target_qq)
    requester_user_id = str(xp_information.requester_qq)
    target_nickname = nickname if target_user_id == requester_user_id else ""

    raw_tags = (illust.get('tags') if isinstance(illust, dict) else getattr(illust, 'tags', [])) or []
    tags_to_process = []
    for tag in raw_tags:
        tag_name = (tag.get('name') if isinstance(tag, dict) else getattr(tag, 'name', '')) or ''
        tag_name = tag_name.strip()
        if tag_name and tag_name not in setu_function_control.blacklist_freq_keyword:
            tags_to_process.append(tag_name)
        if len(tags_to_process) >= 5:
            break

    for tag_name in tags_to_process:
        setu_function_control.set_user_xp(target_user_id, tag_name, target_nickname)
        setu_function_control.track_keyword(tag_name)
        if is_group:
            setu_function_control.set_group_xp(xp_information.group_id, tag_name)

    response += construct_message_chain(
        f'标题：{illust.title}\n'
        f'Pixiv ID： {illust.id}\n'
        f'画师：{illust["user"]["name"]}\n',
        MessageSegment.image(setu_file_path),
        f'Download Time: {(time() - start_time):.2f}s',
        f'\nTA最喜欢的关键词是{xp_information.xp_result[0]}'
        f'，已经查询了{xp_information.xp_result[1]}次。' if xp_information.xp_result else ''
    )

    setu_function_control.set_user_data(xp_information.requester_qq, SETU, nickname)
    return response


async def _download_pixiv_image_helper(illust) -> str:
    if illust.type != 'ugoira':
        return await _handle_normal_illust_download(illust)

    ugoira_data = pixiv_service.get_ugoira_metadata(illust.id)
    if not ugoira_data:
        return ''

    url_list = ugoira_data.ugoira_metadata.zip_urls.medium
    duration = ugoira_data.ugoira_metadata.frames[0].delay
    gif_path = await download_gif(url_list, illust.user.name + '_' + illust.title, duration)

    logger.success(f'Gif path done: {gif_path}')
    return gif_path if gif_path else ''


async def _handle_normal_illust_download(illust):
    if illust['meta_single_page']:
        if 'original_image_url' in illust['meta_single_page']:
            image_url = illust.meta_single_page['original_image_url']
        else:
            image_url = illust.image_urls['medium']
    else:
        if 'meta_pages' in illust:
            image_url_list = illust.meta_pages
            illust = choice(image_url_list)

        image_urls = illust.image_urls
        image_url = image_urls['original'] if 'original' in image_urls else \
            image_urls['large'] if 'large' in image_urls else \
                image_urls['medium'] if 'medium' in image_urls else \
                    image_urls['square_medium']
    logger.info(f"{illust.title}: {image_url}, {illust.id}")
    setu_file_path = PIXIV_PIC_PATH
    try:
        setu_file_path = await download_image(
            image_url, setu_file_path, headers={'Referer': 'https://app-api.pixiv.net/'})
    except Exception as err:
        logger.info(f'Download image error: {err}')
        return ''
    edited_path = await slight_adjust_pic_and_get_path(setu_file_path)
    logger.info("PATH = " + edited_path)
    return edited_path


reverse_search_manual_cmd = on_command('搜图')


@reverse_search_manual_cmd.handle()
async def reverse_image_search(_event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    args = args.get('image')
    if args:
        url: MessageSegment = args[0]
        logger.info(f'URL extracted: {url.data["url"]}')
        url = url.data["url"]
        try:
            response_data = await sauce_helper(url)
            if not response_data:
                response = f'图片无法辨别的说！'
            else:
                response = anime_reverse_search_response(response_data)

            await matcher.finish(response)
        except Exception as err:
            logger.warning(f'Error when reverse searching image data {err}')

        return
    else:
        await matcher.finish('¿')


def _get_info_for_setu(event: GroupMessageEvent):
    message_id = event.message_id

    group_id = get_group_id(event)
    allow_r18 = group_control.get_group_permission(group_id, group_permission.ALLOW_R18)
    user_id = get_user_id(event)

    return message_id, allow_r18, user_id, group_id
