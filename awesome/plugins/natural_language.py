from datetime import datetime
from random import seed, randint
from re import fullmatch, findall, match, sub
from time import time_ns
from typing import Union

import nonebot

import config
from awesome.adminControl import permission as perm
from awesome.plugins.setu import sauce_helper
from awesome.plugins.util.helper_util import anime_reverse_search_response
from qq_bot_core import admin_control, user_control_module

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)


@nonebot.on_natural_language(only_to_me=False, only_short_message=False)
async def natural_language_proc(session: nonebot.NLPSession):
    seed(time_ns())
    context = session.ctx.copy()
    if 'group_id' not in context:
        return

    group_id = context['group_id']
    user_id = context['user_id']
    message = str(context['raw_message'])

    if match(r'.*?哼{2,}啊+', message):
        await session.send('别臭了别臭了！孩子要臭傻了')
        return

    auto_reply = _do_auto_reply_retrieve(user_id, group_id, message)
    if auto_reply:
        await session.send(auto_reply)
        return

    reply_response = await _check_reply_keywords(message)
    if reply_response:
        await session.send(reply_response)
        return

    message = message.strip()
    fetch_result = _repeat_and_palindrome_fetch(message)
    if fetch_result:
        await session.send(fetch_result)


def _repeat_and_palindrome_fetch(message: str) -> str:
    repeat_syntax = r'^(.*?)\1+$'
    if fullmatch(repeat_syntax, message):
        word_repeat = findall(repeat_syntax, message)[0]
        count = message.count(word_repeat)
        if count >= 3:
            return f'{count}个{word_repeat}'
        return ''

    if len(message) > 5 and message == message[::-1]:
        return '好一个回文句！'

    return ''


def _do_auto_reply_retrieve(
        user_id: Union[str, int],
        group_id: Union[str, int],
        message: str
) -> str:
    rand_num = randint(0, 3)

    if admin_control.get_data(group_id, 'enabled'):
        if get_privilege(user_id, perm.BANNED):
            return ''

        if rand_num == 1 and message in user_control_module.get_user_response_dict():
            group_id = str(group_id)
            try:
                if group_id not in user_control_module.get_last_question() or \
                        user_control_module.get_last_question_by_group(group_id) != message:
                    user_control_module.set_last_question_by_group(group_id, message)
                    return user_control_module.get_user_response(message)

            except Exception as err:
                print(f"Something went wrong: {err}")

    return ''


async def _check_reply_keywords(message: str) -> str:
    if '[CQ:reply' in message:
        if '搜图' in message:
            response = await _do_soutu_operation(message)
        elif '复述' in message:
            response = await _do_tts_send(message)
        else:
            response = ''
    else:
        response = ''

    return response.strip()


async def _do_tts_send(message: str) -> str:
    reply_id = findall(r'\[CQ:reply,id=(.*?)]', message)
    bot = nonebot.get_bot()
    data = await bot.get_msg(message_id=int(reply_id[0]))
    message = data['content']
    message = sub(r'\[CQ.*?]', '', message)

    return f'[CQ:tts,text={message}]'


async def _do_soutu_operation(message: str) -> str:
    reply_id = findall(r'\[CQ:reply,id=(.*?)]', message)
    response = ''
    bot = nonebot.get_bot()
    data = await bot.get_msg(message_id=int(reply_id[0]))
    possible_image_content = data['message']
    if not possible_image_content:
        possible_image_content = data['raw_message']

    has_image = findall(r'file=(.*?\.image)', possible_image_content)
    if has_image:
        for idx, element in enumerate(has_image):
            image = await bot.get_image(file=element)
            url = image['url']
            nonebot.logger.info(f'URL extracted: {url}')
            try:
                response_data = await sauce_helper(url)
                if not response_data:
                    response += f'图片{idx + 1}无法辨别的说！'
                else:
                    response += f'==={idx + 1}===\n' if len(has_image) > 1 else ''
                    response += anime_reverse_search_response(response_data)

            except Exception as err:
                await bot.send_private_msg(
                    user_id=config.SUPER_USER,
                    message=f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                            f'搜图功能出错：\n'
                            f'Error：{err}\n'
                            f'出错URL：{url}'
                )
                return f'啊这~图片{idx + 1}搜索出错了！报错信息已发送主人debug~'
            finally:
                response += '\n\n'

        return response

    return '阿这，是我瞎了么？好像没有图片啊原文里。'
