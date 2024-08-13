import asyncio
from json import loads
from time import time
from traceback import format_exc
from typing import List

from nonebot import get_driver, on_command, get_bot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent, Message, Bot
from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot_plugin_apscheduler import scheduler

from Services import live_notification, twitch_notification, twitch_clipping, dynamic_notification, discord_notification
from Services.twitch_service import TwitchClipInstruction
from Services.util.ctx_utility import get_user_id, get_group_id
from awesome.Constants.user_permission import ADMIN
from awesome.adminControl import user_control
from util.helper_util import construct_message_chain

global_config = get_driver().config


async def start_verification(event: GroupMessageEvent | PrivateMessageEvent):
    user_id = get_user_id(event)
    if not user_control.get_user_privilege(user_id, ADMIN):
        return False

    return True


stop_bilibili_monitor_cmd = on_command('停止b站监控')


@stop_bilibili_monitor_cmd.handle()
async def stop_bilibili_live_spying(event: GroupMessageEvent | PrivateMessageEvent, matcher: Matcher,
                                    args: Message = CommandArg()):
    if not await start_verification(event):
        return

    args = args.extract_plain_text().strip()
    await live_notification.stop_live_follow(args)
    await matcher.finish('整好了啦~')


start_b2_monitor_cmd = on_command('b站监控')


@start_b2_monitor_cmd.handle()
async def bilibili_live_tracking(
        event: GroupMessageEvent | PrivateMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not await start_verification(event):
        return

    args = args.extract_plain_text().strip().split()
    if not args:
        return

    args = [x.strip() for x in args]
    if len(args) < 2 or len(args) > 3:
        await matcher.finish('用法错误，！b站监控 主播名 房间号 群号（可选）')

    if len(args) == 2:
        await live_notification.add_data_to_bilibili_notify_database(
            args[0],
            args[1],
            str(get_group_id(event)))
        await matcher.finish('整好了')

    if not args[2].isdigit():
        await matcher.finish('您家群号长这样？')

    await twitch_notification.add_data_to_twitch_notify_database(args[0], args[1])


twitch_clip_cmd = on_command('切片')


@twitch_clip_cmd.handle()
async def twitch_live_tracking(bot: Bot, event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    args = args.extract_plain_text().strip()
    verification_status = await twitch_clipping.analyze_clip_comment(args, matcher)
    if not verification_status.is_success:
        await matcher.finish(verification_status.message)

    twitch_clip_instruction: TwitchClipInstruction = verification_status.message
    download_status = await twitch_clipping.download_twitch_videos(twitch_clip_instruction)
    logger.info(f'Received download status: {download_status}')

    await matcher.send(download_status.message)
    try:
        temp_group_filename = f'{str(int(time()))}.mp4'
        temp_group_filename = twitch_clip_instruction.file_name if twitch_clip_instruction.file_name else temp_group_filename
        if download_status.is_success and download_status.file_path:
            logger.info(f'Trying to upload the group file. {download_status.file_path}')
            await bot.call_api(
                'upload_group_file',
                group_id=event.group_id,
                file=f'{download_status.file_path}',
                name=temp_group_filename,
                folder='/'
            )
            logger.success(f'Group file transfer completed. {temp_group_filename}')
    except Exception as err:
        logger.error(f'Failed to upload to group file. skipping that. {err.__class__}')


start_twitch_monitor_cmd = on_command('twitch监控')


@start_twitch_monitor_cmd.handle()
async def twitch_live_tracking(
        event: GroupMessageEvent | PrivateMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not await start_verification(event):
        return

    args = args.extract_plain_text().strip().split()
    if not args:
        return

    args = [x.strip() for x in args]
    if len(args) != 1 and len(args) != 2:
        await matcher.finish('用法错误，！twitch监控 主播名 群号（可选）')

    if len(args) == 1:
        await twitch_notification.add_data_to_twitch_notify_database(args[0], str(get_group_id(event)))
        await matcher.finish('整好了')

    if not args[1].isdigit():
        await matcher.finish('您家群号长这样？')

    await twitch_notification.add_data_to_twitch_notify_database(args[0], args[1])


start_b2_dynamic_cmd = on_command('b站动态监控')


@start_b2_dynamic_cmd.handle()
async def bilibili_dynamic_track(
        event: GroupMessageEvent | PrivateMessageEvent,
        matcher: Matcher,
        args: Message = CommandArg()):
    if not await start_verification(event):
        return

    args = args.extract_plain_text().strip().split()
    if not args:
        return

    args = [x.strip() for x in args]
    if len(args) < 2 or len(args) > 3:
        await matcher.finish('用法错误，！b站动态监控 用户名 用户UID 群号（可选）')

    if len(args) == 2:
        await dynamic_notification.add_to_dynamic_notification_queue(
            args[0],
            args[1],
            str(get_group_id(event)))
        await matcher.finish('整好了')

    if not args[2].isdigit():
        await matcher.finish('您家群号长这样？')

    await dynamic_notification.add_to_dynamic_notification_queue(args[0], args[1], args[2])


@scheduler.scheduled_job('interval', minutes=1, misfire_grace_time=5)
async def scheduled_jobs():
    try:
        await asyncio.gather(do_bilibili_live_fetch(), do_dynamic_fetch(), do_discord_live_fetch())
    except Exception as err:
        logger.error(f'Something went wrong with scheduled jobs. {err.__class__}')
        logger.error(format_exc())


async def do_discord_live_fetch():
    logger.info('Automatically fetching discord info...')
    data_list = await discord_notification.check_discord_updates()
    bot = get_bot()

    for data in data_list:
        logger.info(f'New data found for {data.channel_name} for discord')
        notify_group = loads(discord_notification.get_group_ids_for_notification(data.channel_id))
        if notify_group is None:
            continue
        for group in notify_group:
            if data.is_success:
                await bot.call_api(
                    'send_group_msg',
                    group_id=int(group),
                    message=await discord_notification.group_notification_to_literal_string(data))
            else:
                await bot.call_api('send_private_msg',
                                   user_id=global_config.SUPER_USER,
                                   message=f'discord动态更新出了点小问题，user：{data.channel_name},'
                                           f' channel id: {data.channel_id},'
                                           f' error message: {data.message}')


async def do_bilibili_live_fetch():
    logger.info('Automatically fetching bilibili live info...')
    live_notification_data_list = await live_notification.check_live_bilibili()

    bot = get_bot()
    for data in live_notification_data_list:
        logger.info(f'New data found for {data.streamer_name}. bilibili live.')
        notify_group = loads(live_notification.get_group_ids_for_streamer(data.streamer_name))
        if notify_group is None:
            continue
        for group in notify_group:
            await bot.call_api('send_group_msg',
                               group_id=int(group),
                               message=construct_message_chain(
                                   await live_notification.convert_live_data_to_string(data)))

    unpickled_danmaku_datas = live_notification.get_dumped_live_data()
    for danmaku_data in unpickled_danmaku_datas:
        notified_group: List[str] = loads(danmaku_data.qq_group_dumped)
        for group in notified_group:
            await bot.call_api('send_group_msg',
                               group_id=int(group),
                               message=live_notification.stringify_danmaku_data(danmaku_data))


async def do_dynamic_fetch():
    logger.info('Automatically fetching bilibili dynamic info...')
    data_list = await dynamic_notification.fetch_all_dynamic_updates()

    bot = get_bot()
    for data in data_list:
        logger.info(f'New data found for {data.name}. Dynamic.')
        notify_group = await dynamic_notification.get_group_to_notify(data.name)
        if notify_group is None:
            continue
        for group in notify_group:
            dynamic_message = await dynamic_notification.construct_string_from_data(data)
            if dynamic_message:
                logger.success(dynamic_message)
                await bot.call_api('send_group_msg',
                                   group_id=int(group),
                                   message=dynamic_message)
