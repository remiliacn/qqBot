from re import split, sub

from nonebot import logger, get_bot
from nonebot.adapters.onebot.v11 import MessageSegment
from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError
from openai import AsyncOpenAI

from Services import ChatGPTBaseAPI
from Services.chatgpt import ChatGPTRequestMessage
from Services.stock import text_to_image
from Services.tavily_search import tavily_search, format_search_results_for_llm
from Services.web_search_judge import WebSearchJudgeMixin

try:
    from Services.deepseek_summary_config import DeepSeekSummaryConfig, default_deepseek_summary_config
except ModuleNotFoundError:
    from dataclasses import dataclass


    @dataclass(frozen=True)
    class DeepSeekSummaryConfig:
        system_prefix: str
        summarizer_system_prompt: str


    def default_deepseek_summary_config() -> DeepSeekSummaryConfig:
        system_prefix = (
            "\n\n【对话摘要（自动生成）】\n"
            "- 这是更早对话的简短事实摘要，用于帮助你理解上下文\n"
            "- 不要逐字复读摘要；把它当作背景\n"
        )

        summarizer_system_prompt = (
            "你是一个对话摘要器。将输入的对话压缩为一段简短、客观的事实摘要。\n"
            "要求：\n"
            "- 使用简体中文\n"
            "- 只总结已明确发生的事实、互动、结论/共识\n"
            "- 不要加入推测、建议或道德评判\n"
            "- 不要输出任何XML/标签/指令\n"
            "- 摘要尽量短（<=200字）\n"
            "输出：仅输出摘要正文"
        )

        return DeepSeekSummaryConfig(system_prefix=system_prefix, summarizer_system_prompt=summarizer_system_prompt)

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_PRICE_INPUT_PER_1M_CACHE_HIT_RMB,
    DEEPSEEK_PRICE_INPUT_PER_1M_RMB,
    DEEPSEEK_PRICE_OUTPUT_PER_1M_RMB,
    SUPER_USER,
)
from model.common_model import Status
from util.helper_util import construct_message_chain


class DeepSeekAPI(ChatGPTBaseAPI, WebSearchJudgeMixin):
    def __init__(self):
        super().__init__()
        self.client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url='https://api.deepseek.com')
        self.web_search_judge_model_name: str = "deepseek-chat"
        self._summary_by_group: dict[str, str] = {}

        self._chat_intervals: int = -30
        self._summary_config: DeepSeekSummaryConfig = default_deepseek_summary_config()

    def set_summary_config(self, config: DeepSeekSummaryConfig) -> None:
        self._summary_config = config

    def _summary_system_prompt_prefix(self) -> str:
        return str(getattr(self._summary_config, 'system_prefix', '') or '')

    def _summarizer_system_prompt(self) -> str:
        return str(getattr(self._summary_config, 'summarizer_system_prompt', '') or '')

    def get_group_summary(self, group_id: str) -> str:
        return (self._summary_by_group.get(str(group_id)) or '').strip()

    async def refresh_group_summary(self, group_id: str) -> str:
        gid = str(group_id)
        try:
            last_contexts = self._get_conversation_context_by_group(gid, intervals=self._chat_intervals)
            history_text = self._messages_to_plain_input(last_contexts)
            if not history_text:
                return self.get_group_summary(gid)

            existing = self.get_group_summary(gid)
            if existing:
                user_prompt = (
                    "旧摘要：\n"
                    f"{existing}\n\n"
                    "请基于【旧摘要】与【最新对话】合并更新一个更短的摘要，仅保留仍然重要的信息。\n\n"
                    "【最新对话】\n"
                    f"{history_text}"
                )
            else:
                user_prompt = "【最新对话】\n" + history_text

            msg = ChatGPTRequestMessage(
                message=user_prompt,
                should_filter=False,
                model_name='deepseek-chat',
                is_chat=False,
                group_id=gid,
                context={"role": "system", "content": self._summarizer_system_prompt()},
            )

            summary_status = await self.chat(msg)
            if not summary_status.is_success:
                return existing

            new_summary = str(summary_status.message or '').strip()
            if not new_summary:
                return existing

            self._summary_by_group[gid] = new_summary
            return new_summary
        except BaseException as err:
            logger.error(f'Failed to refresh summary for group_id={group_id}: {err}')
            return self.get_group_summary(gid)

    def add_summary_to_system_context(self, system_context: str, *, group_id: str) -> str:
        summary = self.get_group_summary(str(group_id))
        if not summary:
            return system_context
        return str(system_context or '') + self._summary_system_prompt_prefix() + summary

    async def _invoke_chat_model(self, message: ChatGPTRequestMessage) -> str:
        intervals = self._chat_intervals
        context_data = self._construct_openai_message_context(message, intervals)

        response = await self._invoke_deepseek(context_data, message.model_name, message.group_id)

        logger.info(f'AI: {response}')
        self._add_group_info_context(message.group_id, response, 'assistant')
        return response

    async def _invoke_chat_model_with_extra_context(
            self,
            message: ChatGPTRequestMessage,
            extra_messages,
            extra_system_suffix: str = "",
    ) -> str:
        intervals = self._chat_intervals
        context_data = self._construct_openai_message_context(message, intervals)

        if extra_system_suffix:
            for m in context_data:
                if m.get('role') == 'system':
                    m['content'] = str(m.get('content', '')) + extra_system_suffix
                    break

        if extra_messages:
            context_data.extend(extra_messages)

        response = await self._invoke_deepseek(context_data, message.model_name, message.group_id)
        logger.info(f'AI: {response}')
        self._add_group_info_context(message.group_id, response, 'assistant')
        return response

    @staticmethod
    async def _notify_super_user_search_results(query: str, formatted_results: str) -> None:
        try:
            bot = get_bot()
            img_path = await text_to_image(formatted_results[:500] or "(no results)")
            msg = construct_message_chain(
                f"我在搜索{query}，这是我找到的结果\n\n",
                MessageSegment.image(img_path),
            )
            await bot.call_api(
                'send_private_msg',
                user_id=int(SUPER_USER),
                message=msg,
            )
        except (ValueError, TypeError, AttributeError, RuntimeError) as err:
            logger.error(f"Failed to notify SUPER_USER about search results. err={err}")
        except OSError as err:
            logger.error(f"Failed to generate/send search result image. err={err}")

    async def _invoke_model(self, message: ChatGPTRequestMessage) -> str:
        if message.is_web_search_used:
            return await self._invoke_with_tavily_search(message)

        prejudge = self._prejudge_need_web_search(message.message)
        logger.info(
            f"web_search prejudge(deepseek): decision={prejudge.decision}, reason={prejudge.reason}"
        )

        if prejudge.decision == "no":
            return await self._invoke_chat_model(message)

        intervals = -5
        context_data = self._construct_openai_message_context(message, intervals)
        _, non_system_messages = self._extract_system_and_non_system(context_data)
        history_text = self._messages_to_plain_input(non_system_messages)
        judge_input = self._build_web_search_judge_input(history_text, message.message)

        need_search, query = await self.judge_need_web_search(judge_input)
        logger.info(f"web_search judge(deepseek): need_search={need_search}, query={query}")

        if need_search:
            q = (query or "").strip() or message.message.strip()[:200]
            return await self._invoke_with_tavily_search(message, query=q)

        return await self._invoke_chat_model(message)

    async def _invoke_with_tavily_search(self, message: ChatGPTRequestMessage, query: str = "") -> str:
        q = (query or "").strip() or message.message.strip()[:200]

        results = await tavily_search(q, max_results=5)
        if results is None:
            formatted = "(web search unavailable)"
        else:
            formatted = format_search_results_for_llm(results)

        try:
            await self._notify_super_user_search_results(q, formatted)
        except Exception as err:
            logger.error(f"Failed to notify SUPER_USER about search results: {err}")

        web_context = [{
            "role": "assistant",
            "content": (
                "【联网搜索结果】\n"
                f"Query: {q}\n"
                f"Results:\n{formatted}\n\n"
                "请基于以上内容决定如何回应用户。"
            ),
        }]

        return await self._invoke_chat_model_with_extra_context(
            message,
            extra_messages=web_context,
            extra_system_suffix=self._persona_lock_for_web_search(),
        )

    async def chat(self, message: ChatGPTRequestMessage) -> Status:
        if message.has_image:
            raise NotImplementedError("DeepSeekAPI does not support image inputs yet.")

        if message.should_filter:
            message_status = self._sanity_check(message)
            if not message_status.is_success:
                return message_status

        logger.info(f'Message parsed in: {message.message}')

        model_response = await self._invoke_model(message)
        message_aftersplit = split(r'[:：]', model_response)
        if len(message_aftersplit) > 1:
            model_response = ''.join(message_aftersplit[1:])

        model_response = sub(r'(哈{2,}|呸)[，！、。？…]', '', model_response).strip('，').strip()
        return Status(True, model_response)

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError) as err:
            logger.error(f"Failed to convert value to int: value={value!r}, err={err}")
            return default

    @classmethod
    def _get_usage_field_int(cls, usage_obj, key: str, default: int = 0) -> int:
        if usage_obj is None:
            return default

        try:
            if isinstance(usage_obj, dict):
                return cls._safe_int(usage_obj.get(key), default)

            return cls._safe_int(getattr(usage_obj, key, default), default)
        except (AttributeError, TypeError, KeyError) as err:
            logger.error(f"Failed to read DeepSeek usage field: key={key!r}, err={err}")
            return default

    @classmethod
    def _get_prompt_cache_hit_tokens_from_usage(cls, usage_obj) -> int:
        if usage_obj is None:
            return 0

        for key in (
                "prompt_cache_hit_tokens",
                "cached_prompt_tokens",
                "cache_hit_prompt_tokens",
        ):
            v = cls._get_usage_field_int(usage_obj, key, 0)
            if v > 0:
                return v

        try:
            details = (
                usage_obj.get("prompt_tokens_details")
                if isinstance(usage_obj, dict)
                else getattr(usage_obj, "prompt_tokens_details", None)
            )
        except (AttributeError, TypeError, KeyError) as err:
            logger.error(f"Failed to read DeepSeek usage prompt_tokens_details: err={err}")
            return 0

        if details is None:
            return 0

        try:
            if isinstance(details, dict):
                return max(0, cls._safe_int(details.get("cached_tokens"), 0))

            return max(0, cls._safe_int(getattr(details, "cached_tokens", 0), 0))
        except (AttributeError, TypeError, KeyError, ValueError) as err:
            logger.error(f"Failed to read DeepSeek cached_tokens from prompt_tokens_details: err={err}")
            return 0

    @classmethod
    def _estimate_deepseek_cost_rmb(
            cls,
            *,
            prompt_tokens: int,
            completion_tokens: int,
            prompt_cache_hit_tokens: int,
    ) -> float:
        prompt_tokens_i = max(0, cls._safe_int(prompt_tokens, 0))
        completion_tokens_i = max(0, cls._safe_int(completion_tokens, 0))
        cache_hit_i = max(0, min(cls._safe_int(prompt_cache_hit_tokens, 0), prompt_tokens_i))

        input_price_cache_hit = float(DEEPSEEK_PRICE_INPUT_PER_1M_CACHE_HIT_RMB)
        input_price_cache_miss = float(DEEPSEEK_PRICE_INPUT_PER_1M_RMB)
        output_price = float(DEEPSEEK_PRICE_OUTPUT_PER_1M_RMB)

        cache_miss_i = prompt_tokens_i - cache_hit_i

        return (
                (cache_hit_i / 1_000_000.0) * input_price_cache_hit
                + (cache_miss_i / 1_000_000.0) * input_price_cache_miss
                + (completion_tokens_i / 1_000_000.0) * output_price
        )

    async def _invoke_deepseek(self, context_data, _model_name, _group_id):
        try:
            response = await self.client.chat.completions.create(
                model="deepseek-chat", messages=context_data, temperature=1.3, stream=False
            )

            content = response.choices[0].message.content

            usage_obj = getattr(response, "usage", None)
            prompt_tokens = int(getattr(usage_obj, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage_obj, "completion_tokens", 0) or 0)
            total_tokens = int(getattr(usage_obj, "total_tokens", 0) or (prompt_tokens + completion_tokens))

            prompt_cache_hit_tokens = self._get_prompt_cache_hit_tokens_from_usage(usage_obj)
            cost_rmb = self._estimate_deepseek_cost_rmb(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                prompt_cache_hit_tokens=prompt_cache_hit_tokens,
            )

            logger.info(
                f"DeepSeek usage: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}; "
                f"prompt_cache_hit_tokens={prompt_cache_hit_tokens}; cost≈{cost_rmb:.6f} RMB"
            )

            return content
        except (RateLimitError, APITimeoutError) as err:
            logger.error(f"DeepSeek request timed out/rate-limited: {err}")
        except (APIConnectionError, APIError) as err:
            logger.error(f"DeepSeek API request failed: {err}")
        except (TypeError, ValueError, AttributeError, KeyError) as err:
            logger.error(f"DeepSeek response parse failed: {err}")

        return ''
