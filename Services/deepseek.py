from re import split, sub

from nonebot import logger
from openai import AsyncOpenAI

from Services import ChatGPTBaseAPI
from Services.chatgpt import ChatGPTRequestMessage
from config import DEEPSEEK_API_KEY
from model.common_model import Status


class DeepSeekAPI(ChatGPTBaseAPI):
    def __init__(self):
        super().__init__()
        self.client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url='https://api.deepseek.com')

    async def _invoke_chat_model(self, message: ChatGPTRequestMessage) -> str:
        logger.info(f'is it chat? {message.is_chat}, using gpt model: {message.model_name}')
        intervals = -40
        context_data = self._construct_openai_message_context(message, intervals)

        logger.info(f'chat context: {context_data}')

        response = await self._invoke_deepseek(context_data, message.model_name, message.group_id)

        logger.info(f'AI: {response}')
        self._add_group_info_context(message.group_id, response, 'assistant')
        return response

    async def chat(self, message: ChatGPTRequestMessage) -> Status:
        if message.should_filter:
            message_status = self._sanity_check(message)
            if not message_status.is_success:
                return message_status

        logger.info(f'Message parsed in: {message.message}')

        message = await self._invoke_chat_model(message)
        message_aftersplit = split(r'[:：]', message)
        if len(message_aftersplit) > 1:
            message = ''.join(message_aftersplit[1:])

        message = sub(r'(哈{2,}|呸)[，！、。？…]', '', message).strip('，').strip()
        return Status(True, message)

    async def _invoke_deepseek(self, context_data, _model_name, _group_id):
        try:
            response = await self.client.chat.completions.create(
                model="deepseek-chat", messages=context_data, temperature=1.3, stream=False)
            return response.choices[0].message.content
        except Exception as err:
            logger.error(f'Failed to invoke deepseek {err}')

        return ''
