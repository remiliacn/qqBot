import nonebot, asyncio
from RMPClass import RMPClass, classNotifier

@nonebot.on_command('老师评分', only_to_me=False)
async def getRMPRating(session : nonebot.CommandSession):
    teacherName = session.get('teacherName', prompt='请输入需要查询的老师全名（暂时只支持ASU老师）')

    api = RMPClass.RateMyProfAPI(teacher=teacherName)
    api.retrieveRMPInfo()
    if api.getRMPInfo() == '/5.0':
        await session.send('好像什么没有查到！换一个名字试试？')
        return

    await session.send('热门标签：%s\n评分%s' % (api.getFirstTag(), api.getRMPInfo()))

@nonebot.on_command('课程查询', only_to_me=False)
async def getASUClassInfos(session : nonebot.CommandSession):
    major = session.get('major', prompt='请输入课程代码（如：CSE）')
    code = session.get('code', prompt='请输入课程编号（如：230）')
    api = RMPClass.ASUClassFinder(major=major, code=code)
    await session.send('已查询到 %d 个结果' % api.getElementsCount())
    await asyncio.sleep(0.5)
    await session.send(api.__str__())

@getRMPRating.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['teacherName'] = stripped_arg
        return

    session.state[session.current_key] = stripped_arg