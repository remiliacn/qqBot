import asyncio
import json
import re
from datetime import datetime
from subprocess import Popen

import nonebot
from aiocqhttp import ActionFailed
from loguru import logger

from Services.random_services import YouTubeLiveTracker
from Services.stock import text_to_image
from Services.util.ctx_utility import get_user_id, get_group_id
from awesome.adminControl import permission as perm
from awesome.plugins.shadiao.shadiao import setu_control
from awesome.plugins.util.tweetHelper import tweeter
from config import SUPER_USER, DOWNLODER_FILE_NAME, PATH_TO_ONEDRIVE, STEAM_UTIL_GROUP_NUM
from qq_bot_core import buff_requester
from qq_bot_core import user_control_module

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)

tweet = tweeter.Tweeter()


@nonebot.on_command('跟推添加', only_to_me=False)
async def add_new_tweeter_function(session: nonebot.CommandSession):
    usage = '！跟推添加 中文名 推特ID（@后面的那一部分） 直播间（bilibili） 是否启用（启用输入Y反则N）\n' \
            '推特ID和直播间id可使用下划线 _ 忽略参数'

    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.ADMIN):
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

    await session.finish(tweet.add_to_config(args, get_group_id(ctx)))


@nonebot.on_command('跟推移除', only_to_me=False)
async def remove_tweet_following(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.ADMIN):
        await session.finish('您无权使用本指令')

    key_word = session.get(
        'key_word',
        prompt='请输入需要移除的中文key'
    )

    if tweet.remove_from_config(key_word):
        await session.finish('成功！')
    else:
        await session.finish(f'未找到key：{key_word}')


@nonebot.scheduler.scheduled_job('interval', minutes=2, misfire_grace_time=5)
async def scheduled_jobs():
    await do_youtube_update_fetch()
    if get_status():
        Popen(
            ['py', DOWNLODER_FILE_NAME, 'bulk'],
            stdin=None,
            stdout=None,
            stderr=None,
            close_fds=True
        )

    await asyncio.gather(
        do_tweet_update_fetch(),
        # do_bilibili_live_fetch(),
        fill_sanity(),
        check_youtube_live(),
        check_rates()
    )


def get_status():
    file = open('data/started.json', 'r')
    status_dict = json.loads(str(file.read()))
    return status_dict['status']


async def check_rates():
    if not STEAM_UTIL_GROUP_NUM:
        return

    await buff_requester.do_igxe_work()
    await buff_requester.do_buff_work()
    buff_requester.clear_item_id_set()

    if buff_requester.has_new_data():
        logger.success('We have new data for steam market fetch.')
        bot = nonebot.get_bot()
        for group_num in STEAM_UTIL_GROUP_NUM:
            assert isinstance(group_num, int)
            try:
                await bot.send_group_msg(
                    group_id=int(group_num),
                    # message=f'[CQ:image,file=file:///{await text_to_image(buff_requester.get_table_content())}]'
                    message=buff_requester.get_table_content()
                )
            except ActionFailed:
                await bot.send_group_msg(
                    group_id=int(group_num),
                    message=f'[CQ:image,file=file:///{await text_to_image(buff_requester.get_table_content())}]'
                )

        buff_requester.clear_table_content()

    logger.success('Steam fetch done.')


async def check_youtube_live():
    tasks = []
    with open(f'config/downloader.json', 'r', encoding='utf-8') as file:
        json_data = json.loads(file.read())
        for ch_name in json_data:
            tasks.append(_async_youtube_live(ch_name, json_data))

    await asyncio.gather(*tasks)


async def _async_youtube_live(ch_name, json_data):
    api = YouTubeLiveTracker(json_data[ch_name]['channel'], ch_name)
    await api.get_json_data()
    if 'notify' not in json_data[ch_name] or json_data[ch_name]['notify']:
        if api.get_live_status():
            if await api.update_live_id(True) == 1:
                bot = nonebot.get_bot()
                message = await api.get_live_details()
                if message:
                    await bot.send_group_msg(
                        group_id=json_data[ch_name]['qqGroup'],
                        message=f'{ch_name} 开播啦！\n'
                                f'{message}'
                    )

                    await bot.send_private_msg(
                        user_id=SUPER_USER,
                        message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                                f'{ch_name} is now live:\n'
                                f'{await api.get_live_details()}'
                    )

        # Not currently LIVE info fetch:
        if api.get_upcoming_status():
            resp_code, update_info = await api.update_live_id(False)
            if resp_code == 1:
                bot = nonebot.get_bot()
                message = await api.get_live_details()
                if message:
                    await bot.send_group_msg(
                        group_id=json_data[ch_name]['qqGroup'],
                        message=f'{ch_name} 直播间待机！\n{await api.get_live_details()}'
                    )

                    await bot.send_private_msg(
                        user_id=SUPER_USER,
                        message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                                f'{ch_name} is now ready:\n'
                                f'{await api.get_live_details()}'
                    )
            elif resp_code == 2:
                bot = nonebot.get_bot()
                message = await api.get_live_details()
                if message:
                    await bot.send_group_msg(
                        group_id=json_data[ch_name]['qqGroup'],
                        message=f'{ch_name} 直播间内容更新！\n{update_info}'
                    )

                    await bot.send_private_msg(
                        user_id=SUPER_USER,
                        message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                                f'{ch_name} updated:\n'
                                f'{update_info}'
                    )


async def fill_sanity():
    if setu_control.happy_hours:
        setu_control.fill_sanity(sanity=5)
    else:
        setu_control.fill_sanity(sanity=1)


async def do_youtube_update_fetch():
    file = open('config/YouTubeNotify.json')
    fl = file.read()

    youtube_notify_dict = json.loads(str(fl))
    if youtube_notify_dict:
        bot = nonebot.get_bot()
        for elements in youtube_notify_dict:
            if not youtube_notify_dict[elements]['status']:
                if youtube_notify_dict[elements]['retcode'] == 0:
                    group_id = int(youtube_notify_dict[elements]['group_id'])
                    try:
                        name = youtube_notify_dict[elements]['ch_name']
                        await bot.send_private_msg(
                            user_id=SUPER_USER,
                            message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]'
                                    f'Video is now available for group {group_id}\n'
                                    f'Video title: {elements}'
                        )

                        await bot.upload_group_file(
                            group_id=group_id,
                            file=f"{PATH_TO_ONEDRIVE}{name}/{elements}.mp4",
                            name=f"{elements}.mp4"
                        )

                    except Exception as err:
                        logger.warning(f'扒源error：{err}')
                        await bot.send_group_msg(
                            group_id=group_id,
                            message=f'视频上传失败，请检查群空间是否足够。'
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
                    logger.warning('Something went wrong %s' % e)

        file.close()
        empty_dict = {}
        with open('config/YouTubeNotify.json', 'w+') as f:
            json.dump(empty_dict, f, indent=4)


async def do_tweet_update_fetch():
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

            for element in group_id_list:
                setu_control.set_user_data(0, 'tweet', 'null', 1, True)
                await bot.send_group_msg(group_id=element,
                                         message=message)
                await bot.send_private_msg(
                    user_id=SUPER_USER,
                    message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                            f'A message was sent to group: {element}\n'
                            f'The group belongs to: {ch_name}'
                )


# 如果需要bilibili直播间提醒请把这部分的注释去掉。
"""
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
"""


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
