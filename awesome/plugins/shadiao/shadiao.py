import os
import random
import re

import aiocqhttp.event
import aiohttp
import nonebot
from aiocqhttp import MessageSegment
from nonebot.message import CanceledException
from nonebot.plugin import PluginManager

from Services import ark_nights, shadiao, pcr_news
from Services.util.common_util import HttpxHelperClient
from Services.util.ctx_utility import get_nickname, get_user_id, get_group_id, get_message_id
from awesome.Constants import user_permission as perm, group_permission
from awesome.Constants.function_key import ARKNIGHTS_PULLS, ARKNIGHTS_SINGLE_PULL, ARKNIGHTS_SIX_STAR_PULL, \
    YULU_CHECK, ARKNIGHTS_BAD_LUCK_PULL, POKER_GAME, SETU, QUESTION, HIT_XP, ROULETTE_GAME, HORSE_RACE
from awesome.plugins.util.helper_util import get_downloaded_image_path, ark_helper, set_group_permission
from config import SUPER_USER
from qq_bot_core import admin_group_control, global_rate_limiter
from qq_bot_core import user_control_module, setu_control, weeb_learning

pcr_api = pcr_news.GetPCRNews()
arknights_api = ark_nights.ArkHeadhunt(times=10)
ark_pool_pity = ark_nights.ArknightsPity()

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)
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


@nonebot.on_command('吹我', only_to_me=False)
async def do_joke_flatter(session: nonebot.CommandSession):
    flatter_api = shadiao.Flatter()
    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)
    await session.send(flatter_api.get_flatter_result(user_id))


@nonebot.on_command('清空语录', only_to_me=False)
async def clear_group_quotes(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.OWNER):
        await session.finish()

    group_id = session.get('group_id', prompt='群号？')
    if admin_group_control.clear_group_quote(group_id):
        await session.finish('Done!')

    await session.finish('啊这……群号不对啊……')


@nonebot.on_command('转移语录', only_to_me=False)
async def transfer_group_quotes(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.OWNER):
        await session.finish()

    group_id_arg = re.split(r'[,，]', session.current_arg_text)
    if len(group_id_arg) != 2:
        await session.finish('用法为！转移语录 目标群号，原群号')

    admin_group_control.transfer_group_quote(group_id_arg[0], group_id_arg[1])
    await session.finish('Done')


@nonebot.on_command('你群语录', aliases=('你组语录', '语录'), only_to_me=False)
async def get_group_quotes(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish()

    user_id = get_user_id(ctx)
    message_id = ctx['message_id']

    rate_limiter_check = await global_rate_limiter.group_limit_check(
        'group_quote',
        get_group_id(ctx),
        time_period=15,
        function_limit=2)
    if isinstance(rate_limiter_check, str):
        await session.finish(f'[CQ:reply,id={message_id}]{rate_limiter_check}')

    nickname = get_nickname(ctx)

    setu_control.set_user_data(user_id, YULU_CHECK, nickname)
    await session.finish(admin_group_control.get_group_quote(get_group_id(ctx)))


@nonebot.on_command('添加语录', only_to_me=False)
async def add_group_quotes(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish()

    key_word = re.sub(r'.*?添加语录[\s\r\n]*', '', ctx['raw_message']).strip()
    if '屑bot' in key_word.lower():
        await session.finish('爬')

    if session.current_arg_images:
        key_word = get_downloaded_image_path(session.current_arg_images[0], f'{os.getcwd()}/data/lol')

        if key_word:
            admin_group_control.add_quote(get_group_id(ctx), key_word)
            await session.finish(
                f'已添加！（当前总语录条数：{admin_group_control.get_group_quote_count(get_group_id(ctx))})')


@nonebot.on_command('图片识别', only_to_me=False)
async def ocr_image_test(session: nonebot.CommandSession):
    bot = nonebot.get_bot()
    ctx = session.ctx.copy()
    msg: str = ctx['raw_message']

    has_image = re.findall(r'[a-z0-9]+\.image', msg)
    if not has_image:
        await session.finish('无图片哼啊啊啊啊~')

    ocr_response = await bot.ocr_image(image=has_image[0])
    if 'texts' not in ocr_response:
        await session.finish('识别失败！')

    if not ocr_response['texts']:
        await session.finish('无可识别文字')

    text_list = ocr_response['texts']
    language = ocr_response['language']

    if language not in OCR_DICT:
        language = '其他小语种'
    else:
        language = OCR_DICT[language]

    response = f'已识别到{language}文字：\n'
    for element in text_list:
        response += element['text'] + '\n'

    await session.finish(response)


@nonebot.on_command('说', only_to_me=False)
async def send_voice_message(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    msg: str = ctx['raw_message']
    args = msg.split()
    if len(args) < 2:
        return
    else:
        message = ''.join(args[1:])

    text = re.sub(r'\[CQ:.*?]', '', message)
    text = re.sub('祈.*?雨', f'{get_nickname(ctx)}', text)
    await session.send(f'[CQ:tts,text={text}]')


@nonebot.message_preprocessor
async def message_preprocessing(_: nonebot.NoneBot, event: aiocqhttp.event, __: PluginManager):
    group_id = event.group_id
    user_id = event.user_id

    if group_id is not None:
        if not admin_group_control.get_group_permission(group_id, group_permission.ENABLED) \
                and not get_privilege(event['user_id'], perm.OWNER):
            raise CanceledException('Group disabled')

        if user_id is not None:
            if get_privilege(user_id, perm.BANNED) and str(user_id) != str(SUPER_USER):
                raise CanceledException('User disabled')
    else:
        if str(user_id) != str(SUPER_USER):
            raise CanceledException('User disabled')


@nonebot.on_command('来点怪话', only_to_me=False)
async def say_something_weird(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    msg = ctx['raw_message']
    args = msg.split()
    if len(args) != 2:
        return

    response = weeb_learning.get_weeb_reply_by_keyword(args[1])
    if isinstance(response, list):
        response = random.choice(response)

    await session.send(response)


@nonebot.on_command('我教你怪话', only_to_me=False)
async def teach_you_weeb_shit(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    msg = ctx['raw_message']
    args = msg.split()

    if len(args) < 3:
        await session.finish('使用方法应该是：！我教你怪话 {关键词} {二刺猿的答复}')

    response = ' '.join(args[2:])

    uuid, keyword, response = weeb_learning.set_weeb_word_wait_approve(keyword=args[1], response=response)
    if uuid:
        await session.send('已汇报给机器人的主人！请等待审批！')
        bot = nonebot.get_bot()
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=f'新的二刺猿语录等待审批：\n'
                    f'uuid: {uuid}\n'
                    f'关键词：{keyword}\n'
                    f'回复：{response}\n'
                    f'添加人qq：{get_user_id(ctx)}\n'
                    f'添加人昵称：{get_nickname(ctx)}\n'
                    f'来自群：{get_group_id(ctx)}'
        )
    else:
        await session.finish('已检测到该词条存在，将拒绝添加。')


@nonebot.on_command('决定怪话', only_to_me=False)
async def decision_on_weeb_shit(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)
    if not get_privilege(user_id, perm.OWNER):
        await session.finish('您无权使用本命令')

    message = ctx['raw_message']
    args = message.split()
    if len(args) != 3:
        await session.finish('使用方法：！决定怪话 {uuid} {y/n}')

    uuid = args[1]
    decision = args[2].lower()
    decision = decision == 'y'

    if weeb_learning.set_weeb_word_to_main_dict(uuid, decision):
        await session.finish('完成！')

    await session.finish('添加失败（uuid不存在或重复添加语录）')


@nonebot.on_command('你群有多色', only_to_me=False)
async def get_setu_stat(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish('本功能是群组功能')

    group_stat_dict = setu_control.get_group_usage_literal(get_group_id(ctx))
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

    await session.send(setu_notice + yanche_notice + ark_data)


@nonebot.on_command('happy', aliases={'快乐时光'}, only_to_me=False)
async def start_happy_hours(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    id_num = str(get_user_id(ctx))
    if get_privilege(id_num, perm.OWNER):
        if setu_control.happy_hours:
            setu_control.happy_hours = False
            await session.finish('已设置关闭快乐时光')

        setu_control.happy_hours = not setu_control.happy_hours
        await session.finish('已设置打开快乐时光')

    else:
        await session.finish('您无权使用本指令')


@nonebot.on_command('设置R18', only_to_me=False)
async def set_r18(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.WHITELIST):
        await session.finish('您无权进行该操作')

    if 'group_id' in ctx:
        id_num = get_group_id(ctx)
    else:
        await session.finish('请在需要禁用或开启R18的群内使用本指令')

    setting = session.get('stats', prompt='请设置开启或关闭')

    set_group_permission(setting, id_num, group_permission.ALLOW_R18)

    await session.finish('Done!')


@nonebot.on_command('掉落查询', only_to_me=False)
async def check_pcr_drop(session: nonebot.CommandSession):
    query = session.get('group_id', prompt='请输入要查询的道具名称')
    response = await pcr_api.pcr_check(query=query)
    await session.finish(response)


@nonebot.on_command('方舟十连', only_to_me=False)
async def ten_polls(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.send('这是群组功能')
        return

    if get_privilege(get_user_id(ctx), perm.OWNER):
        arknights_api.get_randomized_results(98)

    else:
        offset = ark_pool_pity.get_offset_setting(get_group_id(ctx))
        arknights_api.get_randomized_results(offset)
        class_list = arknights_api.random_class
        six_star_count = class_list.count(6) + class_list.count(-1)
        if 6 in class_list or -1 in class_list:
            ark_pool_pity.reset_offset(get_group_id(ctx))

        five_star_count = class_list.count(5)

        data = {
            "6": six_star_count,
            "5": five_star_count,
            "4": class_list.count(4),
            "3": class_list.count(3)
        }

        nickname = get_nickname(ctx)

        if six_star_count == 0 and five_star_count == 0:
            setu_control.set_user_data(get_user_id(ctx), ARKNIGHTS_BAD_LUCK_PULL, nickname)

        setu_control.set_group_data(group_id=get_group_id(ctx), tag=ARKNIGHTS_PULLS, data=data)
        setu_control.set_group_data(group_id=get_group_id(ctx), tag=ARKNIGHTS_SINGLE_PULL)
        setu_control.set_user_data(get_user_id(ctx), ARKNIGHTS_SIX_STAR_PULL, six_star_count)

    qq_num = get_user_id(ctx)
    await session.send(
        f'[CQ:at,qq={qq_num}]\n{arknights_api.__str__()}'
    )


@nonebot.on_command('方舟up', aliases='方舟UP', only_to_me=False)
async def up_ten_polls(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.OWNER):
        await session.finish('您无权使用本功能')

    key_word: str = session.get(
        'key_word',
        prompt='使用方法：！方舟up 干员名 星级（数字）是否限定(y/n) 是否二级限定(y/n)'
    )

    args = key_word.split()
    validation = ark_helper(args)
    if validation:
        await session.finish(validation)

    await session.finish(
        arknights_api.up_op(
            args[0],
            args[1],
            args[2].lower() == 'y',
            args[3].lower() == 'y'
        )
    )


@nonebot.on_command('帮我做选择', only_to_me=False)
async def do_mcq(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    raw_message: str = ctx['raw_message']

    question_count = 1
    if len(raw_message.split()) == 2:
        try:
            question_count = int(raw_message.split()[1])
        except TypeError:
            question_count = 1

    answer = '选'
    for i in range(question_count):
        answer += f'{chr(random.randint(65, 68))}'

    await session.send(answer + '。')


@nonebot.on_command('方舟up重置', aliases={'方舟UP重置', 'UP重置'}, only_to_me=False)
async def reset_ark_up(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.OWNER):
        await session.finish('您无权使用本功能')

    arknights_api.clear_ups()
    await session.finish('Done!')


@nonebot.on_command('添加干员', aliases='', only_to_me=False)
async def add_ark_op(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.OWNER):
        await session.finish('您无权使用本功能')

    key_word: str = session.get(
        'key_word',
        prompt='使用方法：！方舟up 干员名 星级（数字）'
    )

    args = key_word.split()
    validation = ark_helper(args)
    if validation:
        await session.finish(validation)

    await session.finish(arknights_api.add_op(args[0], args[1]))


def get_stat(key: str, lis: dict) -> (int, int):
    return lis[key]['count'] if key in lis else 0, lis[key]['rank'] if key in lis else 0


@nonebot.on_command('统计', only_to_me=False)
async def stat_player(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)
    stat_dict = setu_control.get_user_data(user_id)
    if not stat_dict:
        await session.send(f'[CQ:at,qq={user_id}]还没有数据哦~')
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

        await session.send(f'用户[CQ:at,qq={user_id}]：\n' +
                           (f'比大小赢得{poker_win}次（排名第{poker_rank}）\n' if poker_win != 0 else '') +
                           (
                               f'方舟抽卡共抽到{six_star_pull}个六星干员（排名第{six_star_rank}）\n ' if six_star_pull != 0 else '') +
                           (f'紫气东来{unlucky}次（排名第{unlucky}）\n' if unlucky != 0 else '') +
                           (f'查了{setu_stat}次的色图！（排名第{setu_rank}）\n' if setu_stat != 0 else '') +
                           (f'问了{question}次问题（排名第{question_rank}）\n' if question != 0 else '') +
                           (f'和bot主人 臭 味 相 投{same}次（排名第{same_rank}）\n' if same != 0 else '') +
                           (f'轮盘赌被处死{roulette}次（排名第{roulette_rank}）\n' if roulette != 0 else '') +
                           (f'赛马获胜{horse_race}次（排名第{horse_rank}）\n' if horse_race != 0 else '') +
                           (f'查询语录{yulu}次（排名第{yulu_rank}）\n' if yulu != 0 else '')
                           )


@nonebot.on_command('统计xp', only_to_me=False)
async def get_xp_stat_data(session: nonebot.CommandSession):
    xp_stat = setu_control.get_xp_data()
    response = ''
    for item in xp_stat:
        response += f'关键词：{item[0]} --> Hit: {item[1]}\n'

    await session.finish(response)


# noinspection PyTestUnpassedFixture
@nonebot.on_command('娱乐开关', only_to_me=False)
async def entertain_switch(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    id_num = str(get_user_id(ctx))
    if not get_privilege(id_num, perm.WHITELIST):
        await session.finish('您无权进行该操作')

    group_id = session.get('group_id', prompt='请输入要禁用所有功能的qq群')
    if not str(group_id).isdigit():
        await session.finish('这不是qq号哦~')

    if admin_group_control.get_group_permission(group_id, group_permission.BANNED):
        admin_group_control.set_group_permission(group_id, group_permission.BANNED, False)
        await session.finish('已禁用娱乐功能！')
    else:
        admin_group_control.set_group_permission(group_id, group_permission.BANNED, True)
        await session.finish('已开启娱乐功能！')


# noinspection PyUnresolvedReferences
@check_pcr_drop.args_parser
@entertain_switch.args_parser
@clear_group_quotes.args_parser
async def _set_group_property(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['group_id'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('qq组号不能为空')

    session.state[session.current_key] = stripped_arg


# noinspection PyUnresolvedReferences
@add_ark_op.args_parser
@up_ten_polls.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('要查询的关键词不能为空')

    session.state[session.current_key] = stripped_arg


@nonebot.on_command('嘴臭一个', aliases=('骂我', '你再骂', '小嘴抹蜜', '嘴臭一下', '机器人骂我'), only_to_me=False)
async def zui_chou(session: nonebot.CommandSession):
    await session.finish('功能已停用。')


@nonebot.on_command('彩虹屁', aliases=('拍个马屁', '拍马屁', '舔TA'), only_to_me=False)
async def chp(session: nonebot.CommandSession):
    await session.finish(await get_lab_responses('https://api.shadiao.pro/chp', session.ctx.copy()))


@nonebot.on_command('疯狂星期四', only_to_me=False)
async def fkxqs(session: nonebot.CommandSession):
    await session.finish(await get_lab_responses('https://api.shadiao.pro/kfc', session.ctx.copy()))


async def get_lab_responses(url: str, ctx: dict):
    client = HttpxHelperClient()
    json_data = await client.get(url)
    if json_data.status_code != 200:
        return '现在出不来'

    json_data = json_data.json()
    return MessageSegment.reply(get_message_id(ctx)) + json_data['data']['text'].replace('\u200b', '')
