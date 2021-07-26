import asyncio
import datetime
from random import randint, seed, choice
from time import time_ns

import china_idiom as idiom
import nonebot

from Services import poker_game, ru_game
from awesome.adminControl import permission as perm
from awesome.plugins.shadiao.shadiao import admin_control, setu_control
from qq_bot_core import user_control_module

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)


class Storer:
    def __init__(self):
        self.stored_result = {}

    def set_store(self, function, ref, group_id: str, is_global: bool, user_id='-1'):
        if group_id not in self.stored_result:
            self.stored_result[group_id] = {}

        if function not in self.stored_result[group_id]:
            self.stored_result[group_id][function] = {}
            if is_global:
                self.stored_result[group_id][function] = ref
            else:
                self.stored_result[group_id][function][user_id] = ref

    def get_store(self, group_id, function, is_global: bool, user_id='-1'):
        if group_id not in self.stored_result:
            self.stored_result[group_id] = {}
            return ''

        if function not in self.stored_result[group_id]:
            self.stored_result[group_id][function] = ''
            return ''

        if is_global:
            temp = self.stored_result[group_id][function]
            self.stored_result[group_id][function] = ''
            return temp
        else:
            if user_id not in self.stored_result[group_id][function]:
                return ''

            info = self.stored_result[group_id][function][user_id]
            self.stored_result[group_id][function][user_id] = ''
            return info


class Horseracing:
    def __init__(self, user_guess: str):
        self.user_guess = user_guess
        self.winning_goal = 7
        self.actual_winner = -1
        self.adding_dict = {
            "正在勇往直前！": 6,
            "正在一飞冲天！": 4,
            "提起马蹄子就继续往前冲冲冲": 4,
            "如同你打日麻放铳一样勇往直前！": 4,
            "如同你打日麻放铳一样疾步迈进！": 3,
            "艰难的往前迈了几步": 2,
            "使用了忍术！它！飞！起！来！了！": 2,
            "艰难的往前迈了一小步": 1,
            "晃晃悠悠的往前走了一步": 1,
            "它窜稀的后坐力竟然让它飞了起来！": 3,
            "终于打起勇气，往前走了……一步": 1,
            "终于打起勇气，往前走了……两步": 2,
            "终于打起勇气，往前走了……三步": 3,
        }

        self.subtracting_dict = {
            "被地上的沥青的颜色吓傻了！止步不前": 0,
            '被電マplay啦！爽的倒退了2步！': -2,
            "打假赛往反方向跑了！": -3,
            "被旁边的选手干扰的吓得往后退了几步": -2,
            "哼啊啊啊啊啊~的叫了起来，落后大部队！": -2,
            "马晕厥了！可能是中暑了！这下要麻烦了！": -5,
            "它它它，居然！马猝死了！哎？等会儿！好像它马又复活了": -10,
            "吃多了在窜稀，暂时失去了战斗力": -1,
            "觉得敌不动我不动，敌动了……我还是不能动": 0,
            "觉得现在这个位置的空气不错，决定多待会儿~": 0,
            "突然站在原地深情的开始感叹——watashi mo +1": 0,
            "决定在原地玩会儿明日方舟": 0,
            "决定在原地玩会儿fgo": 0,
            "决定在原地玩会儿日麻": 0,
        }

        self.horse_list = [0, 0, 0, 0, 0, 0]
        self.response_list = []

    def if_play(self):
        try:
            temp = int(self.user_guess)
            if temp > len(self.horse_list):
                return False

        except ValueError:
            return False

        return True

    def if_win(self):
        for idx, elements in enumerate(self.horse_list):
            if elements >= self.winning_goal:
                self.actual_winner = str(idx + 1)
                return True

        return False

    def who_win(self):
        return self.actual_winner

    def get_play_result(self):
        self.response_list.clear()
        resp = ""
        i = 0
        for idx, elements in enumerate(self.horse_list):
            if randint(0, 5) >= 2:
                this_choice = choice(list(self.adding_dict))
                self.horse_list[idx] += self.adding_dict[this_choice]
                self.response_list.append(str(i + 1) + "号马, " + this_choice)

            else:
                this_choice = choice(list(self.subtracting_dict))
                self.horse_list[idx] += self.subtracting_dict[this_choice]
                self.response_list.append(str(i + 1) + "号马, " + this_choice)

            i += 1

        for elements in self.response_list:
            resp += elements + "\n"

        return resp

    def player_win(self):
        if self.actual_winner == self.user_guess:
            return True

        return False


poker = poker_game.Pokergame()
GLOBAL_STORE = Storer()
game = ru_game.Russianroulette()


@nonebot.on_command('1d100', patterns=r'\d+[dD]\d+', only_to_me=False)
async def pao_tuan_shai_zi(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    message_id = ctx['message_id']

    raw_message = ctx['raw_message'].split()[0][1:].lower()
    args = raw_message.split('d')
    throw_times = int(args[0])
    if throw_times > 10:
        await session.finish('扔这么多干嘛，爬')

    max_val = int(args[1])
    result_list = [randint(1, max_val) for _ in range(throw_times)]
    result_sum = sum(result_list)

    await session.finish(
        f'[CQ:reply,id={message_id}]'
        f'筛子结果为：{", ".join([str(x) for x in result_list])}\n'
        f'筛子结果总和为：{result_sum}'
    )


@nonebot.on_command('赛马', only_to_me=False)
async def horse_race(session: nonebot.CommandSession):
    winner = session.get('winner', prompt='请输入一个胜方编号进行猜测（1-6）')
    race = Horseracing(winner)
    ctx = session.ctx.copy()
    user_id = ctx['user_id']

    if race.if_play():
        while not race.if_win():
            await session.send(race.get_play_result())
            await asyncio.sleep(2)

        if race.player_win():
            await session.send("恭喜你猜赢啦！")
            if 'group_id' in ctx:
                setu_control.set_user_data(user_id, 'horse_race')

        else:
            await session.send(f"啊哦~猜输了呢！其实是{race.who_win()}号赢了哦")


@horse_race.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['winner'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('请输入一个胜方编号进行猜测（1-6）')

    session.state[session.current_key] = stripped_arg


@nonebot.on_command('轮盘赌', only_to_me=False)
async def russian_roulette(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    id_num = ctx['group_id'] if 'group_id' in ctx else ctx['user_id']
    user_id = ctx['user_id']

    if 'group_id' in ctx:
        if admin_control.get_group_permission(ctx['group_id'], 'banned'):
            await session.send('已设置禁止该群的娱乐功能。如果确认这是错误的话，请联系bot制作者')
            return
    else:
        await session.finish('这是群组游戏！')

    if id_num not in game.game_dict:
        game.setUpDictByGroup(id_num)

    if user_id not in game.game_dict[id_num]["playerDict"]:
        game.add_player_in(group_id=id_num, user_id=user_id)
    else:
        game.add_player_play_time(group_id=id_num, user_id=user_id)

    play_time = game.get_play_time_with_user_id(group_id=id_num, user_id=user_id)
    message_id = ctx['message_id']
    if not game.get_result(id_num):
        await session.send(f'[CQ:reply,id={message_id}]咔')
    else:
        death = game.get_death(id_num)
        if get_privilege(user_id, perm.OWNER):
            await session.send(f'[CQ:reply,id={message_id}] sv_cheats 1 -> 成功触发免死\n'
                               '本应中枪几率为：%.2f' % (1 / (7 - death) * 100))
            return

        await session.send(
            f'[CQ:reply,id={message_id}]boom！你死了。这是第{death}枪，'
            f'理论几率为：{(1 / (7 - death) * 100):.2f}%'
        )
        setu_control.set_user_data(user_id, 'roulette')

        bot = nonebot.get_bot()
        if id_num == user_id:
            return

        if play_time < 3:
            low = 1
            high = 2
        else:
            low = 1 + play_time
            high = 2 + play_time

        rand_num = randint(low, high)
        if rand_num > 10:
            rand_num = 10

        if 0 < datetime.datetime.now().hour < 4:
            rand_num = 60 * 6
            await session.send('晚安')

        await bot.set_group_ban(group_id=id_num, user_id=user_id, duration=60 * rand_num)


@nonebot.on_command('转轮', only_to_me=False)
async def shuffle_gun(session: nonebot.CommandSession):
    seed(time_ns())
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish('这是群组游戏！')

    game.reset_gun(ctx['group_id'])
    await session.send('%s转动了弹夹！流向改变了！' % ctx['sender']['nickname'])


@nonebot.on_command('成语接龙', only_to_me=False)
async def jielong(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    random_idiom = GLOBAL_STORE.get_store(
        group_id=str(ctx['group_id']) if 'group_id' in ctx else "-1",
        function='solitaire',
        is_global=False,
        user_id=str(ctx['user_id'])
    )

    if not random_idiom:
        random_idiom = get_random_idiom()
        GLOBAL_STORE.set_store(
            function='solitaire',
            ref=random_idiom,
            group_id=str(ctx['group_id']) if 'group_id' in ctx else "-1",
            is_global=False,
            user_id=str(ctx['user_id'])
        )

    user_choice = session.get('user_choice', prompt=f'请接龙：{random_idiom}')
    if idiom.is_idiom_solitaire(random_idiom, str(user_choice).strip()):
        await session.finish('啧啧啧，什么嘛~还不错嘛~（好感度 +1）')
    else:
        await session.finish('你接球呢ww （好感度 -1）')


@nonebot.on_command('比大小', only_to_me=False)
async def the_poker_game(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = ctx['user_id']

    if 'group_id' in ctx:
        if admin_control.get_group_permission(ctx['group_id'], 'banned'):
            await session.send('已设置禁止该群的娱乐功能。如果确认这是错误的话，请联系bot制作者')
            return

    else:
        await session.finish('抱歉哦这是群组游戏。')

    if get_privilege(user_id, perm.OWNER):
        drawed_card, time_seed = poker.get_random_card(user_id, str(ctx['group_id']), rigged=10)
    else:
        drawed_card, time_seed = poker.get_random_card(user_id, str(ctx['group_id']))

    stat, response = poker.compare_two(str(ctx['group_id']))

    if not stat and response == -1:
        GLOBAL_STORE.set_store(
            'guess',
            drawed_card,
            ctx['group_id'] if 'group_id' in ctx else '-1',
            is_global=True
        )
        await session.send(f"玩家[CQ:at,qq={user_id}]拿到了加密过的卡：{encrypt_card(drawed_card, time_seed)}\n"
                           f"有来挑战一下的么？\n"
                           f"本次游戏随机种子：{time_seed}")

    else:
        player_one_card = GLOBAL_STORE.get_store(
            ctx['group_id'] if 'group_id' in ctx else '-1',
            'guess',
            is_global=True
        )
        if not stat and response == -2:
            await session.send(f"玩家[CQ:at,qq={user_id}]抓到了{drawed_card}。咳咳虽然斗争很激烈，但是平局啦！！")
        else:
            await session.send(f"玩家[CQ:at,qq={user_id}]抓到了{drawed_card}\n"
                               f"玩家1的加密卡为："
                               f"{player_one_card}。\n"
                               f"玩家[CQ:at,qq={response}]获胜！")

            setu_control.set_user_data(response, 'poker')

        poker.clear_result(str(ctx['group_id']))


def encrypt_card(card, time_seed):
    result = ''
    for idx, char in enumerate(card):
        order = (ord(char) ^ ord(time_seed[-idx - 6]))
        result += chr(order % 32 + 100)

    return result


def get_random_idiom() -> str:
    with open('data/util/idiom.csv', 'r', encoding='utf-8') as file:
        content = file.readlines()

    # Remove first line in csv file.
    content = [x.strip() for x in content][1:]
    random_idiom = choice(content).split(',')[6]
    while not idiom.is_idiom(random_idiom):
        random_idiom = choice(content).split(',')[6]

    return random_idiom
