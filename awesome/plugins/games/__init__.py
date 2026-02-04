from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from random import randint, seed
from time import time_ns
from typing import Any, List, Optional

from nonebot import get_plugin_config, on_command, get_bot, logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment
from nonebot.exception import FinishedException
from nonebot.internal.matcher import Matcher
from nonebot.params import CommandArg

from Services import poker_game, ru_game, global_rate_limiter
from Services.util.common_util import is_self_group_admin
from Services.util.ctx_utility import get_group_id, get_user_id, get_nickname
from awesome.Constants import user_permission as perm, group_permission
from awesome.Constants.function_key import ROULETTE_GAME, POKER_GAME, DICE
from util.helper_util import construct_message_chain
from .game_config import GameConfig, DICE_RATE_LIMIT, ROULETTE_RATE_LIMIT
from ...adminControl import get_privilege, setu_function_control, group_control

config = get_plugin_config(GameConfig)


class Storer:
    def __init__(self):
        self.stored_result: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(dict))

    def set_store(self, function: str, ref: Any, group_id: str | int, is_global: bool, user_id: str = '-1') -> None:
        group_id = str(group_id)
        if is_global:
            self.stored_result[group_id][function] = ref
        else:
            if not isinstance(self.stored_result[group_id][function], dict):
                self.stored_result[group_id][function] = {}
            self.stored_result[group_id][function][user_id] = ref

    def get_store(self, group_id: str | int, function: str, is_global: bool, user_id: str = '-1',
                  clear_after_use: bool = True) -> Any:
        group_id = str(group_id)

        if group_id not in self.stored_result or function not in self.stored_result[group_id]:
            return None

        if is_global:
            result = self.stored_result[group_id][function]
            if clear_after_use:
                del self.stored_result[group_id][function]
            return result

        if not isinstance(self.stored_result[group_id][function], dict) or user_id not in self.stored_result[group_id][
            function]:
            return None

        result = self.stored_result[group_id][function][user_id]
        if clear_after_use:
            del self.stored_result[group_id][function][user_id]
        return result


GLOBAL_STORE = Storer()


@dataclass
class DiceResult:
    throw_times: int
    result_sum: int
    max_val: int
    result_list: list[int]


class CommandType(Enum):
    MULTIPLE_DICE = auto()
    EXPRESSION = auto()
    BINARY_DECISION = auto()
    NORMAL = auto()


@dataclass
class ParsedDiceCommand:
    command_type: CommandType
    content: str
    tokens: list[str]


class DiceParser:
    @staticmethod
    def parse(raw_message: str) -> ParsedDiceCommand:
        tokens = [x.strip() for x in raw_message.replace('，', ',').split(',') if x.strip()]
        content = raw_message.strip()

        if 'OR' in content.upper():
            return ParsedDiceCommand(CommandType.BINARY_DECISION, content, tokens)

        if DiceParser._is_multiple_dice(tokens):
            return ParsedDiceCommand(CommandType.MULTIPLE_DICE, content, tokens)

        if DiceParser._is_expression(content):
            return ParsedDiceCommand(CommandType.EXPRESSION, content, tokens)

        return ParsedDiceCommand(CommandType.NORMAL, content, tokens)

    @staticmethod
    def is_dice_notation(text: str) -> bool:
        if not text or 'D' not in text.upper():
            return False

        parts = text.upper().split('D')
        if len(parts) != 2:
            return False

        try:
            count = int(parts[0])
            sides = int(parts[1])
            return count > 0 and sides > 0
        except (ValueError, IndexError):
            return False

    @staticmethod
    def _is_multiple_dice(tokens: list[str]) -> bool:
        if len(tokens) <= 1:
            return False
        return all(DiceParser.is_dice_notation(token) for token in tokens)

    @staticmethod
    def _is_expression(text: str) -> bool:
        if not text:
            return False

        has_dice = 'D' in text.upper()
        has_operator = any(op in text for op in ['+', '-', '*', '/'])

        return has_dice and has_operator

    @staticmethod
    def extract_dice_notations(text: str) -> list[str]:
        result = []
        i = 0
        text_upper = text.upper()

        while i < len(text):
            if text_upper[i].isdigit():
                start = i
                while i < len(text) and text[i].isdigit():
                    i += 1

                if i < len(text) and text_upper[i] == 'D':
                    i += 1
                    dice_start = start

                    while i < len(text) and text[i].isdigit():
                        i += 1

                    dice_notation = text[dice_start:i]
                    if DiceParser.is_dice_notation(dice_notation):
                        result.append(dice_notation)
                    continue
            i += 1

        return result


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
    text = text.strip().upper()

    if 'D' not in text:
        raise ValueError(f"Invalid dice format: {text}")

    parts = text.split('D')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid dice format: {text}")

    try:
        throw_times = int(parts[0])
        max_val = int(parts[1])
    except ValueError:
        raise ValueError(f"Invalid dice format: {text}")

    if throw_times <= 0:
        raise ValueError(f"Throw times must be positive: {throw_times}")
    if max_val <= 0:
        raise ValueError(f"Dice sides must be positive: {max_val}")

    throw_times = min(throw_times, 30)
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


async def _get_binary_decision_result(text: str) -> str:
    text_upper = text.upper()
    or_index = text_upper.find('OR')

    if or_index == -1:
        return '必须包含 OR 关键字'

    first_part = text[:or_index].strip()
    second_part = text[or_index + 2:].strip()

    if not first_part or not second_part:
        return '必须有两个选项。'

    first_choice, first_display = await _parse_choice(first_part)
    if first_choice is None:
        return '第一个选项格式错误'

    second_choice, second_display = await _parse_choice(second_part)
    if second_choice is None:
        return '第二个选项格式错误'

    if first_choice >= second_choice:
        return f'第一个结果 {first_display} >= 第二个结果 {second_display}，取第一个结果：{first_choice}'

    return f'第一个结果 {first_display} < 第二个结果 {second_display}，取第二个结果：{second_choice}'


async def _parse_choice(text: str) -> tuple[Optional[int], Optional[str]]:
    text = text.strip()

    if text.isdigit():
        value = int(text)
        return value, str(value)

    if DiceParser.is_dice_notation(text):
        try:
            result = await _get_dice_result(text)
            return result.result_sum, f"{text.upper()}({result.result_sum})"
        except ValueError:
            return None, None

    return None, None


async def _multiple_row_result(text_args: list) -> str:
    dice_result_list = [(await _get_dice_result(x)) for x in text_args]
    dice_result_text = [(await _get_dice_result_plain_text(x)) for x in dice_result_list]
    return '\n'.join(dice_result_text)


async def _evaluate_dice_expression(text: str) -> str:
    all_dice_notations = DiceParser.extract_dice_notations(text)

    if not all_dice_notations:
        return '未找到有效的骰子表达式'

    evaluation_list_result = []
    for dice_expr in all_dice_notations:
        try:
            result = await _get_dice_result(dice_expr)
            evaluation_list_result.append(result)
        except ValueError as e:
            logger.error(f'Dice evaluation error: {e}')
            return f'骰子表达式 {dice_expr} 格式错误'

    expression_to_eval = text
    for idx, dice_text in enumerate(all_dice_notations):
        expression_to_eval = expression_to_eval.replace(dice_text, str(evaluation_list_result[idx].result_sum), 1)

    allowed_chars = set('0123456789+-*/(). ')
    if not all(c in allowed_chars for c in expression_to_eval):
        return '表达式包含非法字符'

    try:
        result = eval(expression_to_eval)
    except ZeroDivisionError:
        return '除数不能为0'
    except Exception as e:
        logger.error(f'Expression evaluation error: {e}')
        return '表达式计算错误'

    dice_result_plain_text_list = "\n".join([await _get_dice_result_plain_text(x) for x in evaluation_list_result])
    return f'随机结果如下：\n{dice_result_plain_text_list}\n最后计算结果为：{result}'


dice_roll_cmd = on_command('骰娘')


@dice_roll_cmd.handle()
@global_rate_limiter.rate_limit(func_name=DICE, config=DICE_RATE_LIMIT, show_prompt=False)
async def pao_tuan_shai_zi(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    raw_message = args.extract_plain_text().strip()

    if not raw_message:
        await matcher.finish('请输入骰子指令，例如：1D100, 2D100, 1D100+1D100, 1D100 OR 1D100')

    try:
        message_id = event.message_id
        parsed = DiceParser.parse(raw_message)

        match parsed.command_type:
            case CommandType.MULTIPLE_DICE:
                await matcher.finish(await _multiple_row_result(parsed.tokens))

            case CommandType.EXPRESSION:
                await matcher.finish(await _evaluate_dice_expression(parsed.content))

            case CommandType.BINARY_DECISION:
                await matcher.finish(
                    construct_message_chain(
                        MessageSegment.reply(message_id),
                        await _get_binary_decision_result(parsed.content)))

            case CommandType.NORMAL:
                await matcher.finish(
                    construct_message_chain(
                        MessageSegment.reply(message_id),
                        await _get_normal_decision_result(parsed.tokens)))

    except FinishedException:
        pass
    except ValueError as e:
        logger.error(f'Dice value error: {e}')
        await matcher.finish(f'参数错误：{e}')
    except Exception as err:
        logger.error(f'Dice result error: {err.__class__.__name__}: {err}')
        await matcher.finish('使用方式有误。')


russia_roulette_cmd = on_command('轮盘赌')


@russia_roulette_cmd.handle()
@global_rate_limiter.rate_limit(func_name=ROULETTE_GAME, config=ROULETTE_RATE_LIMIT, show_prompt=False)
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

        if await is_self_group_admin(get_group_id(event)):
            await bot.set_group_ban(group_id=id_num, user_id=user_id, duration=rand_num)


shuffle_gun_cmd = on_command('转轮')


@shuffle_gun_cmd.handle()
@global_rate_limiter.rate_limit(func_name=ROULETTE_GAME, config=ROULETTE_RATE_LIMIT, show_prompt=False)
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
