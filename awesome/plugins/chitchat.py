import nonebot
import os
import random
import re
import time

from awesome.adminControl import permission as perm
from awesome.adminControl import group_admin, user_control
from awesome.plugins.util.helper_util import get_downloaded_image_path


class Votekick:
    def __init__(self):
        self.vote_kick_dict = {}

    def get_vote_kick(self, qq_num):
        if qq_num not in self.vote_kick_dict:
            self.vote_kick_dict[qq_num] = 1
            return 1

        self.vote_kick_dict[qq_num] += 1
        return self.vote_kick_dict[qq_num]

admin_control = group_admin.Shadiaoadmin()
vote_kick_controller = Votekick()

user_control_module = user_control.UserControl()

get_privilege = lambda x, y : user_control_module.get_user_privilege(x, y)

@nonebot.on_command('添加图片', only_to_me=False)
async def add_more_pic(session: nonebot.CommandSession):
    types = ('恰柠檬', '泪流猫猫头', '迫害', '辛苦了', '不愧是你', '威胁', '社保', '恰桃')
    prompt_info = f'请输入要加入的类型，类型应该为这其中的一个：{types}\n' \
                  f'然后添加一个空格再加上需要添加的图'

    key_word = session.get('key_word', prompt=prompt_info)
    args = key_word.split()

    if args[0] not in types:
        await session.finish('不是说了必须是其中一个了kora')

    key_dict = {
        '恰柠檬': f'{os.getcwd()}/data/dl/lemon/',
        '泪流猫猫头': f'{os.getcwd()}/data/dl/useless/',
        '迫害': f'{os.getcwd()}/data/dl/pohai/',
        '辛苦了': f'{os.getcwd()}/data/dl/otsukare/',
        '不愧是你': f'{os.getcwd()}/data/dl/bukui/',
        '威胁': f'{os.getcwd()}/data/dl/weixie/',
        '社保': f'{os.getcwd()}/data/dl/shebao/',
        '恰桃': f'{os.getcwd()}/data/dl/peach/',
    }

    path = key_dict[args[0]]

    has_image = re.findall(r'.*?file=(.*?\.image)', args[1])
    if has_image:
        bot = nonebot.get_bot()
        response = await bot.get_image(file=has_image[0])
        _ = get_downloaded_image_path(response, path)
        await session.finish('图片已添加！')

    await session.finish('你发的smjb玩意……')

@nonebot.on_command('?', aliases='？', only_to_me=False)
async def change_question_mark(session : nonebot.CommandSession):
    await session.send('¿?¿?')

@nonebot.on_command('你好', only_to_me=False)
async def send_hello_world(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.OWNER):
        await session.send('妈妈好~')
    else:
        await session.send('你好呀~' + ctx['sender']['nickname'])

@nonebot.on_command('内鬼', aliases='有没有内鬼', only_to_me=False)
async def nei_gui_response(session : nonebot.CommandSession):
    random.seed(time.time_ns())
    rand_num = random.randint(0, 50)
    ctx = session.ctx.copy()
    if rand_num >= 26 and not get_privilege(ctx['user_id'], perm.OWNER):
        qq_num = ctx['user_id']
        await session.send(f'哦屑！有内鬼！终止交易！！ \n'
                           f'TA的QQ号是：{qq_num}！！！ \n'
                           f'QQ昵称是：{ctx["sender"]["nickname"]}')

    else:
        await session.send('一切安全！开始交易！')

@nonebot.on_command('生草', only_to_me=False)
async def vtuber_audio(session : nonebot.CommandSession):
    key_word : str = session.get_optional('key_word')
    if key_word is None:
        file = await get_random_file(f'{os.getcwd()}/data/dl/audio')
    elif '鹿乃' in key_word:
        file = 'pa0.wav'
    elif '盘子' in key_word:
        file = '05-1.mp3'
    elif '恋口上' in key_word:
        file = 'a0616-12.mp3'
    elif 'seaside' in key_word.lower():
        file = '34-1.mp3'
    elif '恩' in key_word or '嗯' in key_word:
        file = '71.mp3'
    elif '唱歌' in key_word:
        file = 'a-207.mp3'
    else:
        file = await get_random_file(f'{os.getcwd()}/data/dl/audio')

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
    file = await get_random_file(f'{os.getcwd()}/data/dl/useless')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('威胁', only_to_me=False)
async def threat_send(session : nonebot.CommandSession):
    file = await get_random_file(f'{os.getcwd()}/data/dl/weixie')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('恰柠檬', aliases='吃柠檬', only_to_me=False)
async def lemon_send(session : nonebot.CommandSession):
    file = await get_random_file(f'{os.getcwd()}/data/dl/lemon')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('迫害', only_to_me=False)
async def send_pohai(session : nonebot.CommandSession):
    file = await get_random_file(f'{os.getcwd()}/data/dl/pohai')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('不愧是你', aliases='bukui', only_to_me=False)
async def bu_kui_send(session : nonebot.CommandSession):
    file = await get_random_file(f'{os.getcwd()}/data/dl/bukui')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('恰桃', aliases='恰peach', only_to_me=False)
async def send_peach(session : nonebot.CommandSession):
    file = await get_random_file(f'{os.getcwd()}/data/dl/peach')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('社保', aliases='awsl', only_to_me=False)
async def she_bao(session : nonebot.CommandSession):
    file = await get_random_file(f'{os.getcwd()}/data/dl/shebao')
    await session.send(f'[CQ:image,file=file:///{file}]')

@nonebot.on_command('votekick', only_to_me=False)
async def vote_kick_person(session : nonebot.CommandSession):
    ctx = session.ctx.copy()
    message = ctx['raw_message']
    if re.match(r'.*?CQ:at,qq=\d+', str(message)):
        qq_num = re.findall(r'CQ:at,qq=(\d+)', message)[0]
        if get_privilege(ctx['user_id'], perm.OWNER):
            await session.finish('民意说踢………你踢你🐴呢')

        await session.finish(f'民意说踢出[CQ:at,qq={qq_num}]的人有{vote_kick_controller.get_vote_kick(qq_num)}个')

@nonebot.on_command('otsukare', aliases=('おつかれ', '辛苦了'), only_to_me=False)
async def otsukare(session : nonebot.CommandSession):
    file = await get_random_file(f'{os.getcwd()}/data/dl/otsukare')
    await session.send(f'[CQ:image,file=file:///{file}]')

async def get_random_file(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f'No image found in default location: {path}')

    file = os.listdir(path)
    return path + '/' + random.choice(file)