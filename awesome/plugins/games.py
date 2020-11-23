import asyncio
from random import randint, seed, choice
from time import time_ns

import nonebot

from Shadiao import poker_game, ru_game
from awesome.adminControl import permission as perm
from awesome.plugins.admin_setting import get_privilege
from awesome.plugins.shadiao import admin_control, sanity_meter


class Storer:
    def __init__(self):
        self.stored_result = {}

    def set_store(self, ref, group_id):
        self.stored_result[group_id] = ref

    def getStore(self, group_id):
        temp = self.stored_result[group_id]
        self.stored_result[group_id] = ''
        return temp

class horseRacing:
    def __init__(self, userGuess: str):
        self.userGuess = userGuess
        self.winningGoal = 7
        self.actualWinner = -1
        self.addingDict = {
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

        self.subtractingDict = {
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

        self.horseList = [0, 0, 0, 0, 0, 0]
        self.responseList = []

    def ifPlay(self):
        try:
            temp = int(self.userGuess)
            if temp > len(self.horseList):
                return False

        except ValueError:
            return False

        return True

    def ifWin(self):
        for idx, elements in enumerate(self.horseList):
            if elements >= self.winningGoal:
                self.actualWinner = str(idx + 1)
                return True

        return False

    def whoWin(self):
        return self.actualWinner

    def getPlayResult(self):
        self.responseList.clear()
        resp = ""
        i = 0
        for idx, elements in enumerate(self.horseList):
            if randint(0, 5) >= 2:
                thisChoice = choice(list(self.addingDict))
                self.horseList[idx] += self.addingDict[thisChoice]
                self.responseList.append(str(i + 1) + "号马, " + thisChoice)

            else:
                thisChoice = choice(list(self.subtractingDict))
                self.horseList[idx] += self.subtractingDict[thisChoice]
                self.responseList.append(str(i + 1) + "号马, " + thisChoice)

            i += 1

        for elements in self.responseList:
            resp += elements + "\n"

        return resp

    def playerWin(self):
        if self.actualWinner == self.userGuess:
            return True

        return False

poker = poker_game.Pokergame()
GLOBAL_STORE = Storer()
game = ru_game.Russianroulette()


@nonebot.on_command('赛马', only_to_me=False)
async def horseRace(session: nonebot.CommandSession):
    winner = session.get('winner', prompt='请输入一个胜方编号进行猜测（1-6）')
    race = horseRacing(winner)
    ctx = session.ctx.copy()
    user_id = ctx['user_id']

    if race.ifPlay():
        while not race.ifWin():
            await session.send(race.getPlayResult())
            await asyncio.sleep(2)

        if race.playerWin():
            await session.send("恭喜你猜赢啦！")
            if 'group_id' in ctx:
                sanity_meter.set_user_data(user_id, 'horse_race')

        else:
            await session.send(f"啊哦~猜输了呢！其实是{race.whoWin()}号赢了哦")


@horseRace.args_parser
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
async def russianRoulette(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    id_num = ctx['group_id'] if 'group_id' in ctx else ctx['user_id']
    user_id = ctx['user_id']

    if 'group_id' in ctx:
        if admin_control.get_data(ctx['group_id'], 'banned'):
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
                               '本应中枪几率为：%.2f' % (1 / (7 - death)))
            return

        await session.send(f'[CQ:reply,id={message_id}]boom！你死了。这是第%d枪，理论几率为：%.2f' % (death, (1 / (7 - death))))
        sanity_meter.set_user_data(user_id, 'roulette')

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
            
        await bot.set_group_ban(group_id=id_num, user_id=user_id, duration=60 * rand_num)


@nonebot.on_command('转轮', only_to_me=False)
async def shuffle_gun(session: nonebot.CommandSession):
    seed(time_ns())
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish('这是群组游戏！')

    game.reset_gun(ctx['group_id'])
    await session.send('%s转动了弹夹！流向改变了！' % ctx['sender']['nickname'])


@nonebot.on_command('比大小', only_to_me=False)
async def the_poker_game(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = ctx['user_id']

    if 'group_id' in ctx:
        if admin_control.get_data(ctx['group_id'], 'banned'):
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
        GLOBAL_STORE.set_store(drawed_card, ctx['group_id'])
        await session.send(f"玩家[CQ:at,qq={user_id}]拿到了加密过的卡：{encrypt_card(drawed_card, time_seed)}\n"
                           f"有来挑战一下的么？\n"
                           f"本次游戏随机种子：{time_seed}")

    else:
        if not stat and response == -2:
            await session.send(f"玩家[CQ:at,qq={user_id}]抓到了{drawed_card}。咳咳虽然斗争很激烈，但是平局啦！！")
        else:
            await session.send(f"玩家[CQ:at,qq={user_id}]抓到了{drawed_card}\n"
                               f"玩家1的加密卡为：{GLOBAL_STORE.getStore(ctx['group_id'])}。\n"
                               f"玩家[CQ:at,qq={response}]获胜！")

            sanity_meter.set_user_data(response, 'poker')

        poker.clear_result(str(ctx['group_id']))


def encrypt_card(card, time_seed):
    result = ''
    for idx, char in enumerate(card):
        order = (ord(char) ^ ord(time_seed[-idx - 6]))
        result += chr(order % 32 + 100)

    return result
