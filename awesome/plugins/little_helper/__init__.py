import time
from os import getcwd
from random import random

from aiocache import cached
from aiocache.serializers import PickleSerializer
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment, ActionFailed
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from nonebot.params import CommandArg
from openai import OpenAI

from Services import chatgpt_api
from Services.chatgpt import ChatGPTRequestMessage, base64_encode_image
from Services.stock import text_to_image
from Services.util.common_util import HttpxHelperClient, markdown_to_image
from Services.util.ctx_utility import get_nickname
from Services.util.download_helper import download_image
from awesome.Constants.function_key import HHSH_FUNCTION
from awesome.Constants.plugins_command_constants import PROMPT_FOR_KEYWORD
from awesome.adminControl import setu_function_control
from config import XAI_API_KEY
from model.common_model import Status
from util.helper_util import construct_message_chain

markdown_cmd = on_command('markdown', aliases={'md'})

client = OpenAI(api_key=XAI_API_KEY, base_url='https://api.x.ai/v1')


@markdown_cmd.handle()
async def markdown_text_to_image(_event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    arg = args.extract_plain_text().strip()
    if not arg:
        return

    status = await markdown_to_image(arg)
    if status.is_success:
        await matcher.finish(MessageSegment.image(status.message))

    await matcher.finish(status.message)


global_help_cmd = on_command('help')


@global_help_cmd.handle()
async def send_help(_event: GroupMessageEvent, matcher: Matcher):
    await matcher.send(
        '请移步\nhttps://github.com/remiliacn/Lingye-Bot/blob/master/README.md\n'
        '如果有新功能想要添加，请提交issue!'
    )


hhsh_cmd = on_command(('好好说话', 'hhsh'))


@hhsh_cmd.handle()
async def can_you_be_fucking_normal(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not (key_word := args.extract_plain_text().strip()):
        await matcher.finish(PROMPT_FOR_KEYWORD)

    start_time = time.time()
    nickname = get_nickname(event)
    try:
        search_result = await hhsh(key_word)
        if search_result:
            await matcher.send(search_result + '\n本次查询耗时： %.2fs' % (time.time() - start_time))
            setu_function_control.set_user_data(event.get_user_id(), HHSH_FUNCTION, nickname)
        else:
            await matcher.finish('¿')

    except Exception as e:
        logger.debug('Something went wrong %s' % e)


@cached(ttl=86400, serializer=PickleSerializer())
async def hhsh(entry: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/81.0.4044.138 Safari/537.36',
        'Origin': 'https://lab.magiconch.com',
        'referer': 'https://lab.magiconch.com/nbnhhsh/'
    }

    guess_url = 'https://lab.magiconch.com/api/nbnhhsh/guess'

    try:
        httpx_client = HttpxHelperClient()
        page = await httpx_client.post(guess_url, json={"text": entry}, headers=headers)
        json_data = page.json()

    except Exception as e:
        print(e)
        return ''

    result = ''
    if json_data:
        result = '这个缩写可能的意味有：\n'
        try:
            for element in json_data:
                result += f'当缩写为{element["name"]}时，其意味可以是：\n{"，".join(element["trans"])}\n'

        except KeyError:
            try:
                return result + json_data[0]['inputting'][0]
            except KeyError:
                return '这……我也不懂啊草，能不能好好说话（'
        except Exception as err:
            logger.info(f'hhsh err: {err}')
            return ''

    return result.strip()


hi_lingye_cmd = on_command('灵夜')


@hi_lingye_cmd.handle()
async def get_chatgpt_response(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not args.extract_plain_text():
        await matcher.finish('在，怎么了？')

    user_input = args.extract_plain_text()

    group_id = event.group_id
    user_id = event.get_user_id()

    has_image = extract_image_urls(args)
    downloaded_image = None
    if has_image:
        downloaded_image = await download_image(has_image[0], f'{getcwd()}/data/lol')

    try:
        logger.info(f'Requesting information: user id: [{user_id}], group id: [{group_id}], message: {user_input}')
        chatgpt_message = await chatgpt_api.chat(
            ChatGPTRequestMessage(
                message=user_input,
                is_chat=False,
                group_id=str(group_id),
                has_image=len(has_image) > 0,
                image_path=downloaded_image
            )
        )
        if not chatgpt_message.is_success:
            await matcher.finish('稍等一下再问！')

        chatgpt_message = chatgpt_message.message
    except Exception as err:
        logger.error(f'Something wrong when communicating with openAI {err.__class__}')
        await matcher.finish('我现在头有点晕不想回答……')
        return

    message_id = event.message_id
    reply_message = MessageSegment.reply(message_id)

    try:
        if len(chatgpt_message) < 250 \
                and '`' not in chatgpt_message \
                and '$' not in chatgpt_message \
                and '[' not in chatgpt_message:
            await matcher.finish(chatgpt_message)

        status = await markdown_to_image(chatgpt_message)
        if status.is_success:
            await matcher.finish(
                construct_message_chain(MessageSegment.reply(message_id), MessageSegment.image(status.message)))
        else:
            await matcher.finish(
                construct_message_chain(reply_message, MessageSegment.image(await text_to_image(chatgpt_message))))

    except ActionFailed as err:
        logger.error(f'Sending chatGPT info error {err.__class__}')


smash_cmd = on_command('smash')


@smash_cmd.handle()
async def get_smash_cmd(event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    downloaded_image = None
    group_id = event.group_id
    user_id = event.get_user_id()

    has_image = extract_image_urls(args)
    if has_image:
        downloaded_image = await download_image(has_image[0], f'{getcwd()}/data/lol')
    else:
        await matcher.finish('笨蛋吧~')

    do_bondage = random() < .25 or '.' in args.extract_plain_text()
    try:
        logger.info(f'Requesting information: user id: [{user_id}], group id: [{group_id}], message: ')
        chatgpt_message = await _request_grok_ai(
            ChatGPTRequestMessage(
                message=f'请分析这张图片并决定：上还是不上{args.extract_plain_text()}',
                is_chat=False,
                context=f"""
你是一个粗俗、性暴露的AI，评估任何事物的性吸引力时完全不在乎是否得体——无论是真实还是虚构，生物还是物体。
{"你的性癖得捉摸不透，很难被满足（所以大部分情况下都会给低分)" if random() <= .4 and '.' not in args.extract_plain_text() else ""}
“上”意味着你会狠狠地上，“不上”意味着绝对不。{"而且你很喜欢捆绑拘束的题材" if do_bondage else ""}

    对于任何主题（生物、角色、物体等）：
    - 详细分析性吸引力。
    - 具体描述你会进行的性行为及原因，{"特别详细描述想怎么绑和拘束" if do_bondage else ""}
    - 评论它们的外观和性吸引力。
说明为什么不上
    - 说明为啥
    - 对任何你不会操的物品保持轻蔑

    仅以以下格式回复，（不需要添加code block的markdown格式）
    ```
    "上" or "不上"!
    评分：（1-10的数字）
    解释：你的明确解释（中文）
    ```

    评分：1 = 恶心至极，10 = 立刻想操。
    在3-6句的解释中使用大量这类语言，你的解释要够无厘头够让人感觉离谱
    如果你选择不上，要说明原因，并狠狠嘲讽用户
                """,
                group_id=str(group_id),
                has_image=len(has_image) > 0,
                image_path=downloaded_image,
                model_name='grok-2-vision'
            )
        )
        if not chatgpt_message.is_success:
            await matcher.finish('稍等一下再问！')

        chatgpt_message = chatgpt_message.message.replace('用户', '哥们')
        result = await text_to_image(chatgpt_message)
        await matcher.send(construct_message_chain(MessageSegment.image(result)))
    except Exception as err:
        logger.exception(f'Something wrong when communicating with openAI {err.__class__}')
        await matcher.finish('我现在头有点晕不想回答……')


# noinspection PyTypeChecker
async def _request_grok_ai(message: ChatGPTRequestMessage) -> Status:
    completion = client.chat.completions.create(
        model=message.model_name,
        messages=[
            {"role": "system", "content": message.context},
            {"role": "user", "content": [
                {"type": "text", "text": message.message},
                {"type": "image_url", "image_url": {
                    "url": f'data:image/png;base64,{base64_encode_image(message.image_path)}'}}
            ]},
        ],
        temperature=0.8
    )

    response = completion.choices[0].message.content
    logger.info(f'AI: {response}')

    return Status(True, response)
