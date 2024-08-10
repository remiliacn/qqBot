from nonebot import on_command, on_notice
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, GroupBanNoticeEvent, Bot
from nonebot.internal.matcher import Matcher
from nonebot.params import CommandArg

from Services.util.ctx_utility import get_user_id
from awesome.Constants import group_permission
from awesome.Constants.user_permission import OWNER
from awesome.adminControl import get_privilege
from config import SUPER_USER
from util.helper_util import set_group_permission

anti_recall_cmd = on_command('antirecall')


@anti_recall_cmd.handle()
async def anti_recall_setting(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not get_privilege(get_user_id(event), OWNER):
        return

    group_id = event.group_id
    arg = args.extract_plain_text()

    await matcher.finish(f'Done {set_group_permission(arg, group_id, group_permission.RECALL)}')


group_ban_cmd = on_notice(priority=7, block=False)


@group_ban_cmd.handle()
async def _group_handle_ban_events(bot: Bot, event: GroupBanNoticeEvent):
    user_id = event.get_user_id()
    group_id = event.group_id
    duration = event.duration

    if user_id == event.self_id and duration >= 60 * 60 * 24:
        await bot.set_group_leave(group_id=group_id)
        await bot.send_private_msg(user_id=SUPER_USER,
                                   message=f'Quitting group: {group_id} because long ban time.')
