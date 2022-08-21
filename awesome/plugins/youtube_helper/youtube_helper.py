import json
from re import match, findall
from subprocess import Popen

import nonebot

from Services.util.ctx_utility import get_user_id, get_group_id
from awesome.adminControl import permission as perm
from qq_bot_core import user_control_module

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)


@nonebot.on_command('添加下源', only_to_me=False)
async def add_auto_video_download(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(get_user_id(ctx), perm.WHITELIST):
        await session.finish()

    if 'group_id' not in ctx:
        return

    user_input: str = session.get(
        'videoID',
        prompt='使用方法：！添加下源 中文名 频道 是否开启（Y/N）'
    )

    args = user_input.split()
    if len(args) != 3:
        await session.finish('参数不够')

    if len(args[1]) < 23:
        await session.finish('频道名可能无效')

    if not match(r'[A-Za-z0-9\-_]{23,}', args[1]):
        await session.finish('频道名可能无效')

    if args[2].upper() != 'Y' and args[2].upper() != 'N':
        await session.finish('第三参数必须是Y或者N')

    ch_name = args[0]
    channel = args[1]
    group_id = get_group_id(ctx)
    enabled = args[2] == 'Y'

    with open('config/downloader.json', 'r') as file:
        existing_dict = json.loads(file.read())

    if ch_name not in existing_dict:
        existing_dict[ch_name] = {
            "channel": channel,
            "qqGroup": int(group_id),
            "videoID": "",
            "enabled": enabled
        }

    else:
        temp_dict = existing_dict[ch_name]
        if temp_dict['channel'] != channel:
            existing_dict[ch_name]['channel'] = channel

        if temp_dict['qqGroup'] != int(group_id):
            existing_dict[ch_name]['qqGroup'] = int(group_id)

        if temp_dict['enabled'] != enabled:
            existing_dict[ch_name]['enabled'] = enabled

    with open('config/downloader.json', 'w+') as file:
        json.dump(existing_dict, file, indent=4)

    await session.finish('添加成功！')


@nonebot.on_command('下源', only_to_me=False)
async def get_video_from_id(session: nonebot.CommandSession):
    if not get_status():
        await session.send('机器人正忙，请稍后……')
        return

    ctx = session.ctx.copy()
    id_num = get_user_id(ctx)

    video_id = session.get('video_id', prompt='需要一个YouTube视频ID，请提供！')
    if len(video_id) > 12:
        if match(r'.*?https://www.youtube.com/watch\?v=', video_id):
            video_id = findall(r'v=([A-Za-z0-9\-_]{11})', video_id)[0]

        elif match(r'.*?youtu\.be/[A-Za-z0-9\-_]{11}', video_id):
            video_id = findall(r'.*?youtu\.be/([A-Za-z0-9\-_]{11})', video_id)[0]

        else:
            await session.send('你发了个什么鬼给我……')
            return

    await session.send('我要开始了，源下载好了会尝试上传群文件，请保证充足群空间~')
    if 'group_id' in ctx:
        id_num = get_group_id(ctx)
    Popen('py for_download.py single %s %d' % (video_id, id_num), stdin=None, stdout=None, stderr=None, close_fds=True)


@nonebot.on_command('checkNow', only_to_me=False)
async def check_now(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(get_user_id(ctx), perm.OWNER):
        Popen('py for_download.py bulk', stdin=None, stdout=None, stderr=None, close_fds=True, shell=True)


def get_status():
    file = open('data/started.json', 'r')
    status_dict = json.loads(str(file.read()))
    return status_dict['status']


@get_video_from_id.args_parser
@add_auto_video_download.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['video_id'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('要查询的关键词不能为空')

    session.state[session.current_key] = stripped_arg
