from asyncio import Task, create_task
from dataclasses import dataclass
from functools import lru_cache
from json import loads
from typing import Tuple

from nonebot import logger


@dataclass(frozen=True)
class WebSearchJudgeResult:
    need_search: bool
    query: str


class WebSearchJudgeMixin:

    @property
    def _judge_instructions(self) -> str:
        return (
            "你是一个路由器。任务：判断用户问题是否需要联网搜索才能可靠回答。\n"
            "仅输出严格 JSON，不要输出任何多余文字、代码块、解释。\n"
            "输出格式必须为："
            '{"need_search": true/false, "query": "用于搜索的简短关键词或问题（中文/英文均可）"}\n\n'
            "判断标准：\n"
            "- 涉及最新信息、时效性强、价格/政策/发布/现任职位/新闻/数据统计/需要来源 => need_search=true\n"
            "- 如果 input 是一个网站/链接 => need_search=true\n"
            "- 纯聊天、写作、代码、数学、常识解释、主观建议 => need_search=false\n"
            "- 如果问题可以在不联网的情况下给出可靠回答 => need_search=false\n"
            "- query 尽量短，能直接用于搜索\n"
        )

    @staticmethod
    def _normalize_judge_text(text: str) -> str:
        t = (text or "").strip()
        t = " ".join(t.split())
        return t[:500]

    @staticmethod
    def _extract_json_object(text: str) -> str:
        raw = (text or "").strip()
        if not raw:
            return ""
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end != -1 and end > start:
            return raw[start:end + 1]
        return raw

    @classmethod
    def _parse_judge_json(cls, raw: str, fallback_query: str) -> WebSearchJudgeResult:
        try:
            data = loads(cls._extract_json_object(raw))
            need = bool(data.get("need_search", False))
            query = str(data.get("query", "")).strip()
            if need and not query:
                query = (fallback_query or "").strip()[:200]
            return WebSearchJudgeResult(need, query)
        except Exception as err:
            logger.error(f"Failed to parse judge output: {err}; raw={str(raw)[:300]}")
            return WebSearchJudgeResult(False, "")

    async def _judge_llm_raw(self, user_text: str) -> str:  # pragma: no cover
        raise NotImplementedError

    @lru_cache(maxsize=2048)
    def _judge_task(self, _key: str, raw_text: str) -> Task[WebSearchJudgeResult]:
        return create_task(self._judge_need_web_search_uncached(raw_text))

    async def _judge_need_web_search_uncached(self, user_text: str) -> WebSearchJudgeResult:
        raw = ""
        try:
            raw = (await self._judge_llm_raw(user_text)) or ""
        except Exception as err:
            logger.error(f"Judge LLM call failed: {err}")
            return WebSearchJudgeResult(False, "")

        return self._parse_judge_json(raw, user_text)

    async def judge_need_web_search(self, user_text: str) -> Tuple[bool, str]:
        key = self._normalize_judge_text(user_text)
        task = self._judge_task(key, user_text)
        try:
            result = await task
            return result.need_search, result.query
        except Exception as err:
            logger.error(f"Judge pipeline failed: {err}")
            self._judge_task.cache_clear()
            return False, ""
