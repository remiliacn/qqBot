import asyncio
from json import loads
from typing import List

import nonebot
from loguru import logger

from Services.discord_service import DiscordService
from Services.live_notification import LiveNotification, BilibiliDynamicNotifcation
from Services.twitch_service import TwitchService, TwitchClippingService
from Services.util.ctx_utility import get_user_id, get_group_id
from awesome.Constants.user_permission import ADMIN
from config import SUPER_USER
from qq_bot_core import user_control_module

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)
live_notification = LiveNotification()
twitch_notification = TwitchService()
dynamic_notification = BilibiliDynamicNotifcation()
twitch_clipping = TwitchClippingService()
discord_notification = DiscordService()


async def start_verification(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)
    if 'group_id' not in ctx:
        return False

    if not user_control_module.get_user_privilege(user_id, ADMIN):
        return False

    return True


@nonebot.on_command('停止b站监控', only_to_me=False)
async def stop_bilibili_live_spying(session: nonebot.CommandSession):
    if not await start_verification(session):
        return

    args = session.current_arg_text.strip()
    await live_notification.stop_live_follow(args)
    await session.finish('整好了啦~')


@nonebot.on_command('b站监控', only_to_me=False)
async def bilibili_live_tracking(session: nonebot.CommandSession):
    if not await start_verification(session):
        return

    args = session.current_arg_text.split()
    if not args:
        return

    args = list(map(lambda x: x.strip(), args))
    if len(args) < 2 or len(args) > 3:
        await session.finish('用法错误，！b站监控 主播名 房间号 群号（可选）')

    if len(args) == 2:
        await live_notification.add_data_to_bilibili_notify_database(
            args[0],
            args[1],
            str(get_group_id(session.ctx.copy())))
        await session.finish('整好了')

    if not args[2].isdigit():
        await session.finish('您家群号长这样？')

    await twitch_notification.add_data_to_twitch_notify_database(args[0], args[1])


@nonebot.on_command('切片', only_to_me=False)
async def twitch_live_tracking(session: nonebot.CommandSession):
    group_id = get_group_id(session.ctx.copy())
    if group_id == -1:
        return

    args = session.current_arg_text
    verification_status = await twitch_clipping.analyze_clip_comment(args, session)
    if not verification_status.is_success:
        await session.finish(verification_status.message)

    download_status = await twitch_clipping.download_twitch_videos(verification_status.message)
    await session.finish(download_status.message)


@nonebot.on_command('twitch监控', only_to_me=False)
async def twitch_live_tracking(session: nonebot.CommandSession):
    if not await start_verification(session):
        return

    args = session.current_arg_text.split()
    if not args:
        return

    args = list(map(lambda x: x.strip(), args))
    if len(args) != 1 and len(args) != 2:
        await session.finish('用法错误，！twitch监控 主播名 群号（可选）')

    if len(args) == 1:
        await twitch_notification.add_data_to_twitch_notify_database(args[0], str(get_group_id(session.ctx.copy())))
        await session.finish('整好了')

    if not args[1].isdigit():
        await session.finish('您家群号长这样？')

    await twitch_notification.add_data_to_twitch_notify_database(args[0], args[1])


@nonebot.on_command('b站动态监控', only_to_me=False)
async def bilibili_dynamic_track(session: nonebot.CommandSession):
    if not await start_verification(session):
        return

    args = session.current_arg_text.split()
    if not args:
        return

    args = list(map(lambda x: x.strip(), args))
    if len(args) < 2 or len(args) > 3:
        await session.finish('用法错误，！b站动态监控 用户名 用户UID 群号（可选）')

    if len(args) == 2:
        await dynamic_notification.add_to_dynamic_notification_queue(
            args[0],
            args[1],
            str(get_group_id(session.ctx.copy())))
        await session.finish('整好了')

    if not args[2].isdigit():
        await session.finish('您家群号长这样？')

    await dynamic_notification.add_to_dynamic_notification_queue(args[0], args[1], args[2])


@nonebot.scheduler.scheduled_job('interval', minutes=1, misfire_grace_time=5)
async def scheduled_jobs():
    await asyncio.gather(do_bilibili_live_fetch(), do_dynamic_fetch(), do_discord_live_fetch())


# async def do_twitch_live_fetch():
#     logger.info('Automatically fetching twitch live info...')
#     live_notification_data_list = await twitch_notification.check_live_twitch()
#
#     bot = nonebot.get_bot()
#     for data in live_notification_data_list:
#         logger.info(f'New data found for {data.streamer_name}. twitch live.')
#         notify_group = loads(twitch_notification.get_group_ids_for_streamer(data.streamer_name))
#         if notify_group is None:
#             continue
#         for group in notify_group:
#             await bot.send_group_msg(
#                 group_id=int(group),
#                 message=await twitch_notification.convert_live_data_to_string(data))


async def do_discord_live_fetch():
    logger.info('Automatically fetching discord info...')
    data_list = await discord_notification.check_discord_updates()
    bot = nonebot.get_bot()

    for data in data_list:
        logger.info(f'New data found for {data.channel_name} for discord')
        notify_group = loads(discord_notification.get_group_ids_for_notification(data.channel_id))
        if notify_group is None:
            continue
        for group in notify_group:
            if data.is_success:
                await bot.send_group_msg(
                    group_id=int(group),
                    message=await discord_notification.group_notification_to_literal_string(data))
            else:
                await bot.send_private_msg(
                    user_id=SUPER_USER,
                    message=f'discord动态更新出了点小问题，user：{data.channel_name},'
                            f' channel id: {data.channel_id},'
                            f' error message: {data.message}')


async def do_bilibili_live_fetch():
    logger.info('Automatically fetching bilibili live info...')
    live_notification_data_list = await live_notification.check_live_bilibili()

    bot = nonebot.get_bot()
    for data in live_notification_data_list:
        logger.info(f'New data found for {data.streamer_name}. bilibili live.')
        notify_group = loads(live_notification.get_group_ids_for_streamer(data.streamer_name))
        if notify_group is None:
            continue
        for group in notify_group:
            await bot.send_group_msg(
                group_id=int(group),
                message=await live_notification.convert_live_data_to_string(data))

    unpickled_danmaku_datas = live_notification.get_dumped_live_data()
    for danmaku_data in unpickled_danmaku_datas:
        notified_group: List[str] = loads(danmaku_data.qq_group_dumped)
        for group in notified_group:
            await bot.send_group_msg(
                group_id=int(group),
                message=live_notification.stringify_danmaku_data(danmaku_data))


async def do_dynamic_fetch():
    logger.info('Automatically fetching bilibili dynamic info...')
    data_list = await dynamic_notification.fetch_all_dynamic_updates()

    bot = nonebot.get_bot()
    for data in data_list:
        logger.info(f'New data found for {data.name}. Dynamic.')
        notify_group = await dynamic_notification.get_group_to_notify(data.name)
        if notify_group is None:
            continue
        for group in notify_group:
            dynamic_message = await dynamic_notification.construct_string_from_data(data)
            if dynamic_message.strip():
                logger.success(dynamic_message)
                await bot.send_group_msg(
                    group_id=int(group),
                    message=dynamic_message.strip()
                )
