import asyncio
import re
import time
from datetime import datetime

import nonebot
from nonebot.log import logger

from awesome.adminControl import permission as perm
from awesome.adminControl import user_control, group_admin
from awesome.plugins.shadiao import pcr_api
from awesome.plugins.shadiao import sanity_meter
from awesome.plugins.tweetHelper import tweeter
from bilibiliService import bilibili_topic
from config import SUPER_USER
from qq_bot_core import alarm_api

user_control_module = user_control.UserControl()
admin_control = group_admin.Shadiaoadmin()

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)


tweet = tweeter.tweeter()
share_link = 'paryi-my.sharepoint.com/:f:/g/personal/hanayori_paryi_xyz/Em62_uotiDlIohJKvbMWoiQBzutGjbRga1uOXNdmTjEtpA?e=X4hGfT'


@nonebot.on_command('跟推添加', only_to_me=False)
async def add_new_tweeter_function(session: nonebot.CommandSession):
    usage = '！跟推添加 中文名 推特ID（@后面的那一部分） 直播间（bilibili） 是否启用（启用输入Y反则N）\n' \
            '推特ID和直播间id可使用下划线 _ 忽略参数'

    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.ADMIN):
        await session.finish('您无权使用本指令')

    if 'group_id' not in ctx:
        return

    key_word = session.get(
        'key_word',
        prompt='输入格式：\n' +
               usage
    )

    args = key_word.split()
    if len(args) != 4:
        await session.finish(f'指令有误！应为：{usage}')

    if not re.match('[A-Za-z0-9_]+$', args[1]):
        await session.finish('推特ID有误！')

    if args[2] != '_' and (not args[2].isdigit() and int(args[2]) < 100):
        await session.finish('bilibili直播间应为数字')

    if not (args[3].upper() == 'Y' or args[3].upper() == 'N'):
        await session.finish('是否启用应该输入为Y或N')

    await session.finish(tweet.add_to_config(args, ctx['group_id']))


@nonebot.on_command('跟推移除', only_to_me=False)
async def remove_tweet_following(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.ADMIN):
        await session.finish('您无权使用本指令')

    key_word = session.get(
        'key_word',
        prompt='请输入需要移除的中文key'
    )

    if tweet.remove_from_config(key_word):
        await session.finish('成功！')
    else:
        await session.finish(f'未找到key：{key_word}')


@nonebot.on_command('新推', only_to_me=False)
async def get_new_tweet_by_ch_name(session: nonebot.CommandSession):
    key_word = session.get('key_word', prompt='要查谁啊？')
    the_tweet = tweet.get_time_line_from_screen_name(key_word)
    if the_tweet:
        await session.finish(
            f'--- {key_word}最新动态 ---\n'
            f'{the_tweet}'
        )

    else:
        the_tweet = await tweet.get_time_line_from_screen_name(key_word)
        await session.finish(the_tweet)


@nonebot.on_command('推特查询', only_to_me=False)
async def bulk_get_new_tweet(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    message = ctx['raw_message']
    args = message.split()
    screen_name = args[1]
    count: str = args[2]
    if count.isdigit():
        resp = tweet.get_time_line_from_screen_name(screen_name, count)
        await session.send(resp)
    else:
        await session.finish(
            '用法错误！应为：\n'
            '！推特查询 要查询的内容 要前多少条'
        )


@nonebot.scheduler.scheduled_job('interval', seconds=50)
async def send_tweet():
    start_time = time.time()
    await asyncio.gather(
        do_tweet_update_fetch(),
        do_bilibili_live_fetch(),
        do_youtube_update_fetch(),
        do_pcr_update_fetch(),
        fill_sanity(),
        do_recall(),
        save_stats()
    )

    logger.info('Auto fetch all done!')
    use_time = time.time() - start_time
    logger.info(f'Scheduled job in get_tweet.py used {use_time:.2f}s')
    if use_time > 10.0:
        bot = nonebot.get_bot()
        await bot.send_private_msg(
            user_id=SUPER_USER,
            message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]'
                    f'Scheduled job in get_tweet.py took longer than expected:\n'
                    f'Used: {use_time:.2f}s'
        )

        alarm_info = {
            'sev' : 2,
            'message' : '网络连接出现巨大延迟！',
            'time' : datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        alarm_api.set_alarm(alarm_info)
        if alarm_api.get_alarm():
            await bot.send_private_msg(
                user_id=SUPER_USER,
                message=f'Alarm raised!!!: \n'
                        f'BEE WOO BEE WOO!!!\n'
                        f'{alarm_api.get_info()}'
            )
    else:
        alarm_api.suppress_alarm()

async def save_stats():
    sanity_meter.make_a_json('config/stats.json')
    sanity_meter.make_a_json('config/setu.json')


async def do_recall():
    logger.info('Recalling messages...')
    recall_list = sanity_meter.get_recall()
    if recall_list:
        bot = nonebot.get_bot()
        for message in recall_list:
            logger.info(f'recalling message by message id: {message}')
            try:
                await bot.delete_msg(message_id=message)
            except Exception as err:
                logger.info(
                    f'Error recalling message: {err}\n'
                    f'Message id: {message}'
                )

                await bot.send_private_msg(
                    user_id=SUPER_USER,
                    message=f'Error recalling message: {err}\n'
                            f'Message id: {message}'
                )

        sanity_meter.clear_recall()


async def fill_sanity():
    logger.info('Filling sanity...')
    if sanity_meter.happy_hours:
        sanity_meter.fill_sanity(sanity=5)
    else:
        sanity_meter.fill_sanity(sanity=1)


async def do_pcr_update_fetch():
    logger.info('Checking for PCR news...')
    if await pcr_api.if_new_releases():
        bot = nonebot.get_bot()
        news = await pcr_api.get_content()
        await bot.send_group_msg(group_id=1081267415, message=news)


async def do_youtube_update_fetch():
    logger.info('Checking for video updates...')
    file = open('config/YouTubeNotify.json')
    fl = file.read()
    import json
    youtube_notify_dict = json.loads(str(fl))
    if youtube_notify_dict:
        bot = nonebot.get_bot()
        for elements in youtube_notify_dict:
            if not youtube_notify_dict[elements]['status']:
                if youtube_notify_dict[elements]['retcode'] == 0:
                    try:
                        await bot.send_group_msg(group_id=int(youtube_notify_dict[elements]['group_id']),
                                                 message='刚才你们让扒的源搞好了~\n视频名称：%s\n如果上传好了的话视频将会出现在\n%s' % (
                                                     elements, share_link))
                    except Exception as err:
                        await bot.send_private_msg(
                            user_id=SUPER_USER,
                            message=f'发送扒源信息到组失败{err}\n'
                                    f'组号：{youtube_notify_dict[elements]["group_id"]}'
                        )

                elif youtube_notify_dict[elements]['retcode'] == 1:
                    try:
                        await bot.send_group_msg(
                            group_id=int(youtube_notify_dict[elements]['group_id']),
                            message='有新视频了哦~视频名称：%s' % elements
                        )

                    except Exception as err:
                        await bot.send_private_msg(
                            user_id=SUPER_USER,
                            message=f'发送扒源信息到组失败{err}\n'
                                    f'组号：{youtube_notify_dict[elements]["group_id"]}'
                        )

            else:
                try:
                    await bot.send_private_msg(user_id=SUPER_USER, message=f'源下载失败{elements}')
                except Exception as e:
                    nonebot.logger.warning('Something went wrong %s' % e)

        empty_dict = {}
        with open('E:/Python/qqBot/config/YouTubeNotify.json', 'w+') as f:
            json.dump(empty_dict, f, indent=4)

        file.close()


async def do_tweet_update_fetch():
    logger.info('Automatically fetching tweet info...')
    diff_dict = await tweet.check_update()
    if diff_dict:
        bot = nonebot.get_bot()
        for ch_name in diff_dict:
            group_id_list = tweet.get_tweet_config()[ch_name]['group']
            message = diff_dict[ch_name]
            if message[0:2] == 'RT':
                message = f'=== {ch_name}转发推文说 ===\n' + message
            elif message[0] == '@':
                message = f'=== {ch_name}回了一条推 ===\n' + message
            else:
                message = f'=== {ch_name}发了一条推 ===\n' + message

            nonebot.logger.warning(f'发现新推！来自{ch_name}:\n'
                                   f'{message}')

            for element in group_id_list:
                await bot.send_group_msg(group_id=element,
                                         message=message)


async def do_bilibili_live_fetch():
    logger.info('Automatically fetching bilibili live info...')
    live_stat_dict = tweet.get_live_room_info()
    if live_stat_dict:
        bot = nonebot.get_bot()
        tweet_config = tweet.get_tweet_config()
        for ch_name in live_stat_dict:
            group_id_list = tweet_config[ch_name]['group']
            for element in group_id_list:
                message = live_stat_dict[ch_name]
                await bot.send_group_msg(group_id=element,
                                         message=message)


@nonebot.on_command('b站话题', aliases={'B站话题', 'btopic'}, only_to_me=False)
async def get_bilibili_topic(session: nonebot.CommandSession):
    key_word = session.get('key_word', prompt='要什么的话题呢？')
    await session.send('如果动态内容有图片的话这可能会花费一大段时间。。请稍后……')
    topic = bilibili_topic.Bilibilitopic(topic=key_word)
    response = topic.get_content()
    if response != '':
        await session.send(response)
        return

    await session.send('emmm, 好像没有内容？要不换个话题试试？')


@get_bilibili_topic.args_parser
@get_new_tweet_by_ch_name.args_parser
@add_new_tweeter_function.args_parser
@remove_tweet_following.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('要查询的关键词不能为空')

    session.state[session.current_key] = stripped_arg
