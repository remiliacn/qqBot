import json
import random
import re
import time
from math import *

import nonebot
import requests
import os

import config
from awesome.adminControl import group_admin
from awesome.adminControl import permission as perm
from awesome.plugins.shadiao import sanity_meter
from awesome.plugins.util.helper_util import get_downloaded_image_path
from qq_bot_core import alarm_api
from qq_bot_core import user_control_module

admin_control = group_admin.Shadiaoadmin()

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)


@nonebot.on_command('警报解除', only_to_me=False)
async def lower_alarm(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish()

    alarm_api.clear_alarm()
    await session.send('Done!')


@nonebot.on_command('添加监控词', only_to_me=False)
async def add_monitor_word(session: nonebot.CommandSession):
    keyWord = session.get('keyWord', prompt='要加什么进来呢？')
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish('您无权使用本命令')

    sanity_meter.set_new_xp(keyWord)
    await session.finish('Done!')


@nonebot.on_command('添加拉黑词', only_to_me=False)
async def add_blacklist_word(session: nonebot.CommandSession):
    key_word = session.get('key_word', prompt='要加什么进来呢？')
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish('您无权使用本命令')

    keyWords = key_word.split()

    if len(keyWords) != 2:
        await session.finish('参数有误。应为！添加拉黑词 关键词 理智消耗倍数')

    try:
        sanity_meter.add_bad_word_dict(keyWords[0], int(keyWords[1]))
        await session.finish('Done!')
    except ValueError:
        await session.finish('第二输入非数字。')


@nonebot.on_command('添加信任', only_to_me=False)
async def add_whitelist(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    bot = nonebot.get_bot()
    if not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish('您无权使用该功能')

    user_id = session.get('user_id', prompt='请输入要添加的qq号')
    try:
        user_id = int(user_id)
    except ValueError:
        await session.send('主人啊，这是数字么？')
        return

    user_control_module.set_user_privilege(user_id, perm.WHITELIST, True)
    await bot.send_private_msg(
        user_id=user_id,
        message='您已被机器人的主人添加信任'
    )
    await session.send('添加成功！')


@nonebot.on_command('移除信任', aliases={'删除信任', '解除信任'}, only_to_me=False)
async def delete_whitelist(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish('您无权使用该功能')

    user_id = session.get('user_id', prompt='请输入要添加的qq号')
    try:
        user_id = int(user_id)
    except ValueError:
        await session.finish('主人啊，这是数字么？')

    user_control_module.set_user_privilege(user_id, perm.WHITELIST, False)
    await session.send('移除成功！')


@nonebot.on_command('添加管理', only_to_me=False)
async def add_admin(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    bot = nonebot.get_bot()
    if not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish('您无权使用该功能')

    user_id = session.get('user_id', prompt='请输入要添加的qq号')
    try:
        user_id = int(user_id)
    except ValueError:
        await session.send('主人啊，这是数字么？')
        return

    user_control_module.set_user_privilege(user_id, 'ADMIN', True)
    user_control_module.set_user_privilege(user_id, 'WHITELIST', True)
    await bot.send_private_msg(
        user_id=user_id,
        message='您已被机器人的主人给予机器人管理权限'
    )
    await session.send('添加完成')


@nonebot.on_command('删除管理', only_to_me=False)
async def delete_admin(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish('您无权使用该功能')

    user_id = session.get('user_id', prompt='请输入要添加的qq号')
    try:
        user_id = int(user_id)
    except ValueError:
        await session.send('主人啊，这是数字么？')
        return

    user_control_module.set_user_privilege(user_id, 'ADMIN', False)
    user_control_module.set_user_privilege(user_id, 'WHITELIST', False)
    await session.send('移除完成')


@nonebot.on_command('我懂了', only_to_me=False)
async def add_ai_real_response(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    question = session.get('question', prompt='请输入回答的问题')
    question = str(question).replace('\n', '')

    if not get_privilege(ctx['user_id'], perm.WHITELIST):
        await session.finish()

    if question in user_control_module.get_user_dict():
        user_control_module.delete_response(question)

    answer = session.get('answer', prompt='已删除该回答的原始回答，请加入新的回答')
    answer = str(answer).replace('\n', ' ')

    if re.match(r'\$', answer) and not get_privilege(ctx['user_id'], perm.OWNER):
        await session.finish('您无权封印此语料')

    has_image = re.findall(r'.*?file=(.*?\.image)', answer)
    bot = nonebot.get_bot()
    if has_image:
        response = await bot.get_image(file=has_image[0])
        answer = re.sub(
            r'.*?file=(.*?\.image)',
            get_downloaded_image_path(
                response,
                f'{os.getcwd()}/data/bot/response/'
            ),
            answer
        )

    answer_dict = {
        'answer': answer,
        'from_group': ctx['group_id'] if 'group_id' in ctx else -1,
        'from_user': ctx['user_id'],
        'user_nickname': ctx['sender']['nickname'],
        'restriction': True
    }

    user_control_module.add_response(question, answer_dict)
    await session.send('回答已添加！')


@nonebot.on_command('问题', only_to_me=False)
async def sendAnswer(session: nonebot.CommandSession):
    start_time = time.time()
    question = session.get('question', prompt='啊？你要问我什么？')
    question = str(question).lower()
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.BANNED):
        await session.finish()

    sanity_meter.set_user_data(ctx['user_id'], 'question')

    if re.match('.*?你.*?(名字|叫什么|是谁|什么东西)', question):
        await session.finish(
            f'我叫{ctx["sender"]["nickname"]}\n'
            f'回答用时：{(time.time() - start_time):.2f}s'
        )

    # pre-processing
    response = _prefetch(question, ctx['user_id'])
    if response:
        await session.send(
            response + '\n'
                       f'回答用时：{(time.time() - start_time):.2f}s'
        )
    else:
        # math processing
        response = _math_fetch(question, ctx['user_id'])
        if response:
            await session.send(
                response + '\n'
                           f'回答用时：{(time.time() - start_time):.2f}s'
            )

        else:
            nonebot.logger.info(msg="It is not a normal question.")
            ai_process = _simple_ai_process(question)
            if question == ai_process:
                response = _request_api_response(question)
                await session.send(
                    response +
                    f'\n'
                    f'回答用时：{(time.time() - start_time):.2f}s'
                )

            else:
                await session.send(
                    ai_process +
                    f'\n'
                    f'回答用时：{(time.time() - start_time):.2f}s'
                )


@sendAnswer.args_parser
async def _send_answer(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['question'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('啊？你要问我什么？')

    session.state[session.current_key] = stripped_arg


def _simple_ai_process(question: str) -> str:
    syntax = re.compile(r'[么嘛吗马][？?]')
    syntax2 = re.compile(r'.*?(.*?)不\1')

    response = re.sub(syntax, '', question)
    syntax_question = []

    if re.match(r'.*?是(.*?)还?是(.*?)[？?]', response):
        syntax_question = list(re.findall(r'.*?是(.*?)还?是(.*?)[？?]', response))[0]

    if len(syntax_question) > 1:
        rand_num = random.randint(0, 50)
        if syntax_question[0] == syntax_question[1]:
            return '你这什么屑问法？'

        if rand_num >= 25:
            return f'{syntax_question[0]}'
        else:
            return f'{syntax_question[1]}'

    elif re.match(syntax2, response):
        rand_num = random.randint(0, 50)
        if rand_num < 20:
            return '答案肯定是肯定的啦'
        elif rand_num < 40:
            return '答案肯定是否定的啦'
        else:
            return '我也不晓得'

    if len(response) > 3:
        syntax_bot = re.compile('(bot|机器人|机械人|机屑人)')
        response = re.sub(syntax_bot, '人类', response)

    return response


def _math_fetch(question: str, user_id: int) -> str:
    if re.match(r'.*?name__', question) and not get_privilege(user_id, perm.OWNER):
        return '检测到危险指令。拒绝执行'

    if re.match(r'.*?(sudo|ls|rm|curl|chmod|usermod|newgrp|vim|objdump|aux|lambda)', question):
        return ''

    if re.match(r'.*?\*\*', question):
        if len(question) > 10:
            return '检测到可能的DDoS攻击。计算停止'

        if int(re.findall(r'.*?\*\*(\d+)', question)[0]) > 99:
            return '检测到可能的DDoS攻击。计算停止'

    if re.match(r'.*?pow\(\d+,\d+\)', question):
        if len(question) > 10:
            return '检测到可能的DDoS攻击。计算停止'

        if int(re.findall(r'.*?pow\(\d+,(\d+)\)', question)[0]) > 99:
            return '检测到可能的DDoS攻击。计算停止'

    if re.match(r'.*?\\u\d+', question) or re.match(r'.*?\\\w{3}', question):
        return '你说你马呢（'

    try:
        answer = eval(
            question, {"__builtins__": None},
            {'gcd': gcd, 'sqrt': sqrt, 'pow': pow, 'floor': floor, 'factorial': factorial, 'sin': sin,
             'cos': cos,
             'tan': tan, 'asin': asin, 'acos': acos, 'pi': pi, 'atan': atan
             }
        )

    except Exception as err:
        nonebot.logger.warning(f'This is not a math question.{str(err)}')
        return ''

    return f'运算结果是：{f"{answer:.2f}" if _is_float(answer) else answer}' + '\n我算的对吧~'


def _is_float(content: str) -> bool:
    try:
        float(content)
        return True

    except ValueError:
        return False


def _prefetch(question: str, user_id: int) -> str:
    if question == user_control_module.last_question:
        repeat_count = user_control_module.get_user_repeat_question(user_id)
        if repeat_count == 6:
            user_control_module.set_user_privilege(str(user_id), perm.BANNED, True)
            return ''

        if repeat_count > 3:
            return ''

        user_control_module.set_user_repeat_question(user_id)
        return '你怎么又问一遍？'

    elif question in user_control_module.get_user_dict():
        user_control_module.last_question = question
        response = user_control_module.get_user_response(question)
        if isinstance(response, dict):
            response = response['answer']
        elif isinstance(response, list):
            response = random.choice(response)
            response = response['answer']
        else:
            raise ValueError('Invalid data type for answer.')

        return response if response != '$' else ''

    if 'おやすみ' in question:
        return ''

    if '屑bot' in question:
        return '你屑你🐴呢'

    if re.match('.*?(祈|衤|qi).*?(雨|yu)', question):
        return '不敢答，不敢答……溜了溜了w'

    if re.match('.*?你(几|多少?)(岁|大|年龄)', question):
        random.seed(time.time_ns())
        rand_num = random.randint(0, 101)
        if rand_num > 76:
            resp = '我永远的17岁。'
        elif rand_num > 45:
            resp = '我38岁，有两子'
        elif rand_num > 22:
            resp = '我今年1337岁'
        else:
            resp = '我今年114514岁了'

        return resp

    if re.match(r'.*?(爱不爱|喜不喜欢).*?妈妈', question):
        return '答案肯定是肯定的啦~'

    if '妈妈' in question:
        return '请问你有妈妈么？:)'

    return ''


def _request_api_response(question: str) -> str:
    if '鸡汤' in question:
        try:
            page = requests.get('https://api.daidr.me/apis/poisonous', timeout=5)
            response = page.text
        except Exception as err:
            nonebot.logger.warning(err)
            response = '我还不太会回答这个问题哦！不如换种问法？'

    else:
        try:
            page = requests.get(
                f'http://i.itpk.cn/api.php?question={question}'
                f'&limit=7'
                f'&api_key={config.itpk_key}'
                f'&api_secret={config.itpk_secret}',
                timeout=5)

            if not '笑话' in question:
                response = page.text.replace("\ufeff", "")
            else:
                data = json.loads(page.text.replace("\ufeff", ""))
                response = str(data['content']).replace('\r', '')

        except Exception as err:
            nonebot.logger.warning(err)
            response = '我还不太会回答这个问题哦！不如换种问法？'

    return response


@nonebot.on_command('移除语料', only_to_me=False)
async def delete_ai_response(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.WHITELIST):
        key_word = session.get('key_word', prompt='请输入要移除的语料')
        if user_control_module.delete_response(key_word):
            await session.send('已删除该语料')
        else:
            await session.send('语料删除失败，关键词未找到。')
    else:
        await session.send('您无权删除语料。')


@delete_ai_response.args_parser
@add_monitor_word.args_parser
@add_blacklist_word.args_parser
async def _deleteAIResponse(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['key_word'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('啊？要我删什么？')
    session.state[session.current_key] = stripped_arg


@nonebot.on_command('语料查询', only_to_me=False)
async def getAnswerInfo(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.WHITELIST):
        keyWord = session.get('keyWord', prompt='请输入需要查询的预料关键词')
        await session.send(user_control_module.get_response_info(keyWord))


@nonebot.on_natural_language(only_to_me=False, only_short_message=True)
async def send_answer(session: nonebot.NLPSession):
    random.seed(time.time_ns())
    rand_num = random.randint(0, 2)
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        return

    group_id = ctx['group_id']

    if admin_control.get_data(group_id, 'enabled'):
        message = str(ctx['raw_message'])
        if get_privilege(ctx['user_id'], perm.BANNED):
            return

        if 'group_id' in ctx:
            if rand_num == 1 and message in user_control_module.get_user_dict():
                group_id = str(ctx['group_id'])
                try:
                    if group_id not in user_control_module.last_question or \
                            user_control_module.last_question[group_id] != message:
                        user_control_module.last_question[group_id] = message
                        await session.send(user_control_module.get_user_response(message))

                except Exception as err:
                    print(f"Something went wrong: {err}")
                    return

                if ctx['group_id'] not in admin_control.repeat_dict:
                    admin_control.repeat_dict[ctx['group_id']] = {message: 1}
                else:
                    if message in admin_control.repeat_dict[ctx['group_id']]:
                        admin_control.repeat_dict[ctx['group_id']][message] += 1
                        if admin_control.repeat_dict[ctx['group_id']][message] == 3:
                            await session.send(message)
                            return

                    else:
                        admin_control.repeat_dict[ctx['group_id']] = {}
                        admin_control.repeat_dict[ctx['group_id']] = {message: 1}


@nonebot.on_command('ban', only_to_me=False)
async def ban_someone(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.ADMIN):
        try:
            user_id = int(session.get('user_id', prompt='请输入要封禁的qq'))
        except ValueError:
            await session.send('输入非QQ号，发生错误！')
            return

        user_control_module.set_user_privilege(str(user_id), 'BANNED', True)
        await session.send('Done!!')

    else:
        await session.send('您无权进行该操作')
        return


@nonebot.on_command('unban', only_to_me=False)
async def unban_someone(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    if get_privilege(ctx['user_id'], perm.ADMIN):
        try:
            user_id = int(session.get('user_id', prompt='请输入要封禁的qq'))
        except ValueError:
            await session.send('输入非QQ号，发生错误！')
            return

        user_control_module.set_user_privilege(str(user_id), perm.BANNED, False)
        await session.send('Done!!')

    else:
        await session.send('您无权进行该操作')


@ban_someone.args_parser
@unban_someone.args_parser
@add_whitelist.args_parser
@add_admin.args_parser
@delete_admin.args_parser
@delete_whitelist.args_parser
async def _ban_args(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['user_id'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('qq号不得为空哦¿')

    session.state[session.current_key] = stripped_arg
