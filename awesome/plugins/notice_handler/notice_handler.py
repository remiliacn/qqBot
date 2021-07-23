import nonebot
from aiocqhttp import MessageSegment

from awesome.adminControl.permission import OWNER
from awesome.plugins.admin_setting.admin_setting import get_privilege
from qq_bot_core import admin_control


@nonebot.on_command('antirecall', only_to_me=False)
async def anti_recall_setting(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], OWNER):
        return

    if 'group_id' not in ctx:
        return

    group_id = ctx['group_id']
    arg = session.current_arg
    if '开' in arg:
        admin_control.set_group_permission(group_id=group_id, tag='recall', stat=True)
    else:
        admin_control.set_group_permission(group_id=group_id, tag='recall', stat=False)

    await session.finish('Done')


@nonebot.on_notice('group_recall')
async def _recall_handler(session: nonebot.NoticeSession):
    ctx = session.ctx.copy()
    group_id = ctx['group_id']

    recall_setting = admin_control.get_group_permission(
        group_id=group_id,
        tag='recall',
        default_if_none=False
    )

    if not recall_setting:
        return

    ctx = session.ctx.copy()
    message_id = ctx['message_id']
    group_id = ctx['group_id']
    user_id = ctx['user_id']

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
