from re import match, findall
from subprocess import Popen

import json
import nonebot

from awesome.adminControl import permission as perm
from awesome.plugins.admin_setting import user_control_module

get_privilege = lambda x, y : user_control_module.get_user_privilege(x, y)

@nonebot.on_command('下源', only_to_me=False)
async def getVideoFromID(session : nonebot.CommandSession):
    if not getStatus():
        await session.send('机器人正忙，请稍后……')
        return

    ctx = session.ctx.copy()
    idNum = ctx['user_id']

    videoID = session.get('videoID', prompt='需要一个YouTube视频ID，请提供！')
    if len(videoID) > 12:
        if match(r'.*?https://www.youtube.com/watch\?v=', videoID):
            videoID = findall(r'v=([A-Za-z0-9\-_]{11})', videoID)[0]

        elif match(r'.*?youtu\.be/[A-Za-z0-9\-_]{11}', videoID):
            videoID = findall(r'.*?youtu\.be/([A-Za-z0-9\-_]{11})', videoID)[0]

        else:
            await session.send('你发了个什么鬼给我……')
            return

    await session.send('我要开始了')
    if 'group_id' in ctx:
        idNum = ctx['group_id']
    Popen('py D:/forDownload.py single %s %d' % (videoID, idNum), stdin=None, stdout=None, stderr=None, close_fds=True)

@nonebot.on_command('checkNow', only_to_me=False)
async def checkNow(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.OWNER):
        Popen('py D:/forDownload.py bulk', stdin=None, stdout=None, stderr=None, close_fds=True, shell=True)

@nonebot.scheduler.scheduled_job('interval', seconds=1200)
async def downloadVideo():
    Popen('py D:/forDownload.py bulk', stdin=None, stdout=None, stderr=None, close_fds=True)

def getStatus():
    file = open('D:/dl/started.json', 'r')
    statusDict = json.loads(str(file.read()))
    return statusDict['status']

