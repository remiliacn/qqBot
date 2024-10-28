import time

from aiocache import cached
from aiocache.serializers import PickleSerializer
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment, ActionFailed
from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from nonebot.params import CommandArg

from Services import chatgpt_api
from Services.chatgpt import ChatGPTRequestMessage
from Services.stock import text_to_image
from Services.util.common_util import HttpxHelperClient, markdown_to_image
from Services.util.ctx_utility import get_nickname
from awesome.Constants.function_key import HHSH_FUNCTION
from awesome.Constants.plugins_command_constants import PROMPT_FOR_KEYWORD
from awesome.adminControl import setu_function_control
from util.helper_util import construct_message_chain

markdown_cmd = on_command('markdown', aliases={'md'})


@markdown_cmd.handle()
async def markdown_text_to_image(_event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()):
    arg = args.extract_plain_text().strip()
    if not arg:
        return

    result, success = markdown_to_image(arg)
    if success:
        await matcher.finish(MessageSegment.image(result))

    await matcher.finish(result)


search_deprecated_cmd = on_command('搜索')


@search_deprecated_cmd.handle()
async def search_command(_event: GroupMessageEvent, matcher: Matcher):
    await matcher.finish('改功能已被废弃，请使用！灵夜。')


global_help_cmd = on_command('help')


@global_help_cmd.handle()
async def send_help(_event: GroupMessageEvent, matcher: Matcher):
    await matcher.send(
        '请移步\nhttps://github.com/remiliacn/Lingye-Bot/blob/master/README.md\n'
        '如果有新功能想要添加，请提交issue!'
    )


hhsh_cmd = on_command('好好说话')


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
        client = HttpxHelperClient()
        page = await client.post(guess_url, json={"text": entry}, headers=headers)
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

    try:
        logger.info(f'Requesting information: user id: [{user_id}], group id: [{group_id}], message: {user_input}')
        chatgpt_message = await chatgpt_api.chat(
            ChatGPTRequestMessage(message=user_input, is_chat=False, group_id=str(group_id)))
        if not chatgpt_message.is_success:
            await matcher.finish('稍等一下再问！')

        chatgpt_message = chatgpt_message.message
    except Exception as err:
        logger.error(f'Something wrong when communicating with openAI {err.__class__}')
        await matcher.finish('我现在头有点晕不想回答……')

    message_id = event.message_id
    reply_message = MessageSegment.reply(message_id)

    try:
        if len(chatgpt_message) < 250 \
                and '`' not in chatgpt_message \
                and '$' not in chatgpt_message \
                and '[' not in chatgpt_message:
            await matcher.finish(chatgpt_message)

        result, success = markdown_to_image(chatgpt_message)
        if success:
            await matcher.finish(
                construct_message_chain(MessageSegment.reply(message_id), MessageSegment.image(result)))
        else:
            await matcher.finish(
                construct_message_chain(reply_message, MessageSegment.image(await text_to_image(chatgpt_message))))

    except ActionFailed as err:
        logger.error(f'Sending chatGPT info error {err.__class__}')
