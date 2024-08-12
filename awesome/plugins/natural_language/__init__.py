import re
from os import getcwd
from random import seed, randint
from re import fullmatch, match, sub
from time import time_ns
from typing import List

import jieba
import jieba.posseg as pos
from aiocache import cached
from aiocache.serializers import PickleSerializer
from loguru import logger
from nonebot import MatcherGroup
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment, ActionFailed, Bot, Message
# noinspection PyProtectedMember
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.internal.matcher import Matcher
from nonebot.rule import is_type, keyword

from Services.util.common_util import compile_forward_message, markdown_to_image
from Services.util.ctx_utility import get_group_id
from Services.util.sauce_nao_helper import sauce_helper
from util.helper_util import anime_reverse_search_response, get_downloaded_quote_image_path, construct_message_chain
from ..little_helper import hhsh
from ...Constants import group_permission
from ...adminControl import group_control

nlp_matcher_group = MatcherGroup(
    rule=is_type(GroupMessageEvent) & keyword('添加语录', 'md', '搜图', '撤回', 'need'))
natural_language = nlp_matcher_group.on_message(priority=4, block=False)


@natural_language.handle()
async def natural_language_proc(bot: Bot, event: GroupMessageEvent, matcher: Matcher):
    seed(time_ns())

    group_id = get_group_id(event)
    message = event.get_message()
    plain_message = message.extract_plain_text()

    if '添加语录' in message:
        if replied_message := event.reply:
            extracted_images = extract_image_urls(replied_message.message)
            if extracted_images:
                path = get_downloaded_quote_image_path(extracted_images[0], f'{getcwd()}/data/lol')

                if path:
                    group_control.add_quote(group_id, path)
                    await matcher.finish(f'已添加！（当前总语录条数：{group_control.get_group_quote_count(group_id)})')

    if 'md' in plain_message[:4]:
        message_list = plain_message.split('\n')
        if len(message_list) >= 2:
            valid_message = '\n'.join(message_list[1:])
            result, success = markdown_to_image(valid_message)
            if success:
                await matcher.finish(MessageSegment.image(result))

    if plain_message.startswith('搜图') and event.get_message().get('image'):
        response = await _do_soutu_operation(event.get_message())
        await matcher.finish(construct_message_chain(response))

    reply_response = await _check_reply_keywords(event, event.reply, event.self_id, bot)
    if reply_response:
        try:
            await bot.send_group_forward_msg(
                group_id=group_id,
                messages=compile_forward_message(event.self_id, reply_response)
            )
            await matcher.finish()
        except ActionFailed:
            await matcher.finish(reply_response)

    if group_control.get_group_permission(group_id, group_permission.NLP):
        if match(r'.*?哼{2,}啊+', plain_message):
            await matcher.finish('别臭了别臭了！孩子要臭傻了')

        if fullmatch(r'^(\S)\1need$', plain_message.strip()):
            await matcher.finish(f'不许{message[0]}')

        fetch_result = await _check_if_asking_definition(plain_message)
        if fetch_result:
            await matcher.finish(fetch_result)

    matcher.skip()


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
            if key_word == '这':
                return ''

            result = ''
            if key_word.isalpha():
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


async def _check_reply_keywords(
        message: GroupMessageEvent, reply: Reply, self_id: int, bot: Bot) -> [str, List[MessageSegment]]:
    if reply:
        message_str = message.get_plaintext()
        if '搜图' in message_str:
            response = await _do_soutu_operation(reply)
        elif '复述' in message_str:
            response = await _do_tts_send(reply)
        elif '撤' in message_str:
            await _do_delete_msg(bot, reply, self_id)
            response = ''
        else:
            response = ''
    else:
        response = ''

    return response.strip() if isinstance(response, str) else response


async def _do_tts_send(message: Reply) -> str:
    message = message.message.extract_plain_text()
    message = sub(r'\[CQ.*?]', '', message)

    return f'[CQ:tts,text={message}]'


async def _do_delete_msg(bot: Bot, reply: Reply, self_id: int):
    if reply.sender.user_id != self_id:
        return

    await bot.delete_msg(message_id=reply.message_id)


@cached(ttl=86400, serializer=PickleSerializer())
async def _do_soutu_operation(reply: Reply | Message) -> List[MessageSegment]:
    response = []
    possible_image_content = extract_image_urls(reply.message if isinstance(reply, Reply) else reply)
    if possible_image_content:
        for idx, url in enumerate(possible_image_content):
            logger.info(f'URL extracted: {url}')
            try:
                response_data = await sauce_helper(url)
                if not response_data:
                    response += f'图片{idx + 1}无法辨别的说！'
                else:
                    response += f'==={idx + 1}===\n' if len(possible_image_content) > 1 else ''
                    response += anime_reverse_search_response(response_data)

            except Exception as err:
                logger.warning(f'soutu function error: {err}')
                return [MessageSegment.text(f'啊这~图片{idx + 1}无法获取有效逆向数据。')]
            finally:
                response += '\n\n'

        return response

    return [MessageSegment.text('阿这，是我瞎了么？好像没有图片啊原文里。')]
