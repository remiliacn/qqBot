from datetime import datetime
from random import randint, seed
from re import split, findall, fullmatch
from time import time_ns
from typing import List

from nonebot import get_plugin_config, on_command, get_bot, logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment
from nonebot.exception import FinishedException
from nonebot.internal.matcher import Matcher
from nonebot.params import CommandArg

from Services import poker_game, ru_game
from Services.util.ctx_utility import get_group_id, get_user_id, get_nickname
from awesome.Constants import user_permission as perm, group_permission
from awesome.Constants.function_key import ROULETTE_GAME, POKER_GAME
from util.helper_util import construct_message_chain
from .gameconfig import GameConfig
from ...adminControl import get_privilege, setu_function_control, group_control

config = get_plugin_config(GameConfig)


class Storer:
    def __init__(self):
        self.stored_result = {}

    def set_store(self, function, ref, group_id: [str, int], is_global: bool, user_id='-1'):
        group_id = str(group_id)
        if group_id not in self.stored_result:
            self.stored_result[group_id] = {}

        if function not in self.stored_result[group_id]:
            self.stored_result[group_id][function] = {}

        if is_global:
            self.stored_result[group_id][function] = ref
        else:
            self.stored_result[group_id][function][user_id] = ref

    def get_store(self, group_id, function, is_global: bool, user_id='-1', clear_after_use=True):
        if group_id not in self.stored_result:
            self.stored_result[group_id] = {}
            return ''

        if function not in self.stored_result[group_id]:
            self.stored_result[group_id][function] = ''
            return ''

        if is_global:
            temp = self.stored_result[group_id][function]
            if clear_after_use:
                self.stored_result[group_id][function] = ''
            return temp
        else:
            if user_id not in self.stored_result[group_id][function]:
                return ''

            info = self.stored_result[group_id][function][user_id]
            if clear_after_use:
                self.stored_result[group_id][function][user_id] = ''
            return info


GLOBAL_STORE = Storer()


class DiceResult:
    def __init__(self, throw_times: int, result_sum: int, max_val: int, result_list: list):
        self.throw_times = throw_times
        self.result_sum = result_sum
        self.max_val = max_val
        self.result_list = result_list


poker = poker_game.Pokergame()
ru_roulette_game = ru_game.Russianroulette(config.BULLET_IN_GUN)


async def _dice_expr_evaluation(expression: str, result_sum: int, evaluation_target: float) -> bool:
    evaluation_result = False
    match expression:
        case '大于' | '>':
            evaluation_result = result_sum > evaluation_target
        case '小于' | '<':
            evaluation_result = result_sum < evaluation_target
        case '大于等于' | '>=':
            evaluation_result = result_sum >= evaluation_target
        case '小于等于' | '<=':
            evaluation_result = result_sum <= evaluation_target
        case '等于' | '=' | '==':
            evaluation_result = result_sum == evaluation_target
        case '不等于' | '≠' | '!=':
            evaluation_result = result_sum != evaluation_target

    return evaluation_result


async def _get_dice_result(text: str) -> DiceResult:
    args = split(r'[dD]', text)
    throw_times = int(args[0])
    if throw_times > 30:
        throw_times = 30

    max_val = int(args[1])
    result_list = [randint(1, max_val) for _ in range(throw_times)]
    result_sum = sum(result_list)

    return DiceResult(throw_times, result_sum, max_val, result_list)


async def _get_dice_result_plain_text(dice_result: DiceResult) -> str:
    sum_string = f'\n其掷骰结果总和为：{dice_result.result_sum}' if dice_result.throw_times > 1 else ""
    result_string = f'{dice_result.throw_times}次掷{dice_result.max_val}面骰的结果为：' \
                    f'{", ".join([str(x) for x in dice_result.result_list])}' + \
                    sum_string

    return result_string


async def _get_normal_decision_result(text_args: list):
    dice_result = await _get_dice_result(text_args[0])

    evaluation_result = None
    if len(text_args) == 3 and text_args[2].isdigit():
        evaluation_target = float(text_args[2])
        expression = text_args[1]
        evaluation_result = await _dice_expr_evaluation(expression, dice_result.result_sum, evaluation_target)

    if evaluation_result is None:
        return await _get_dice_result_plain_text(dice_result)

    return await _get_dice_result_plain_text(dice_result) + '，' + ('判定成功' if evaluation_result else '判定失败')


async def _get_binary_decision_result(text_args: List[str]):
    data_args = text_args[0].split('OR')
    if len(data_args) != 2:
        return '必须有两个选项。'

    first_data_choice = data_args[0].strip()
    if first_data_choice.isdigit():
        first_choice = int(first_data_choice)
    else:
        first_choice_await = await _get_dice_result(first_data_choice)
        first_choice = first_choice_await.result_sum

    second_data_choice = data_args[1].strip()

    if second_data_choice.isdigit():
        second_choice = int(second_data_choice)
    else:
        second_choice_await = await _get_dice_result(second_data_choice)
        second_choice = second_choice_await.result_sum

    if await _dice_expr_evaluation('>=', first_choice, int(data_args[1])):
        return f'1d100 >= {data_args[1]}成功，取第一个结果：{first_choice}'

    return f'1d100 >= {data_args[1]}失败（Roll点结果为：{first_choice}），取第二个结果：{second_choice}'


async def _multiple_row_result(text_args: list) -> str:
    dice_result_list = [(await _get_dice_result(x)) for x in text_args]
    dice_result_text = [(await _get_dice_result_plain_text(x)) for x in dice_result_list]
    return '\n'.join(dice_result_text)


async def _evaluate_dice_expression(text: str):
    all_dice_role_evaluation = findall(r'\d+[dD]\d+', text)
    evaluation_list_result = [(await _get_dice_result(x)) for x in all_dice_role_evaluation]
    for idx, dice_text in enumerate(all_dice_role_evaluation):
        text = text.replace(dice_text, str(evaluation_list_result[idx].result_sum), 1)

    try:
        result = eval(text)
    except ZeroDivisionError:
        return '除数不能为0'

    dice_result_plain_text_list = "\n".join([(await _get_dice_result_plain_text(x)) for x in evaluation_list_result])
    return f'随机结果如下：\n' \
           f'{dice_result_plain_text_list}\n' \
           f'最后计算结果为：{result}'


dice_roll_cmd = on_command('骰娘')


@dice_roll_cmd.handle()
async def pao_tuan_shai_zi(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    raw_message = args.extract_plain_text().strip()
    text_args = split(r'[,，\s]+', raw_message)
    text_args = [x.strip() for x in text_args if x]

    normal_decision = True
    if all(fullmatch(r'^\d+[dD]\d+$', x) for x in text_args):
        await matcher.finish(await _multiple_row_result(text_args))

    if fullmatch(r'^\d+[dD]\d+([+\-*/]\d+([dD]\d+)?)+$', text_args[0]):
        await matcher.finish(await _evaluate_dice_expression(text_args[0]))

    if fullmatch(r'^\d+([dD]\d+)?\s*OR\s*\d+([dD]\d+)?$', raw_message):
        normal_decision = False

    message_id = event.message_id

    try:
        if normal_decision:
            await matcher.finish(
                construct_message_chain(MessageSegment.reply(message_id), await _get_normal_decision_result(text_args)))
        else:
            await matcher.finish(
                construct_message_chain(MessageSegment.reply(message_id),
                                        await _get_binary_decision_result([raw_message])))
    except FinishedException:
        pass
    except Exception as err:
        logger.error(f'Dice result error: {err.__class__.__name__}: {err}')
        await matcher.finish('使用方式有误。')


russia_roulette_cmd = on_command('轮盘赌')


@russia_roulette_cmd.handle()
async def russian_roulette(event: GroupMessageEvent, matcher: Matcher):
    id_num = event.group_id
    user_id = event.get_user_id()

    if id_num not in ru_roulette_game.game_dict:
        ru_roulette_game.set_up_dict_by_group(id_num)

    if user_id not in ru_roulette_game.game_dict[id_num]["playerDict"]:
        ru_roulette_game.add_player_in(group_id=id_num, user_id=user_id)
    else:
        ru_roulette_game.add_player_play_time(group_id=id_num, user_id=user_id)

    message_id = event.message_id
    nickname = get_nickname(event)

    if not ru_roulette_game.get_result(id_num):
        await matcher.finish(construct_message_chain(MessageSegment.reply(message_id), f'好像什么也没发生'))
    else:
        death = ru_roulette_game.get_death(id_num)
        death_dodge = randint(0, 100)
        if get_privilege(user_id, perm.OWNER) or death_dodge < 3:
            await matcher.finish(construct_message_chain(
                MessageSegment.reply(message_id),
                f'sv_cheats 1 -> 成功触发免死\n'
                f'本应中枪几率为：%{1 / (ru_roulette_game.get_bullet_in_gun() + 1 - death) * 100:.2f}'))

        setu_function_control.set_user_data(user_id, ROULETTE_GAME, nickname)
        await matcher.send(
            construct_message_chain(
                MessageSegment.reply(message_id),
                f'boom！你死了。这是第{death}枪，',
                f'理论几率为：{(1 / (ru_roulette_game.get_bullet_in_gun() + 1 - death) * 100):.2f}%'))

        bot = get_bot()
        if id_num == user_id:
            return

        rand_num = 60 * 2
        if 0 < datetime.now().hour < 4 and config.ENABLE_GOOD_NIGHT_MODE:
            rand_num = 60 * 60 * 6
            await matcher.send('晚安')

        await bot.set_group_ban(group_id=id_num, user_id=user_id, duration=rand_num)


shuffle_gun_cmd = on_command('转轮')


@shuffle_gun_cmd.handle()
async def shuffle_gun(event: GroupMessageEvent, matcher: Matcher):
    seed(time_ns())
    ru_roulette_game.reset_gun(get_group_id(event))
    await matcher.send(f'{get_nickname(event)}转动了弹夹！流向改变了！')


set_bullet_cmd = on_command('设置子弹')


@set_bullet_cmd.handle()
async def modify_gun_rounds(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    user_id = get_user_id(event)
    arg = args.extract_plain_text()
    if not arg:
        await matcher.finish('?')

    if not arg.isdigit() or int(arg) <= 0:
        await matcher.finish('必须是正整数')

    bullet = int(arg)

    if not get_privilege(user_id, perm.ADMIN) and (bullet <= 5 or bullet > 10):
        await matcher.finish('非主人只能设置5-10的区间哦')

    ru_roulette_game.modify_bullets_in_gun(bullet)
    await matcher.finish('Done!')


poker_game_cmd = on_command('比大小')


@poker_game_cmd.handle()
async def the_poker_game(event: GroupMessageEvent, matcher: Matcher):
    user_id = get_user_id(event)

    if group_control.get_group_permission(get_group_id(event), group_permission.BANNED):
        await matcher.finish('已设置禁止该群的娱乐功能。如果确认这是错误的话，请联系bot制作者')

    nickname = get_nickname(event)

    if get_privilege(user_id, perm.OWNER):
        drawed_card, time_seed = poker.get_random_card(user_id, str(event.group_id), rigged=10)
    else:
        drawed_card, time_seed = poker.get_random_card(user_id, str(event.group_id))

    stat, response = poker.compare_two(str(event.group_id))
    if not stat and response == -1:
        GLOBAL_STORE.set_store(
            'guess',
            drawed_card,
            event.group_id,
            is_global=True
        )
        await matcher.send(Message([MessageSegment.text('玩家'), MessageSegment.at(user_id),
                                    f"拿到了加密过的卡：{_encrypt_card(drawed_card, time_seed)}\n"
                                    f"有来挑战一下的么？\n"
                                    f"本次游戏随机种子：{time_seed}"]))

    else:
        player_one_card = GLOBAL_STORE.get_store(
            get_group_id(event),
            'guess',
            is_global=True
        )
        if not stat and response == -2:
            await matcher.send(construct_message_chain("玩家", MessageSegment.at(user_id),
                                                       f"抓到了{drawed_card}。咳咳虽然斗争很激烈，但是平局啦！！"))
        else:
            await matcher.send(construct_message_chain("玩家", MessageSegment.at(user_id),
                                                       f"抓到了{drawed_card}\n"
                                                       f"玩家1的加密卡为："
                                                       f"{player_one_card}。\n"
                                                       f"玩家", MessageSegment.at(response), "获胜！"))

            setu_function_control.set_user_data(response, POKER_GAME, nickname)

        poker.clear_result(str(get_group_id(event)))


def _encrypt_card(card: List[str], time_seed: str) -> str:
    result = ''
    for idx, char in enumerate(card):
        order = (ord(char) ^ ord(time_seed[-idx - 6]))
        result += chr(order % 32 + 100)

    return result
