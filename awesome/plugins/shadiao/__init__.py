import os
import random
import re
from typing import Annotated

import aiohttp
import nonebot
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Event, Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.exception import FinishedException
from nonebot.internal.matcher import Matcher
from nonebot.internal.params import ArgStr
from nonebot.message import event_preprocessor
from nonebot.params import CommandArg

from Services import ark_nights, shadiao, global_rate_limiter
from Services.util.common_util import HttpxHelperClient
from Services.util.ctx_utility import get_nickname, get_user_id, get_group_id
from awesome.Constants import user_permission as perm, group_permission
from awesome.Constants.function_key import ARKNIGHTS_PULLS, ARKNIGHTS_SINGLE_PULL, ARKNIGHTS_SIX_STAR_PULL, \
    YULU_CHECK, ARKNIGHTS_BAD_LUCK_PULL, POKER_GAME, SETU, QUESTION, HIT_XP, ROULETTE_GAME, HORSE_RACE
from awesome.adminControl import get_privilege, group_control, setu_function_control
from config import SUPER_USER
from util.helper_util import get_downloaded_quote_image_path, ark_helper, set_group_permission, construct_message_chain

arknights_api = ark_nights.ArkHeadhunt(times=10)
ark_pool_pity = ark_nights.ArknightsPity()

timeout = aiohttp.ClientTimeout(total=5)

OCR_DICT = {
    'zh': '中文',
    'en': '英文',
    'jp': '日语',
    'es': '西班牙语',
    'fr': '法语',
    'ru': '俄语',
    'ar': '阿拉伯语'
}

flatter = on_command('吹我')
clear_group = on_command('清空语录')
tranfer_quote = on_command('转移语录')
your_group_quote = on_command('你群语录', aliases={'你组语录', '语录'})
add_quote_cmd = on_command('添加语录')
ocr = on_command('图片识别')
how_lewd_cmd = on_command('你群有多色')
set_r18_cmd = on_command('设置R18')
ten_roll_cmd_arknights = on_command('方舟十连')
arknights_up = on_command('方舟up', aliases={'方舟UP'})
help_me_choose_cmd = on_command('帮我做选择')


@flatter.handle()
async def _do_joke_flatter(session: GroupMessageEvent):
    flatter_api = shadiao.Flatter()
    await flatter.send(flatter_api.get_flatter_result(session.get_user_id()))


@clear_group.handle()
async def clear_group_quotes(session: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not get_privilege(get_user_id(session), perm.OWNER):
        await matcher.finish()

    if not (group_id := args.extract_plain_text()):
        await matcher.finish('群号呢？')

    if group_control.clear_group_quote(group_id):
        await matcher.finish('Done!')

    await matcher.finish('啊这……群号不对啊……')


@tranfer_quote.handle()
async def transfer_group_quotes(session: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not get_privilege(get_user_id(session), perm.OWNER):
        await matcher.finish()

    group_id_arg = re.split(r'[,，\s+]', args.extract_plain_text())
    if len(group_id_arg) != 2:
        await matcher.finish('用法为！转移语录 目标群号，原群号')

    group_control.transfer_group_quote(group_id_arg[0], group_id_arg[1])
    await matcher.finish('Done')


@your_group_quote.handle()
async def get_group_quotes(session: GroupMessageEvent, matcher: Matcher):
    group_id = session.group_id
    permission_check_succeed = group_control.get_group_permission(group_id, group_permission.NLP)
    if not permission_check_succeed:
        await matcher.finish('本群的语录功能已被关闭，请联系群管理。')

    user_id = session.get_user_id()
    message_id = session.message_id

    rate_limiter_check = await global_rate_limiter.group_limit_check(
        'group_quote',
        group_id,
        time_period=15,
        function_limit=2)
    if isinstance(rate_limiter_check, str):
        await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), rate_limiter_check))

    nickname = session.sender.nickname

    setu_function_control.set_user_data(user_id, YULU_CHECK, nickname)
    await matcher.finish(MessageSegment.image(group_control.get_group_quote(group_id)))


@add_quote_cmd.handle()
async def add_group_quotes(session: GroupMessageEvent, matcher: Matcher):
    key_word = re.sub(r'.*?添加语录[\s\r\n]*', '', session.raw_message).strip()
    if '屑bot' in key_word.lower():
        await matcher.finish('爬')

    if session.current_arg_images:
        key_word = get_downloaded_quote_image_path(session.current_arg_images[0], f'{os.getcwd()}/data/lol')

        if key_word:
            group_control.add_quote(get_group_id(session), key_word)
            await matcher.finish(
                f'已添加！（当前总语录条数：{group_control.get_group_quote_count(get_group_id(session))})')


@ocr.handle()
async def ocr_image_test(session: GroupMessageEvent, matcher: Matcher):
    bot = nonebot.get_bot()
    msg: str = session.raw_message

    has_image = re.findall(r'[a-z0-9]+\.image', msg)
    if not has_image:
        await matcher.finish('无图片哼啊啊啊啊~')

    ocr_response = await bot.ocr_image(image=has_image[0])
    if 'texts' not in ocr_response:
        await matcher.finish('识别失败！')

    if not ocr_response['texts']:
        await matcher.finish('无可识别文字')

    text_list = ocr_response['texts']
    language = ocr_response['language']

    if language not in OCR_DICT:
        language = '其他小语种'
    else:
        language = OCR_DICT[language]

    response = f'已识别到{language}文字：\n'
    for element in text_list:
        response += element['text'] + '\n'

    await matcher.finish(response)


@event_preprocessor
async def message_preprocessing(event: Event):
    if not isinstance(event, GroupMessageEvent):
        return

    group_id = event.group_id
    user_id = event.user_id

    if group_id is not None:
        if not group_control.get_group_permission(group_id, group_permission.ENABLED) \
                and not get_privilege(event['user_id'], perm.OWNER):
            raise FinishedException('Group disabled')

        if user_id is not None:
            if get_privilege(user_id, perm.BANNED) and str(user_id) != str(SUPER_USER):
                raise FinishedException('User disabled')
    else:
        if str(user_id) != str(SUPER_USER):
            raise FinishedException('User disabled')


@how_lewd_cmd.handle()
async def get_setu_stat(bot: Bot, session: GroupMessageEvent):
    group_stat_dict = setu_function_control.get_group_usage_literal(get_group_id(session))
    rank = group_stat_dict['rank']
    delta = group_stat_dict['delta']
    yanche = group_stat_dict['yanche']
    ark_stat = group_stat_dict['pulls']
    group_xp = group_stat_dict["group_xp"]
    group_xp_literal = "本群最喜欢的XP为" + group_xp + "\n" if group_xp else ""
    ark_data = ''
    setu_notice = f'自统计功能实装以来，你组查了{group_stat_dict["setu"]}次色图！' \
                  f'{"位居色图查询排行榜的第" + str(rank) + "！" if rank != -1 else ""}\n' \
                  f'{group_xp_literal}' \
                  f'距离第{2 if rank == 1 else rank - 1}位相差{delta}次搜索！\n'

    yanche_notice = ('并且验车了' + str(yanche) + "次！\n") if yanche > 0 else ''
    if ark_stat['pulls'] != 0:
        ark_data += f'十连抽卡共{ark_stat["pulls"]}次，理论消耗合成玉{ark_stat["pulls"] * 6000}。抽到了：\n' \
                    f"3星{ark_stat['pulls3']}个，4星{ark_stat['pulls4']}个，" \
                    f"5星{ark_stat['pulls5']}个，6星{ark_stat['pulls6']}个"

    await bot.send_group_msg(group_id=session.group_id, message=setu_notice + yanche_notice + ark_data)


@set_r18_cmd.handle()
async def set_r18(session: GroupMessageEvent, matcher: Matcher, stats: Annotated[str, ArgStr()]):
    if not get_privilege(get_user_id(session), perm.WHITELIST):
        await matcher.finish('您无权进行该操作')

    set_group_permission(stats, session.group_id, group_permission.ALLOW_R18)
    await matcher.finish('Done!')


@ten_roll_cmd_arknights.handle()
async def ten_polls(bot: Bot, session: GroupMessageEvent):
    if get_privilege(get_user_id(session), perm.OWNER):
        arknights_api.get_randomized_results(98)

    else:
        offset = ark_pool_pity.get_offset_setting(get_group_id(session))
        arknights_api.get_randomized_results(offset)
        class_list = arknights_api.random_class
        six_star_count = class_list.count(6) + class_list.count(-1)
        if 6 in class_list or -1 in class_list:
            ark_pool_pity.reset_offset(get_group_id(session))

        five_star_count = class_list.count(5)

        data = {
            "6": six_star_count,
            "5": five_star_count,
            "4": class_list.count(4),
            "3": class_list.count(3)
        }

        nickname = get_nickname(session)

        if six_star_count == 0 and five_star_count == 0:
            setu_function_control.set_user_data(get_user_id(session), ARKNIGHTS_BAD_LUCK_PULL, nickname)

        setu_function_control.set_group_data(group_id=get_group_id(session), tag=ARKNIGHTS_PULLS, data=data)
        setu_function_control.set_group_data(group_id=get_group_id(session), tag=ARKNIGHTS_SINGLE_PULL)
        setu_function_control.set_user_data(get_user_id(session), ARKNIGHTS_SIX_STAR_PULL, six_star_count)

    qq_num = get_user_id(session)
    await bot.send_group_msg(
        group_id=session.group_id,
        message=construct_message_chain(MessageSegment.at(qq_num), arknights_api.__str__()))


@arknights_up.got(
    'key_word',
    prompt='使用方法：！方舟up 干员名 星级（数字）是否限定(y/n) 是否二级限定(y/n)')
async def up_ten_polls(session: GroupMessageEvent, matcher: Matcher,
                       key_word: Annotated[str, ArgStr('key_word')]):
    if not get_privilege(get_user_id(session), perm.OWNER):
        await matcher.finish('您无权使用本功能')

    args = key_word.split()
    validation = ark_helper(args)
    if validation:
        await matcher.finish(validation)

    await matcher.finish(
        arknights_api.up_op(
            args[0],
            args[1],
            args[2].lower() == 'y',
            args[3].lower() == 'y'
        )
    )


@help_me_choose_cmd.handle()
async def do_mcq(bot: Bot, session: GroupMessageEvent):
    raw_message = session.raw_message

    question_count = 1
    if len(raw_message.split()) == 2:
        try:
            question_count = int(raw_message.split()[1])
        except TypeError:
            question_count = 1

    answer = '选'
    for i in range(question_count):
        answer += f'{chr(random.randint(65, 68))}'

    await bot.send_group_msg(group_id=session.group_id, message=answer + '。')


up_reset_cmd = on_command('方舟up重置', aliases={'方舟UP重置', 'UP重置'})


@up_reset_cmd.handle()
async def reset_ark_up(session: GroupMessageEvent, matcher: Matcher):
    if not get_privilege(get_user_id(session), perm.OWNER):
        await matcher.finish('您无权使用本功能')

    arknights_api.clear_ups()
    await matcher.finish('Done!')


add_arknights_operator_cmd = on_command('添加干员')


@add_arknights_operator_cmd.got('key_word', prompt='使用方法：！方舟up 干员名 星级（数字）')
async def add_ark_op(session: GroupMessageEvent, matcher: Matcher,
                     key_word: Annotated[str, ArgStr('key_word')]):
    if not get_privilege(get_user_id(session), perm.OWNER):
        await matcher.finish('您无权使用本功能')

    args = key_word.split()
    validation = ark_helper(args)
    if validation:
        await matcher.finish(validation)

    await matcher.finish(arknights_api.add_op(args[0], args[1]))


def get_stat(key: str, lis: dict) -> (int, int):
    return lis[key]['count'] if key in lis else 0, lis[key]['rank'] if key in lis else 0


stat_cmd = on_command('统计')


@stat_cmd.handle()
async def stat_player(bot: Bot, session: GroupMessageEvent):
    user_id = get_user_id(session)
    stat_dict = setu_function_control.get_user_data(user_id)
    if not stat_dict:
        await bot.send_group_msg(
            group_id=session.group_id,
            message=construct_message_chain(MessageSegment.at(user_id), '还没有数据哦~'))
    else:
        poker_win, poker_rank = get_stat(POKER_GAME, stat_dict)
        six_star_pull, six_star_rank = get_stat(ARKNIGHTS_SIX_STAR_PULL, stat_dict)
        setu_stat, setu_rank = get_stat(SETU, stat_dict)
        question, question_rank = get_stat(QUESTION, stat_dict)
        unlucky, unlucky_rank = get_stat(ARKNIGHTS_BAD_LUCK_PULL, stat_dict)
        same, same_rank = get_stat(HIT_XP, stat_dict)
        roulette, roulette_rank = get_stat(ROULETTE_GAME, stat_dict)
        horse_race, horse_rank = get_stat(HORSE_RACE, stat_dict)
        yulu, yulu_rank = get_stat(YULU_CHECK, stat_dict)

        await bot.send_group_msg(
            group_id=session.group_id,
            message=construct_message_chain(
                f'用户', MessageSegment.at(user_id), '：\n',
                f'比大小赢得{poker_win}次（排名第{poker_rank}）\n' if poker_win != 0 else '',
                f'方舟抽卡共抽到{six_star_pull}个六星干员（排名第{six_star_rank}）\n ' if six_star_pull != 0 else '',
                f'紫气东来{unlucky}次（排名第{unlucky}）\n' if unlucky != 0 else '',
                f'查了{setu_stat}次的色图！（排名第{setu_rank}）\n' if setu_stat != 0 else '',
                f'问了{question}次问题（排名第{question_rank}）\n' if question != 0 else '',
                f'和bot主人 臭 味 相 投{same}次（排名第{same_rank}）\n' if same != 0 else '',
                f'轮盘赌被处死{roulette}次（排名第{roulette_rank}）\n' if roulette != 0 else '',
                f'赛马获胜{horse_race}次（排名第{horse_rank}）\n' if horse_race != 0 else '',
                f'查询语录{yulu}次（排名第{yulu_rank}）\n' if yulu != 0 else ''))


xp_stat_cmd = on_command('统计xp')


@xp_stat_cmd.handle()
async def get_xp_stat_data(matcher: Matcher):
    xp_stat = setu_function_control.get_xp_data()
    response = ''
    for item in xp_stat:
        response += f'关键词：{item[0]} --> Hit: {item[1]}\n'

    await matcher.finish(response)


entertain_switch_cmd = on_command('娱乐开关')


# noinspection PyTestUnpassedFixture
@entertain_switch_cmd.got('group_id', prompt='请输入要禁用所有功能的qq群')
async def entertain_switch(session: GroupMessageEvent, matcher: Matcher,
                           group_id: Annotated[str, ArgStr('group_id')]):
    id_num = str(get_user_id(session))
    if not get_privilege(id_num, perm.WHITELIST):
        await matcher.finish('您无权进行该操作')

    if not str(group_id).isdigit():
        await matcher.finish('这不是qq号哦~')

    if group_control.get_group_permission(group_id, group_permission.BANNED):
        group_control.set_group_permission(group_id, group_permission.BANNED, False)
        await matcher.finish('已禁用娱乐功能！')
    else:
        group_control.set_group_permission(group_id, group_permission.BANNED, True)
        await matcher.finish('已开启娱乐功能！')


zui_chou_cmd = on_command('嘴臭一个', aliases={'骂我', '你再骂', '小嘴抹蜜', '嘴臭一下', '机器人骂我'})


@zui_chou_cmd.handle()
async def zui_chou():
    await zui_chou_cmd.finish('功能已停用。')


chp_cmd = on_command('彩虹屁', aliases={'拍个马屁', '拍马屁', '舔TA'})


@chp_cmd.handle()
async def chp(session: GroupMessageEvent, matcher: Matcher):
    await matcher.finish(await get_lab_responses('https://api.shadiao.pro/chp', session.message_id))


fkxqs_cmd = on_command('疯狂星期四')


@fkxqs_cmd.handle()
async def fkxqs(session: GroupMessageEvent, matcher: Matcher):
    await matcher.finish(await get_lab_responses('https://api.shadiao.pro/kfc', session.message_id))


async def get_lab_responses(url: str, message_id: int):
    client = HttpxHelperClient()
    json_data = await client.get(url)
    if json_data.status_code != 200:
        return '现在出不来'

    json_data = json_data.json()
    return construct_message_chain(
        MessageSegment.reply(message_id), json_data['data']['text'].replace('\u200b', ''))
