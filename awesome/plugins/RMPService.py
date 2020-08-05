import nonebot, asyncio
from RMPClass import RMPClass

@nonebot.on_command('老师评分', only_to_me=False)
async def get_rmp_rating(session : nonebot.CommandSession):
    teacher_name = session.get('teacher_name', prompt='请输入需要查询的老师全名（暂时只支持ASU老师）')

    api = RMPClass.RateMyProfAPI(teacher=teacher_name)
    api.retrieve_rmp_info()
    if api.get_rmp_info() == '/5.0':
        await session.finish('好像什么没有查到！换一个名字试试？')

    await session.send('热门标签：%s\n评分%s' % (api.get_first_tag(), api.get_rmp_info()))

@nonebot.on_command('课程查询', only_to_me=False)
async def getASUClassInfos(session : nonebot.CommandSession):
    major = session.get('major', prompt='请输入课程代码（如：CSE）')
    code = session.get('code', prompt='请输入课程编号（如：230）')
    api = RMPClass.ASUClassFinder(major=major, code=code)
    await session.send('已查询到 %d 个结果' % api.get_elements_count())
    await asyncio.sleep(0.5)
    await session.send(api.__str__())

@get_rmp_rating.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['teacher_name'] = stripped_arg
        return

    session.state[session.current_key] = stripped_arg