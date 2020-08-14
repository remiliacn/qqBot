import json
import os
import random
import re
import time

import aiocqhttp.event
import nonebot
import pixivpy3
import requests
from aiocqhttp import MessageSegment
from nonebot.message import CanceledException
from nonebot.plugin import PluginManager

import config
from Shadiao import waifu_finder, ark_nights, shadiao, pcr_news
from awesome.adminControl import group_admin, setu
from awesome.adminControl import permission as perm
from config import SUPER_USER
from qq_bot_core import alarm_api
from qq_bot_core import user_control_module

pcr_api = pcr_news.GetPCRNews()
sanity_meter = setu.SetuFunction()
pixiv_api = pixivpy3.AppPixivAPI()
arknights_api = ark_nights.ArkHeadhunt(times=10)
admin_control = group_admin.Shadiaoadmin()
ark_pool_pity = ark_nights.ArknightsPity()

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)


def ark_helper(args: list) -> str:
    if len(args) != 2:
        return '用法有误\n' + '使用方法：！命令 干员名 星级（数字）'

    if not args[1].isdigit():
        return '使用方法有误，第二参数应为数字'

    return ''

@nonebot.on_command('吹我', only_to_me=False)
async def do_joke_flatter(session: nonebot.CommandSession):
    flatter_api = shadiao.flatter()
    ctx = session.ctx.copy()
    user_id = ctx['user_id']
    await session.send(flatter_api.get_flatter_result(user_id))

@nonebot.on_command('你群语录', aliases=('你组语录', '语录'), only_to_me=False)
async def get_group_quotes(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish()

    await session.finish(admin_control.get_group_quote(ctx['group_id']))


@nonebot.on_command('色图数据', only_to_me=False)
async def get_setu_stat(session: nonebot.CommandSession):
    setu_stat = sanity_meter.get_keyword_track()[0:10]
    response = ''
    if not setu_stat:
        await session.finish('暂时还无色图数据！')
    for element in setu_stat:
        response += f'关键词：{element[0]} -> hit = {element[1]}\n'

    await session.finish(response)


@nonebot.on_command('添加语录', only_to_me=False)
async def add_group_quotes(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish()

    key_word = re.sub(r'.*?添加语录[\s\r\n]*', '', ctx['raw_message']).strip()
    if '屑bot' in key_word.lower():
        await session.finish('爬')

    bot = nonebot.get_bot()
    has_image = re.findall(r'.*?\[CQ:image,file=(.*?\.image)]', key_word)
    if has_image:
        response = await bot.get_image(file=has_image[0])
        url = response['url']
        image_response = requests.get(
            url,
            stream=True
        )
        image_response.raise_for_status()
        path = f'{os.getcwd()}/data/lol/{response["filename"]}'
        with open(path, 'wb') as file:
            file.write(image_response.content)

        key_word = str(MessageSegment.image(f'file:///{path}'))

    if key_word:
        admin_control.add_quote(ctx['group_id'], key_word)
        await session.finish('已添加！')


@nonebot.message_preprocessor
async def message_preprocessing(unused1: nonebot.NoneBot, event: aiocqhttp.event, unused2: PluginManager):
    group_id = event.group_id
    if group_id is not None:
        if not admin_control.get_data(group_id, 'enabled') \
                and not get_privilege(event['user_id'], perm.OWNER):
            raise CanceledException('Group disabled')


@nonebot.on_command('来个老婆', aliases=('来张waifu', '来个waifu', '老婆来一个'), only_to_me=False)
async def send_waifu(session: nonebot.CommandSession):
    waifu_api = waifu_finder.waifuFinder()
    path, message = waifu_api.getImage()
    if not path:
        await session.send(message)
    else:
        nonebot.logger.info(f'Get waifu pic: {path}')
        await session.send(f'[CQ:image,file=file:///{path}]\n{message}')


@nonebot.on_command('shadiao', aliases=('沙雕图', '来一张沙雕图', '机器人来张沙雕图'), only_to_me=False)
async def shadiao_send(session: nonebot.CommandSession):
    shadiao_api = shadiao.ShadiaoAPI()
    file = shadiao_api.get_picture()
    await session.send(f'[CQ:image,file=file:///{file}]')


@nonebot.on_command('PCR', only_to_me=False)
async def pcr_news_send(session: nonebot.CommandSession):
    try:
        await session.send(await pcr_api.get_content())
    except Exception as e:
        await session.send(
            f'请上报机器人主人\n'
            f'Error fetching data: {e}'
        )


@nonebot.on_command('你群有多色', only_to_me=False)
async def get_setu_stat(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish('本功能是群组功能')

    times, rank, yanche, delta, ark_stat, ark_pull = sanity_meter.get_usage(ctx['group_id'])
    setu_notice = f'自统计功能实装以来，你组查了{times}次色图！' \
                  f'{"位居色图查询排行榜的第" + str(rank) + "！" if rank != -1 else ""}\n' \
                  f'距离第{2 if rank == 1 else rank - 1}位相差{delta}次搜索！\n'

    yanche_notice = ('并且验车了' + str(yanche) + "次！\n") if yanche > 0 else ''
    ark_data = ''
    if ark_stat:
        ark_data += f'十连充卡共{ark_pull}次，理论消耗合成玉{ark_pull * 6000}。抽到了：\n' \
                    f"3星{ark_stat['3']}个，4星{ark_stat['4']}个，5星{ark_stat['5']}个，6星{ark_stat['6']}个"

    await session.send(setu_notice + yanche_notice + ark_data)


@nonebot.on_command('理智查询', only_to_me=False)
async def sanity_checker(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' in ctx:
        id_num = ctx['group_id']
    else:
        id_num = ctx['user_id']

    if id_num in sanity_meter.get_sanity_dict():
        sanity = sanity_meter.get_sanity(id_num)
    else:
        sanity = sanity_meter.get_max_sanity()
        sanity_meter.set_sanity(id_num, sanity_meter.get_max_sanity())

    await session.send(f'本群剩余理智为：{sanity}')


@nonebot.on_command('理智补充', only_to_me=False)
async def sanity_refill(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.ADMIN):
        await session.finish('您没有权限补充理智')

    id_num = 0
    sanity_add = 0
    try:
        id_num = int(session.get('id_num', prompt='请输入要补充的ID'))
        sanity_add = int(session.get('sanity_add', prompt='那要补充多少理智呢？'))
    except ValueError:
        await session.finish('未找到能够补充的对象')

    try:
        sanity_meter.fill_sanity(id_num, sanity=sanity_add)
    except KeyError:
        await session.finish('未找到能够补充的对象')

    await session.finish('补充理智成功！')


@nonebot.on_command('happy', aliases={'快乐时光'}, only_to_me=False)
async def start_happy_hours(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    id_num = str(ctx['user_id'])
    if get_privilege(id_num, perm.OWNER):
        if sanity_meter.happy_hours:
            sanity_meter.happy_hours = False
            await session.finish('已设置关闭快乐时光')

        sanity_meter.happy_hours = not sanity_meter.happy_hours
        await session.finish('已设置打开快乐时光')

    else:
        await session.finish('您无权使用本指令')


@nonebot.on_command('设置R18', only_to_me=False)
async def set_r18(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.WHITELIST):
        await session.finish('您无权进行该操作')

    if 'group_id' in ctx:
        id_num = ctx['group_id']
    else:
        await session.finish('请在需要禁用或开启R18的群内使用本指令')
        id_num = -1

    setting = session.get('stats', prompt='请设置开启或关闭')
    if '开' in setting:
        admin_control.set_data(id_num, 'R18', True)
        resp = '开启'
    else:
        admin_control.set_data(id_num, 'R18', False)
        resp = '关闭'

    await session.finish('Done! 已设置%s' % resp)


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

    if get_privilege(ctx['user_id'], perm.OWNER):
        arknights_api.get_randomized_results(98)

    else:
        offset = ark_pool_pity.get_offset_setting(ctx['group_id'])
        arknights_api.get_randomized_results(offset)
        class_list = arknights_api.random_class
        six_star_count = class_list.count(6)
        if 6 in class_list:
            ark_pool_pity.reset_offset(ctx['group_id'])

        five_star_count = class_list.count(5)

        data = {
            "6": six_star_count,
            "5": five_star_count,
            "4": class_list.count(4),
            "3": class_list.count(3)
        }

        if six_star_count == 0 and five_star_count == 0:
            sanity_meter.set_user_data(ctx['user_id'], 'only_four_three')

        sanity_meter.set_usage(group_id=ctx['group_id'], tag='pulls', data=data)
        sanity_meter.set_usage(group_id=ctx['group_id'], tag='pull')
        sanity_meter.set_user_data(ctx['user_id'], 'six_star_pull', six_star_count)

    qq_num = ctx['user_id']
    await session.send(
        f'[CQ:at,qq={qq_num}]\n{arknights_api.__str__()}'
    )


@nonebot.on_command('方舟up', aliases='方舟UP', only_to_me=False)
async def up_ten_polls(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish('您无权使用本功能')

    key_word: str = session.get(
        'key_word',
        prompt='使用方法：！方舟up 干员名 星级（数字）'
    )

    args = key_word.split()
    validation = ark_helper(args)
    if validation:
        await session.finish(validation)

    await session.finish(arknights_api.set_up(args[0], args[1]))


@nonebot.on_command('方舟up重置', aliases='方舟UP重置', only_to_me=False)
async def reset_ark_up(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish('您无权使用本功能')

    arknights_api.clear_ups()
    await session.finish('Done!')


@nonebot.on_command('添加干员', aliases='', only_to_me=False)
async def add_ark_op(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.OWNER):
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


@nonebot.on_command('统计', only_to_me=False)
async def stat_player(session: nonebot.CommandSession):
    get_stat = lambda key, lis: lis[key] if key in lis else 0
    ctx = session.ctx.copy()
    user_id = ctx['user_id']
    statDict = sanity_meter.get_user_data(user_id)
    if not statDict:
        await session.send(f'[CQ:at,qq={user_id}]还没有数据哦~')
    else:
        poker_win = get_stat('poker', statDict)
        six_star_pull = get_stat('six_star_pull', statDict)
        yanche = get_stat('yanche', statDict)
        setu_stat = get_stat('setu', statDict)
        question = get_stat('question', statDict)
        unlucky = get_stat('only_four_three', statDict)
        same = get_stat('hit_xp', statDict)
        zc = get_stat('zc', statDict)
        chp = get_stat('chp', statDict)
        roulette = get_stat('roulette', statDict)
        horse_race = get_stat('horse_race', statDict)

        await session.send(f'用户[CQ:at,qq={user_id}]：\n' +
                           (f'比大小赢得{poker_win}次\n' if poker_win != 0 else '') +
                           (f'方舟抽卡共抽到{six_star_pull}个六星干员\n' if six_star_pull != 0 else '') +
                           (f'紫气东来{unlucky}次\n' if unlucky != 0 else '') +
                           (f'验车{yanche}次\n' if yanche != 0 else '') +
                           (f'查了{setu_stat}次的色图！\n' if setu_stat != 0 else '') +
                           (f'问了{question}次问题\n' if question != 0 else '') +
                           (f'和bot主人 臭 味 相 投{same}次\n' if same != 0 else '') +
                           (f'嘴臭{zc}次\n' if zc != 0 else '') +
                           (f'彩虹屁{chp}次\n' if chp != 0 else '') +
                           (f'轮盘赌被处死{roulette}次\n' if roulette != 0 else '') +
                           (f'赛马获胜{horse_race}次\n' if horse_race != 0 else '')

                           )


@nonebot.on_command('统计xp', only_to_me=False)
async def get_xp_stat_data(session: nonebot.CommandSession):
    xp_stat = sanity_meter.get_xp_data()
    response = ''
    for item, keys in xp_stat.items():
        response += f'关键词：{item} --> Hit: {keys}\n'

    await session.finish(response)


@nonebot.on_command('娱乐开关', only_to_me=False)
async def entertain_switch(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    id_num = str(ctx['user_id'])
    if not get_privilege(id_num, perm.WHITELIST):
        await session.finish('您无权进行该操作')

    group_id = session.get('group_id', prompt='请输入要禁用所有功能的qq群')
    if not str(group_id).isdigit():
        await session.finish('这不是qq号哦~')

    if admin_control.get_data(group_id, 'enabled'):
        admin_control.set_data(group_id, 'enabled', False)
        await session.finish('已禁用娱乐功能！')
    else:
        admin_control.set_data(group_id, 'enabled', True)
        await session.finish('已开启娱乐功能！')


@nonebot.on_command('设置色图禁用', only_to_me=False)
async def set_black_list_group(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.WHITELIST):
        group_id = session.get('group_id', prompt='请输入要禁用的qq群')
        try:
            admin_control.set_data(group_id, 'banned', True)
        except ValueError:
            await session.finish('这不是数字啊kora')

        await session.finish('你群%s没色图了' % group_id)


@nonebot.on_command('删除色图禁用', only_to_me=False)
async def deleteBlackListGroup(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.WHITELIST):
        group_id = session.get('group_id', prompt='请输入要禁用的qq群')
        try:
            admin_control.set_data(group_id, 'banned', False)
        except ValueError:
            await session.finish('emmm没找到哦~')

        await session.finish('你群%s又有色图了' % group_id)


@set_black_list_group.args_parser
@deleteBlackListGroup.args_parser
@check_pcr_drop.args_parser
@entertain_switch.args_parser
async def _setGroupProperty(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['group_id'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('qq组号不能为空')

    session.state[session.current_key] = stripped_arg


@nonebot.on_command('闪照设置', only_to_me=False)
async def set_exempt(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.ADMIN) or 'group_id' not in ctx:
        return

    group_id = ctx['group_id']
    if admin_control.get_data(group_id, 'exempt'):
        admin_control.set_data(group_id, 'exempt', False)
        await session.finish('已打开R18闪照发送模式')

    else:
        admin_control.set_data(group_id, 'exempt', True)
        await session.finish('本群R18图将不再已闪照形式发布')


@nonebot.on_command('验车', only_to_me=False)
async def av_validator(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    if not admin_control.get_data(ctx['group_id'], 'R18'):
        await session.finish('请联系BOT管理员开启本群R18权限')

    key_word = session.get('key_word', prompt='在？你要让我查什么啊baka')
    validator = shadiao.Avalidator(text=key_word)
    if 'group_id' in ctx:
        sanity_meter.set_usage(ctx['group_id'], tag='yanche')
        sanity_meter.set_user_data(ctx['user_id'], 'yanche')

    await session.finish(validator.get_content())


@nonebot.on_command('色图', aliases='来张色图', only_to_me=False)
async def pixiv_send(session: nonebot.CommandSession):
    if not get_status():
        await session.finish('机器人现在正忙，不接受本指令。')

    if alarm_api.get_alarm():
        await session.finish(
            '警报已升起！请等待解除！\n'
            f'{alarm_api.get_info()}'
        )

    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.BANNED):
        return

    group_id = ctx['group_id'] if 'group_id' in ctx else -1
    user_id = ctx['user_id']
    if 'group_id' in ctx and not get_privilege(user_id, perm.OWNER):
        if admin_control.get_data(ctx['group_id'], 'banned'):
            await session.finish('管理员已设置禁止该群接收色图。如果确认这是错误的话，请联系bot制作者')

    sanity = -1
    monitored = False
    multiplier = 1
    doMultiply = False

    if group_id in sanity_meter.get_sanity_dict():
        sanity = sanity_meter.get_sanity(group_id)

    elif 'group_id' not in ctx and not get_privilege(user_id, perm.WHITELIST):
        await session.finish('我主人还没有添加你到信任名单哦。请找BOT制作者要私聊使用权限~')

    else:
        sanity = sanity_meter.get_max_sanity()
        sanity_meter.set_sanity(group_id=group_id, sanity=sanity_meter.get_max_sanity())

    if sanity <= 0:
        if group_id not in sanity_meter.remind_dict or not sanity_meter.remind_dict[group_id]:
            sanity_meter.set_remid_dict(group_id, True)
            await session.finish(
                '您已经理智丧失了，不能再查了哟~（小提示：指令理智查询可以帮您查看本群还剩多少理智）'
            )
            
        return

    if not admin_control.get_if_authed():
        pixiv_api.set_auth(
            access_token=admin_control.get_access_token(),
            refresh_token='iL51azZw7BWWJmGysAurE3qfOsOhGW-xOZP41FPhG-s'
        )
        admin_control.set_if_authed(True)

    is_exempt = admin_control.get_data(group_id, 'exempt') if group_id != -1 else False

    key_word = str(session.get('key_word', prompt='请输入一个关键字进行查询')).lower()

    if key_word in sanity_meter.get_bad_word_dict():
        multiplier = sanity_meter.get_bad_word_dict()[key_word]
        doMultiply = True
        if multiplier > 0:
            await session.send(
                f'该查询关键词在黑名单中，危机合约模式已开启：本次色图搜索将{multiplier}倍消耗理智'
            )
        else:
            await session.send(
                f'该查询关键词在白名单中，支援合约已开启：本次色图搜索将{abs(multiplier)}倍补充理智'
            )

    if key_word in sanity_meter.get_monitored_keywords():
        await session.send('该关键词在主人的监控下，本次搜索不消耗理智，且会转发主人一份√')
        monitored = True
        if 'group_id' in ctx:
            sanity_meter.set_user_data(user_id, 'hit_xp')
            sanity_meter.set_xp_data(key_word)

    elif '色图' in key_word:
        await session.finish(MessageSegment.image(f'file:///{os.getcwd()}/data/dl/others/QQ图片20191013212223.jpg'))

    elif '屑bot' in key_word:
        await session.finish('你屑你🐴呢')

    json_result = {}

    try:
        if '最新' in key_word:
            json_result = pixiv_api.illust_ranking('week')
        else:
            json_result = pixiv_api.search_illust(
                word=key_word,
                sort="popular_desc"
            )

    except pixivpy3.PixivError:
        await session.finish('pixiv连接出错了！')

    except Exception as err:
        await session.send(f'发现未知错误！错误信息已发送给bot主人分析！\n'
                           f'{err}')

        bot = nonebot.get_bot()
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=f'Uncaught error while using pixiv search:\n'
                    f'Error from {user_id}\n'
                    f'Keyword = {key_word}\n'
                    f'Exception = {err}')

        return

    # 看一下access token是否过期
    if 'error' in json_result:
        admin_control.set_if_authed(False)
        try:
            admin_control.set_access_token(
                access_token=pixiv_api.auth(
                    username=config.user_name,
                    password=config.password).response.access_token
            )

            await session.send('新的P站匿名访问链接已建立……')
            admin_control.set_if_authed(True)

        except pixivpy3.PixivError:
            return

    if '{user=' in key_word:
        key_word = re.findall(r'{user=(.*?)}', key_word)
        if key_word:
            key_word = key_word[0]
        else:
            await session.send('未找到该用户。')
            return

        json_user = pixiv_api.search_user(word=key_word, sort="popular_desc")
        if json_user.user_previews:
            user_id = json_user.user_previews[0].user.id
            json_result = pixiv_api.user_illusts(user_id)
        else:
            await session.send(f"{key_word}无搜索结果或图片过少……")
            return

    else:
        json_result = pixiv_api.search_illust(word=key_word, sort="popular_desc")

    if not json_result.illusts or len(json_result.illusts) < 4:
        nonebot.logger.warning(f"未找到图片, keyword = {key_word}")
        await session.send(f"{key_word}无搜索结果或图片过少……")
        return

    sanity_meter.track_keyword(key_word)
    illust = random.choice(json_result.illusts)
    is_r18 = illust.sanity_level == 6
    if not monitored:
        if is_r18:
            sanity_meter.drain_sanity(
                group_id=group_id,
                sanity=2 if not doMultiply else 2 * multiplier
            )
        else:
            sanity_meter.drain_sanity(
                group_id=group_id,
                sanity=1 if not doMultiply else 1 * multiplier
            )

    start_time = time.time()
    path = download_image(illust)
    try:
        nickname = ctx['sender']['nickname']
    except TypeError:
        nickname = 'null'

    bot = nonebot.get_bot()
    if not is_r18:
        try:
            await session.send(
                f'[CQ:at,qq={user_id}]\n'
                f'Pixiv ID: {illust.id}\n'
                f'查询关键词：{key_word}\n'
                f'画师：{illust["user"]["name"]}\n' +
                f'{MessageSegment.image(f"file:///{path}")}' +
                f'Download Time: {(time.time() - start_time):.2f}s'
            )

            nonebot.logger.info("sent image on path: " + path)

        except Exception as e:
            nonebot.logger.info('Something went wrong %s' % e)
            await session.send('悲，屑TX不收我图。')
            return

    elif is_r18 and (group_id == -1 or admin_control.get_data(group_id, 'R18')):
        message_id = await session.send(
            f'[CQ:at,qq={user_id}]\n'
            f'芜湖~好图来了ww\n'
            f'Pixiv ID: {illust.id}\n'
            f'关键词：{key_word}\n'
            f'画师：{illust["user"]["name"]}\n'
            f'{MessageSegment.image(f"file:///{path}")}' +
            f'Download Time: {(time.time() - start_time):.2f}s'
        )

        if not is_exempt:
            message_id = message_id['message_id']
            sanity_meter.add_recall(message_id)
            nonebot.logger.info(f'Added message_id {message_id} to recall list.')

    else:
        if not monitored:
            await session.send('我找到色图了！\n但是我发给我主人了_(:зゝ∠)_')
            await bot.send_private_msg(user_id=SUPER_USER,
                                       message=f"图片来自：{nickname}\n"
                                               f"来自群：{group_id}\n"
                                               f"查询关键词：{key_word}\n" +
                                               f'Pixiv ID: {illust.id}\n' +
                                               f'{MessageSegment.image(f"file:///{path}")}' +
                                               f'Download Time: {(time.time() - start_time):.2f}s'
                                       )

    sanity_meter.set_usage(group_id, 'setu')
    if 'group_id' in ctx:
        sanity_meter.set_user_data(user_id, 'setu')

    if monitored and not get_privilege(user_id, perm.OWNER):
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=f'图片来自：{nickname}\n'
                    f'查询关键词:{key_word}\n'
                    f'Pixiv ID: {illust.id}\n'
                    '关键字在监控中' + f'[CQ:image,file=file:///{path}]'
        )


def download_image(illust):
    if illust['meta_single_page']:
        if 'original_image_url' in illust['meta_single_page']:
            image_url = illust.meta_single_page['original_image_url']
        else:
            image_url = illust.image_urls['medium']
    else:
        image_url = illust.image_urls['medium']

    nonebot.logger.info(f"{illust.title}: {image_url}, {illust.id}")
    image_file_name = image_url.split('/')[-1].replace('_', '')
    path = f'{os.getcwd()}/data/pixivPic/' + image_file_name

    if not os.path.exists(path):
        try:
            response = pixiv_api.requests_call(
                'GET',
                image_url,
                headers={'Referer': 'https://app-api.pixiv.net/'},
            )

            with open(path, 'wb') as out_file:
                out_file.write(response.content)

        except Exception as err:
            nonebot.logger.info(f'Download image error: {err}')

    nonebot.logger.info("PATH = " + path)
    return path


@nonebot.on_command('ghs', only_to_me=False)
async def get_random_image(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        return

    id_num = ctx['group_id']
    user_id = ctx['user_id']
    sanity_meter.set_usage(id_num, 'setu')
    sanity_meter.set_user_data(user_id, 'setu')

    message, is_nsfw = await get_random()
    message_id = await session.send(message)
    if is_nsfw:
        message_id = message_id['message_id']
        nonebot.logger.info(f'Adding message_id {message_id} to recall list.')
        sanity_meter.add_recall(message_id)


async def get_random():
    headers = {
        'Authorization': 'HM9GYMGhY7ccUk7'
    }

    sfw = 'https://gallery.fluxpoint.dev/api/sfw/anime'
    nsfw = 'https://gallery.fluxpoint.dev/api/nsfw/lewd'
    rand_num = random.randint(0, 101)
    if rand_num >= 80:
        is_nsfw = True
    else:
        is_nsfw = False

    page = requests.get(nsfw if is_nsfw else sfw, headers=headers).json()

    filename = page['file'].split('/')[-1]

    image_page = requests.get(
        page['file'],
        stream=True
    )

    path = f'{os.getcwd()}/data/pixivPic/{filename}'
    if not os.path.exists(path):
        with open(path, 'wb') as f:
            for chunk in image_page.iter_content(chunk_size=1024 ** 3):
                f.write(chunk)

    return MessageSegment.image(f'file:///{path}'), is_nsfw


@pixiv_send.args_parser
@add_ark_op.args_parser
@up_ten_polls.args_parser
@av_validator.args_parser
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
async def zuiChou(session: nonebot.CommandSession):
    ctx = session.ctx.copy()

    if get_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    if 'group_id' in ctx:
        sanity_meter.set_user_data(ctx['user_id'], 'zc')

    random.seed(time.time_ns())
    rand_num = random.randint(0, 100)
    if rand_num > 25:
        try:
            req = requests.get('https://nmsl.shadiao.app/api.php?level=min&from=qiyu', timeout=5)
        except requests.exceptions.Timeout:
            await session.send('骂不出来了！')
            return

        text = req.text

    elif rand_num > 10:
        try:
            req = requests.get('https://nmsl.shadiao.app/api.php?level=max&from=qiyu', timeout=5)
        except requests.exceptions.Timeout:
            await session.send('骂不出来了！')
            return


        text = req.text

    else:
        file = os.listdir('data/dl/zuichou')
        file = random.choice(file)
        text = f"[CQ:image,file=file:///{os.getcwd()}/data/dl/zuichou/{file}]"

    msg = str(ctx['raw_message'])

    if re.match(r'.*?\[CQ:at,qq=.*?\]', msg):
        qq = re.findall(r'\[CQ:at,qq=(.*?)\]', msg)[0]
        if qq != "all":
            if not get_privilege(qq, perm.ADMIN):
                await session.finish(f"[CQ:at,qq={int(qq)}] {text}")
            else:
                await session.finish(f"[CQ:at,qq={ctx['user_id']}] {text}")

    await session.send(text)


@nonebot.on_command('彩虹屁', aliases=('拍个马屁', '拍马屁', '舔TA'), only_to_me=False)
async def cai_hong_pi(session: nonebot.CommandSession):
    ctx = session.ctx.copy()

    if get_privilege(ctx['user_id'], perm.BANNED):
        await session.finish('略略略，我主人把你拉黑了。哈↑哈↑哈')

    if 'group_id' in ctx:
        sanity_meter.set_user_data(ctx['user_id'], 'chp')

    try:
        req = requests.get('https://chp.shadiao.app/api.php?from=qiyu', timeout=5)
    except requests.exceptions.Timeout:
        await session.send('拍马蹄上了_(:зゝ∠)_')
        return

    text = req.text
    msg = str(ctx['raw_message'])

    if re.match(r'.*?\[CQ:at,qq=.*?\]', msg):
        qq = re.findall(r'\[CQ:at,qq=(.*?)\]', msg)[0]
        if qq != "all":
            await session.send(f"[CQ:at,qq={int(qq)}] {text}")
            return

    await session.send(text)


def get_status():
    file = open('data/started.json', 'r')
    status_dict = json.loads(str(file.read()))
    return status_dict['status']
