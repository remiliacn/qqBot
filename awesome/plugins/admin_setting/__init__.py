from datetime import datetime
from math import *
from random import randint, seed
from re import findall, match, sub, compile
from time import time, time_ns

from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, Bot
from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.plugin.on import on_command

import config
from Services.util.common_util import is_float, check_if_number_user_id
from Services.util.ctx_utility import get_user_id, get_nickname
from awesome.Constants import user_permission as perm, group_permission
from awesome.Constants.function_key import QUESTION
from awesome.Constants.plugins_command_constants import NEEDS_THINGS_TO_ADD_PROMPT, NEEDS_QQ_NUMBER_PROMPT, \
    NEEDS_QUESTION_PROMPT
from awesome.Constants.user_permission import OWNER
from awesome.adminControl import get_privilege, user_control, setu_function_control
from util.helper_util import set_group_permission

_LAZY_RESPONSE = '可是我不想动哎.jpg'

free_speech_cmd = on_command('自由发言')


@free_speech_cmd.handle()
async def free_speech_switch(event: GroupMessageEvent, matcher: Matcher):
    group_id = event.group_id
    role = event.sender.role if event.sender.role else 'member'

    if group_id == -1 or (role == 'member' and not get_privilege(event.get_user_id(), OWNER)):
        return

    arg = event.current_arg_text
    set_group_permission(arg, group_id, group_permission.NLP)
    await matcher.finish('我好了')


change_name_cmd = on_command('改名')


@change_name_cmd.handle()
async def change_name(bot: Bot, event: GroupMessageEvent, matcher: Matcher):
    user_id = event.get_user_id()
    if not user_control.get_user_privilege(user_id, perm.ADMIN):
        return

    group_id = event.group_id

    card = event.current_arg_text.replace('&#91;', '[').replace('&#93;', ']')
    await bot.set_group_card(group_id=group_id, user_id=event.self_id, card=card)

    await matcher.finish('Done.')


add_monitor_word_cmd = on_command('添加监控词')


@add_monitor_word_cmd.handle()
async def add_monitor_word(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not (key_word := args.extract_plain_text()):
        await matcher.finish(NEEDS_THINGS_TO_ADD_PROMPT)

    if not get_privilege(get_user_id(event), perm.OWNER):
        await matcher.finish('您无权使用本命令')

    setu_function_control.set_new_xp(key_word)
    await matcher.finish('Done!')


add_blacklist_word_cmd = on_command('添加拉黑词')


@add_blacklist_word_cmd.handle()
async def add_blacklist_word(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not (key_word := args.extract_plain_text()):
        await matcher.finish(NEEDS_THINGS_TO_ADD_PROMPT)

    if not get_privilege(get_user_id(event), perm.OWNER):
        await matcher.finish('您无权使用本命令')

    key_words = key_word.split()

    if len(key_words) != 2:
        await matcher.finish('参数有误。应为！添加拉黑词 关键词 理智消耗倍数')

    try:
        setu_function_control.add_bad_word_dict(key_words[0], int(key_words[1]))
        await matcher.finish('Done!')
    except ValueError:
        await matcher.finish('第二输入非数字。')


add_whitelist_cmd = on_command('添加信任')


@add_whitelist_cmd.handle()
async def add_whitelist(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not get_privilege(get_user_id(event), perm.OWNER):
        await matcher.finish('您无权使用该功能')

    if not (user_id := args.extract_plain_text()):
        await matcher.finish(NEEDS_QQ_NUMBER_PROMPT)

    user_id = await check_if_number_user_id(event, user_id)

    user_control.set_user_privilege(user_id, perm.WHITELIST, True)

    await matcher.send('添加成功！')


delete_whitelist_cmd = on_command('移除信任', aliases={'删除信任', '解除信任'})


@delete_whitelist_cmd.handle()
async def delete_whitelist(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not get_privilege(get_user_id(event), perm.OWNER):
        await matcher.finish('您无权使用该功能')

    if not (user_id := args.extract_plain_text()):
        await matcher.finish(NEEDS_QQ_NUMBER_PROMPT)
    user_id = await check_if_number_user_id(event, user_id)

    user_control.set_user_privilege(user_id, perm.WHITELIST, False)
    await matcher.send('移除成功！')


add_admin_cmd = on_command('添加管理')


@add_admin_cmd.handle()
async def add_admin(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not get_privilege(get_user_id(event), perm.OWNER):
        await matcher.finish('您无权使用该功能')

    if not (user_id := args.extract_plain_text()):
        await matcher.finish(NEEDS_QQ_NUMBER_PROMPT)

    user_id = await check_if_number_user_id(event, user_id)

    user_control.set_user_privilege(user_id, 'ADMIN', True)
    user_control.set_user_privilege(user_id, 'WHITELIST', True)

    await matcher.send('添加完成')


delete_admin_cmd = on_command('删除管理')


@delete_admin_cmd.handle()
async def delete_admin(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not get_privilege(get_user_id(event), perm.OWNER):
        await matcher.finish('您无权使用该功能')

    if not (user_id := args.extract_plain_text()):
        await matcher.finish(NEEDS_QQ_NUMBER_PROMPT)

    user_id = await check_if_number_user_id(event, user_id)

    user_control.set_user_privilege(user_id, 'ADMIN', False)
    user_control.set_user_privilege(user_id, 'WHITELIST', False)
    await matcher.send('移除完成')


ask_question_cmd = on_command('问题')


@ask_question_cmd.handle()
async def send_answer(bot: Bot, event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    start_time = time()
    if not (question := args.extract_plain_text()):
        await matcher.finish(NEEDS_QUESTION_PROMPT)

    question = str(question).lower()
    if get_privilege(get_user_id(event), perm.BANNED):
        await matcher.finish()

    nickname = get_nickname(event)

    setu_function_control.set_user_data(get_user_id(event), QUESTION, user_nickname=nickname)

    if match('.*?你.*?(名字|叫什么|是谁|什么东西)', question):
        await matcher.finish(
            f'我叫{get_nickname(event)}\n'
            f'回答用时：{(time() - start_time):.2f}s'
        )

    # pre-processing
    response = _prefetch(question, get_user_id(event))
    if response:
        await matcher.send(
            response + f'\n回答用时：{(time() - start_time):.2f}s'
        )
    else:
        # math processing
        try:
            response = _math_fetch(question, get_user_id(event))

        except Exception as err:
            await bot.send_private_msg(
                user_id=config.SUPER_USER,
                message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                        f'可能的高危行为汇报：\n'
                        f'使用命令：！问题\n'
                        f'错误：{err}\n'
                        f'使用人：{event.get_user_id()}\n'
                        f'来自群：{event.group_id}\n'
            )
            await matcher.finish('计算时遇到了问题，本事件已上报bot主人进行分析。')

        if response:
            await bot.send_private_msg(
                user_id=config.SUPER_USER,
                message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                        f'风险控制\n'
                        f'使用命令：{str(event.raw_message)}\n'
                        f'我的回复：\n{response}\n'
                        f'使用人：{event.get_user_id()}\n'
                        f'来自群：{event.group_id}'
            )
            await matcher.finish(f'{response}\n回答用时：{(time() - start_time):.2f}s')

        else:
            logger.info("It is not a normal question.")
            ai_process = _simple_ai_process(question, event)
            if question != ai_process:
                await matcher.send(f'{ai_process}\n回答用时：{(time() - start_time):.2f}s')


def _simple_ai_process(question: str, event: GroupMessageEvent) -> str:
    if '你' in question:
        if '我' in question:
            me_word_index = [index for index, c in enumerate(question) if c == '我']
            response = question.replace('你', get_nickname(event))
            temp = list(response)
            for i in me_word_index:
                temp[i] = '你'

            response = ''.join(temp)
            return response

    elif match(r'.*?(我|吾|俺|私|本人)', question):
        response = sub(r'(我|吾|俺|私|本人)', get_nickname(event), question)
        return response

    syntax = compile(r'[么嘛吗马][？?]?')
    syntax2 = compile(r'.*?(.*?)不\1')

    response = sub(syntax, '', question) if '什么' not in question else question
    syntax_question = []

    if match(r'.*?是(.*?)还?是(.*?)[？?]', response):
        syntax_question = list(findall(r'.*?是(.*?)还?是(.*?)[？?]', response))[0]

    if len(syntax_question) > 1:
        if syntax_question[0] == syntax_question[1]:
            return '你这什么屑问法？'

        rand_num = randint(0, 100)
        if rand_num < 45:
            return syntax_question[0]
        elif rand_num < 90:
            return syntax_question[1]
        else:
            return f'又{syntax_question[0]}又{syntax_question[1]}'

    elif match(syntax2, response):
        if match(r'.*?主人', response):
            return '爬'
        rand_num = randint(0, 50)
        if rand_num < 20:
            return '答案肯定是肯定的啦'
        elif rand_num < 40:
            return '答案肯定是否定的啦'
        else:
            return '我也不晓得'

    if len(response) > 3:
        syntax_bot = compile('(bot|机器人|机械人|机屑人)')
        response = sub(syntax_bot, '人类', response)

    if '习近平' in sub(r'[\x00-\xff]+', '', question):
        return '年轻人我劝你好自为之'

    return response


def _math_fetch(question: str, user_id: str) -> str:
    if not get_privilege(user_id, perm.OWNER):
        question = question.replace('_', '')

    if len(question) > 30:
        return ''

    if match(
            r'.*?(sudo|ls|rm|curl|chmod|usermod|newgrp|vim|objdump|aux|lambda|del)',
            question
    ):
        return ''

    if 'factorial' in question:
        if len(question) > 20:
            return _LAZY_RESPONSE

        if '**' in question:
            return _LAZY_RESPONSE

        if 'pow' in question:
            return _LAZY_RESPONSE

        fact_number = findall(r'.*?factorial\((\d+)\)', question)
        if fact_number:
            if int(fact_number[0]) > 500:
                return _LAZY_RESPONSE

    if match(r'.*?<<', question):
        overflow_fetch = findall(r'.*?<<(\d+)', question)
        if overflow_fetch:
            if len(overflow_fetch) != 1:
                return _LAZY_RESPONSE
            if int(overflow_fetch[0]) > 100:
                return _LAZY_RESPONSE

    if match(r'.*?\*\*', question):
        if len(question) > 10:
            return _LAZY_RESPONSE

        overflow_fetch = findall(r'.*?\*\*(\d+)', question)
        if overflow_fetch:
            if len(overflow_fetch) > 2:
                return _LAZY_RESPONSE
            else:
                if int(overflow_fetch[0]) > 99:
                    return _LAZY_RESPONSE
                if len(overflow_fetch) == 2 and int(overflow_fetch[1]) > 2:
                    return _LAZY_RESPONSE

    if match(r'.*?pow\(\d+,\d+\)', question):
        if len(question) > 10:
            return _LAZY_RESPONSE

        if int(findall(r'.*?pow\(\d+,(\d+)\)', question)[0]) > 99:
            return _LAZY_RESPONSE

    if match(r'.*?\\u\d+', question) or match(r'.*?\\\w{3}', question):
        return '你说你马呢（'

    try:
        answer = eval(
            question,
            {"__builtins__": None},
            {
                'gcd': gcd, 'sqrt': sqrt, 'pow': pow,
                'floor': floor, 'factorial': factorial, 'sin': sin,
                'cos': cos, 'tan': tan, 'asin': asin, 'acos': acos,
                'pi': pi, 'atan': atan
            }
        )

    except Exception as err:
        logger.warning(f'This is not a math question.{str(err)}')
        return ''

    if is_float(answer):
        return f'运算结果是：{answer:.2f}\n我算的对吧~'
    else:
        return f'计算结果：{answer}\n请注意，本次计算已被汇报。'


def _prefetch(question: str, user_id: str) -> str:
    if question == user_control.last_question:
        repeat_count = user_control.get_user_repeat_question(user_id)
        if repeat_count == 6:
            user_control.set_user_privilege(str(user_id), perm.BANNED, True)
            return ''

        if repeat_count > 3:
            return ''

        user_control.set_user_repeat_question(user_id)
        return '你怎么又问一遍？'

    elif question in user_control.get_user_response_dict():
        user_control.last_question = question
        response = user_control.get_user_response(question)
        return response if response != '$' else ''

    if '屑bot' in question:
        return '你屑你🐴呢'

    if match('.*?(祈|衤|qi).*?(雨|yu)', question):
        return '不敢答，不敢答……溜了溜了w'

    if match('.*?(者|主人|creator|developer|owner)', sub(r'[\x00-\xff]+', '', question)):
        return ''

    if match('.*?你(几|多少?)(岁|大|年龄)', question):
        seed(time_ns())
        rand_num = randint(0, 101)
        if rand_num > 76:
            resp = '我永远的17岁。'
        elif rand_num > 45:
            resp = '我38岁，有两子'
        elif rand_num > 22:
            resp = '我今年1337岁'
        else:
            resp = '我今年114514岁了'

        return resp

    if match(r'.*?(爱不爱|喜不喜欢).*?妈妈', question):
        return '答案肯定是肯定的啦~'

    if '妈妈' in question or '🐴' in question:
        return '请问你有妈妈么？:)'

    return ''


ban_cmd = on_command('ban')


@ban_cmd.handle()
async def ban_someone(event: GroupMessageEvent, matcher: Matcher):
    if get_privilege(get_user_id(event), perm.ADMIN):
        user_id = await check_if_number_user_id(event, event.get('user_id', prompt='请输入要封禁的qq'))

        user_control.set_user_privilege(str(user_id), 'BANNED', True)
        await matcher.send('Done!!')

    else:
        await matcher.send('您无权进行该操作')
        return


unban_cmd = on_command('unban')


@unban_cmd.handle()
async def unban_someone(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if get_privilege(get_user_id(event), perm.ADMIN):
        user_id = await check_if_number_user_id(event, args.extract_plain_text())

        user_control.set_user_privilege(str(user_id), perm.BANNED, False)
        await matcher.send('Done!!')

    else:
        await matcher.send('您无权进行该操作')
