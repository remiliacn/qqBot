import nonebot
from aiocqhttp import MessageSegment

from Services.util.ctx_utility import get_user_id, get_group_id
from awesome.Constants import group_permission
from awesome.Constants.user_permission import OWNER
from awesome.plugins.admin_setting.admin_setting import get_privilege
from awesome.plugins.util.helper_util import set_group_permission
from config import SUPER_USER
from qq_bot_core import admin_group_control


@nonebot.on_command('antirecall', only_to_me=False)
async def anti_recall_setting(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), OWNER):
        return

    if 'group_id' not in ctx:
        return

    group_id = get_group_id(ctx)
    arg = session.current_arg

    set_group_permission(arg, group_id, group_permission.RECALL)
    await session.finish('Done')


@nonebot.on_notice('group_card')
async def _group_card_change_handler(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)
    group_id = get_group_id(ctx)
    if user_id == session.self_id:
        bot = nonebot.get_bot()
        await bot.set_group_card(
            group_id=group_id,
            user_id=session.self_id,
            card=ctx['card_old']
        )


@nonebot.on_notice('group_ban')
async def _group_handle_ban_events(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)
    group_id = get_group_id(ctx)
    duration = ctx['duration']

    if user_id == session.self_id and duration >= 60 * 60 * 24:
        bot = nonebot.get_bot()
        await bot.set_group_leave(group_id=group_id)
        await bot.send_private_msg(user_id=SUPER_USER, message=f'Quitting group: {group_id} because long ban time.')


@nonebot.on_notice('group_recall')
async def _recall_handler(session: nonebot.NoticeSession):
    ctx = session.ctx.copy()
    group_id = get_group_id(ctx)

    recall_setting = admin_group_control.get_group_permission(
        group_id=group_id,
        tag=group_permission.RECALL
    )

    if not recall_setting:
        return

    ctx = session.ctx.copy()
    message_id = ctx['message_id']
    group_id = get_group_id(ctx)
    user_id = get_user_id(ctx)

    if ctx['operator_id'] != user_id:
        return

    bot = nonebot.get_bot()
    message = await bot.get_msg(message_id=message_id)

    await bot.send_group_msg(
        group_id=group_id,
        message=f'{MessageSegment.at(user_id=user_id)} 发生什么事情了别藏着掖着呀ww\n'
                f'你撤回了：\n'
                f'{str(message["message"])}'
    )
