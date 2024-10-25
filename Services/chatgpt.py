from dataclasses import dataclass
from random import random
from re import split, sub
from typing import List, Iterable, Literal

from nonebot import logger
from openai import OpenAI
from openai.types.chat import ChatCompletionFunctionMessageParam, ChatCompletionToolMessageParam, \
    ChatCompletionAssistantMessageParam, ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam

from Services.util.DFA import DFA
from config import OPEN_API_KEY
from model.common_model import Status


@dataclass
class ChatGPTRequestMessage:
    message: str
    model_name: str = "gpt-4o-mini"
    group_id: str = '1'
    is_chat: bool = False
    should_filter: bool = False
    context: str = None


class ChatGPTBaseAPI:
    def __init__(self):
        self.client = OpenAI(api_key=OPEN_API_KEY)
        self.group_information = {}
        self.filter_word_list = []
        self.dfa = DFA()
        self.dfa.change_words()
        self.SYSTEM_MESSAGE_NON_CHAT = {
            "role": "system",
            "content": "You are a helpful assistant. "
        }

    def _add_group_info_context(self, group_id, message, role: Literal['user', 'assistant']):
        group_id = str(group_id)
        if group_id not in self.group_information:
            self.group_information[group_id] = []

        self.group_information[group_id].append({"role": role, "content": message})

    def _get_conversation_context_by_group(self, group_id, intervals=-10) -> List[str]:
        group_id = str(group_id)
        if group_id not in self.group_information:
            return []

        return self.group_information[group_id][intervals:]

    def _clear_dict_by_group(self, group_id):
        group_id = str(group_id)
        self.group_information[group_id] = []

    def _construct_openai_message_context(self, group_id, is_chat: bool, user_message: str, context=None) -> Iterable[
        ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam |
        ChatCompletionToolMessageParam | ChatCompletionFunctionMessageParam]:

        if not context:
            context = self.SYSTEM_MESSAGE_NON_CHAT

        if isinstance(context, str):
            context = {
                "role": "system",
                "content": context
            }

        group_id = str(group_id)
        self._add_group_info_context(group_id, user_message, 'user')
        last_contexts = self._get_conversation_context_by_group(group_id)

        if is_chat:
            return [context] + last_contexts

        return [self.SYSTEM_MESSAGE_NON_CHAT] + last_contexts[-1:]

    def _sanity_check(self, message: ChatGPTRequestMessage) -> Status:
        if random() < 0.01:
            return Status(False, '作为一个AI机气人，我不提倡与鼓励明知故问的行为。')

        if not message.message:
            return Status(False, '未发现数据')

        message = message.message
        if self.dfa.exists(message):
            return Status(False, '请不要问我类似问题，我的主人不允许我讨论这类话题，谢谢理解。')

        return Status(True, None)

    def _invoke_chat_model(self, message: str, is_chat: bool, model_name: str, group_id: str, context=None) -> str:
        logger.info(f'is it chat? {is_chat}, using gpt model: {model_name}')
        context_data = self._construct_openai_message_context(group_id, is_chat, message, context)

        logger.info(f'chat context: {context_data}')
        completion = self.client.chat.completions.create(
            model=model_name,
            messages=context_data
        )
        response = completion.choices[0].message.content

        logger.info(f'AI: {response}')
        self._add_group_info_context(group_id, response, 'assistant')
        return response

    def chat(self, message: ChatGPTRequestMessage) -> Status:
        is_chat = message.is_chat
        group_id = message.group_id
        model_name = message.model_name
        context = message.context
        if message.should_filter:
            message_status = self._sanity_check(message)
            if not message_status.is_success:
                return message_status

        message = message.message
        logger.info(f'Message parsed in: {message}')

        message = self._invoke_chat_model(message, is_chat, model_name, group_id, context)
        message_aftersplit = split(r'[:：]', message)
        if len(message_aftersplit) > 1:
            message = ''.join(message_aftersplit[1:])

        message = sub(r'哈哈[，！、。？…]', '', message).strip('，').strip()
        return Status(True, message)
