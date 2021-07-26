import asyncio
import re
from datetime import datetime
from os import getcwd
from random import seed, randint
from re import fullmatch, findall, match, sub
from time import time_ns
from typing import Union

import jieba
import jieba.posseg as pos
import nonebot
from loguru import logger

import config
from awesome.adminControl import permission as perm
from awesome.plugins.setu.setu import sauce_helper
from awesome.plugins.util.helper_util import anime_reverse_search_response, get_downloaded_image_path
from qq_bot_core import admin_control, user_control_module
from ..little_helper.little_helper import hhsh, cache
from ..util import search_helper

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

    if '添加语录' in message:
        bot = nonebot.get_bot()
        has_image = re.findall(r'.*?\[CQ:image,file=(.*?\.image)]', message)
        if has_image:
            response = await bot.get_image(file=has_image[0])
            path = get_downloaded_image_path(response, f'{getcwd()}/data/lol')

            if path:
                admin_control.add_quote(group_id, path)
                await session.send(f'已添加！（当前总语录条数：{admin_control.get_group_quote_count(group_id)})')
                return

    if match(r'.*?哼{2,}啊+', message):
        await session.send('别臭了别臭了！孩子要臭傻了')
        return

    auto_reply = _do_auto_reply_retrieve(user_id, group_id, message)
    if auto_reply:
        await session.send(auto_reply)
        return

    reply_response = await _check_reply_keywords(message, session.self_id)
    if reply_response:
        await session.send(reply_response)
        return

    message = message.strip()
    fetch_result = _repeat_and_palindrome_fetch(message)
    if fetch_result:
        await session.send(fetch_result)

    fetch_result = await _check_if_asking_definition(message)
    if fetch_result:
        sleep_time = len(fetch_result) // 25
        await asyncio.sleep(sleep_time)
        await session.send(fetch_result)

    if admin_control.get_group_permission(group_id, 'flash', default_if_none=False):
        fetch_flash_image = await _get_flash_image_entry(message)
        if fetch_flash_image:
            await session.send(f'已拦截到闪照~\n'
                               f'[CQ:image,file={fetch_flash_image}]')


async def _get_flash_image_entry(message: str) -> str:
    if re.match(r'.*?\[CQ:image,type=flash', message):
        logger.debug('Flash image found.')
        has_image = findall(r'file=(.*?\.image)', message)
        logger.debug(f'Flash image: {has_image}')
        if has_image:
            return has_image[0]
    return ''


async def _check_if_asking_definition(message: str) -> str:
    keyword_regex = r'(.*?)是个?(什么|啥)'
    if re.match(keyword_regex, message) and '不是' not in message:
        logger.success(f'hit asking definition. {message}')
        if randint(0, 10) < 5:
            logger.success('hit random chance.')
            extracted_keyword = re.findall(keyword_regex, message)

            if not extracted_keyword:
                return ''

            sentence = extracted_keyword[0][0]
            logger.info(f'first pass keyword: {sentence}')
            if len(sentence) > 4:
                try:
                    key_word = _extract_keyword_from_sentence(sentence)
                except Exception as err:
                    logger.warning(err)
                    return ''
            else:
                key_word = sentence

            logger.info(f'second pass keyword: {key_word}')
            result = cache.get_result(key_word, 'WIKIPEDIA')
            if not result:
                result = await search_helper.get_definition(key_word)
                if result:
                    cache.store_result(key_word, result, 'WIKIPEDIA')
                if not result and key_word.isalpha():
                    result = await hhsh(key_word)

            return result

    return ''


def _extract_keyword_from_sentence(key_word: str) -> str:
    _ = pos.cut(key_word)
    jieba.enable_paddle()

    # 添加“是”这个指示词帮助分词选定最后一个名词
    words = pos.cut(key_word + '是', use_paddle=True)
    words = [(word, flag) for word, flag in words if 'n' in flag or flag in ('PER', 'LOC', 'ORG')]

    if not words:
        return ''

    key_word = words[-1][0]
    key_word = re.sub(r'[，。、；’【】！￥…（）《》？：”“‘]', '', key_word)
    return key_word


def _repeat_and_palindrome_fetch(message: str) -> str:
    repeat_syntax = r'^(.*?)\1+$'
    rand_chance = randint(0, 10)
    if fullmatch(repeat_syntax, message):
        word_repeat = findall(repeat_syntax, message)[0]
        count = message.count(word_repeat)
        if count >= 3 and rand_chance < 4:
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

    if admin_control.get_group_permission(group_id, 'enabled'):
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


async def _check_reply_keywords(message: str, self_id: int) -> str:
    if '[CQ:reply' in message:
        if '搜图' in message:
            response = await _do_soutu_operation(message)
        elif '复述' in message:
            response = await _do_tts_send(message)
        elif '撤' in message:
            await _do_delete_msg(message, self_id)
            response = ''
        else:
            response = ''
    else:
        response = ''

    return response.strip()


async def _do_delete_msg(message: str, self_id):
    bot = nonebot.get_bot()
    reply_id = findall(r'\[CQ:reply,id=(.*?)]', message)[0]
    message_info = await bot.get_msg(message_id=int(reply_id))

    if message_info['sender']['user_id'] != self_id:
        return

    await bot.delete_msg(message_id=int(reply_id))


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
            logger.info(f'URL extracted: {url}')
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
