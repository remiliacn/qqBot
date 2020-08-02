import nonebot, random, time, os, re
from awesome.adminControl import shadiaoAdmin

class Votekick:
    def __init__(self):
        self.vote_kick_dict = {}

    def get_vote_kick(self, qq_num):
        if qq_num not in self.vote_kick_dict:
            self.vote_kick_dict[qq_num] = 1
            return 1

        self.vote_kick_dict[qq_num] += 1
        return self.vote_kick_dict[qq_num]

admin_control = shadiaoAdmin.Shadiaoadmin()
vote_kick_controller = Votekick()

@nonebot.on_command('?', aliases='？', only_to_me=False)
async def change_question_mark(session : nonebot.CommandSession):
    await session.send('¿?¿?')

@nonebot.on_command('你好', only_to_me=False)
async def send_hello_world(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if ctx['user_id'] == 634915227:
        await session.send('妈妈好~')
    else:
        await session.send('你好呀~' + ctx['sender']['nickname'])

@nonebot.on_command('内鬼', aliases='有没有内鬼', only_to_me=False)
async def nei_gui_response(session : nonebot.CommandSession):
    random.seed(time.time_ns())
    rand_num = random.randint(0, 50)
    ctx = session.ctx.copy()
    if rand_num >= 26 and ctx['user_id'] != 634915227:
        qq_num = ctx['user_id']
        await session.send('哦屑！有内鬼！终止交易！！ \nTA的QQ号是：%d！！！ \nQQ昵称是：%s' % (qq_num, ctx['sender']['nickname']))

    else:
        await session.send('一切安全！开始交易！')

@nonebot.on_command('生草', only_to_me=False)
async def vtuber_audio(session : nonebot.CommandSession):
    key_word = session.get_optional('key_word')
    key_word = str(key_word)
    if re.match(r'.*?鹿乃', key_word):
        file = 'pa0.wav'
    elif re.match(r'.*?盘子', key_word):
        file = '05-1.mp3'
    elif re.match(r'.*?恋口上', key_word):
        file = 'a0616-12.mp3'
    elif re.match(r'.*?seaside', str(key_word).lower()):
        file = '34-1.mp3'
    elif re.match(r'.*?([恩嗯])', key_word):
        file = '71.mp3'
    elif re.match(r'.*?唱歌', key_word):
        file = 'a-207.mp3'
    else:
        file = await get_random_file('C:/dl/audio')

    await session.finish(f'[CQ:record,file=file:///{file}]')

@vtuber_audio.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    session.state[session.current_key] = stripped_arg

@nonebot.on_command('我什么都不行', aliases={'什么都不行', '都不行', '不行', '流泪猫猫头'}, only_to_me=False)
async def useless_send(session : nonebot.CommandSession):
    file = await get_random_file('C:/dl/useless')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('威胁', only_to_me=False)
async def threat_send(session : nonebot.CommandSession):
    file = await get_random_file('C:/dl/weixie')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('恰柠檬', aliases='吃柠檬', only_to_me=False)
async def lemon_send(session : nonebot.CommandSession):
    file = await get_random_file('C:/dl/lemon')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('迫害', only_to_me=False)
async def send_pohai(session : nonebot.CommandSession):
    file = await get_random_file('C:/dl/pohai')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('不愧是你', aliases='bukui', only_to_me=False)
async def bu_kui_send(session : nonebot.CommandSession):
    file = await get_random_file('C:/dl/bukui')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('恰桃', aliases='恰peach', only_to_me=False)
async def send_peach(session : nonebot.CommandSession):
    file = await get_random_file('C:/dl/peach')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('社保', aliases='awsl', only_to_me=False)
async def she_bao(session : nonebot.CommandSession):
    file = await get_random_file('C:/dl/shebao')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('votekick', only_to_me=False)
async def vote_kick_person(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    message = ctx['raw_message']
    if re.match(r'.*?CQ:at,qq=\d+', str(message)):
        qq_num = re.findall(r'CQ:at,qq=(\d+)', message)[0]
        if qq_num == "2044450237" or qq_num == "634915227":
            await session.finish('民意说踢………你踢你🐴呢')
        await session.finish(f'民意说踢出[CQ:at,qq={qq_num}]的人有{vote_kick_controller.get_vote_kick(qq_num)}个')

@nonebot.on_command('otsukare', aliases=('おつかれ', '辛苦了'), only_to_me=False)
async def otsukare(session : nonebot.CommandSession):
    file = await get_random_file('C:/dl/otsukare')
    await session.send(f'[CQ:image,file=file:///{file}]')

async def get_random_file(path: str) -> str:
    file = os.listdir(path)
    fileCount = len(file) - 1
    random.seed(time.time_ns())
    rand_num = random.randint(0, fileCount)
    return path + '/' + file[rand_num]