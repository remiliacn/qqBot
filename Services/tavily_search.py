from dataclasses import dataclass
from typing import List, Optional

from async_lru import alru_cache
from nonebot import logger

from Services.util import global_httpx_client
from config import TAVILY_API_KEY


@dataclass
class TavilySearchResult:
    title: str
    url: str
    content: str


def _normalize_query(query: str) -> str:
    return " ".join((query or "").strip().split())


@alru_cache(maxsize=256, ttl=60 * 60)
async def _tavily_search_cached(query: str, max_results: int = 5) -> Optional[List[TavilySearchResult]]:
    q = _normalize_query(query)
    if not q:
        return []

    if not TAVILY_API_KEY:
        logger.warning("Tavily API is not configured (TAVILY_API_KEY).")
        return None

    body = {
        "api_key": TAVILY_API_KEY,
        "query": q,
        "max_results": max(1, min(int(max_results), 10)),
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        resp = await global_httpx_client.post("https://api.tavily.com/search", json=body, timeout=15.0)
        if resp.status_code != 200:
            logger.warning(f"Tavily request failed: status={resp.status_code}, body={resp.text[:500]}")
            return None

        data = resp.json() or {}
        items = data.get("results") or []

        results: List[TavilySearchResult] = []
        for item in items[: body["max_results"]]:
            results.append(
                TavilySearchResult(
                    title=str(item.get("title", "")).strip(),
                    url=str(item.get("url", "")).strip(),
                    content=str(item.get("content", "")).strip(),
                )
            )

        logger.info('Tavily search results: ' + str(results))
        return results
    except Exception as err:
        logger.error(f"Tavily request error: {err}")
        return None


async def tavily_search(query: str, max_results: int = 5) -> Optional[List[TavilySearchResult]]:
    return await _tavily_search_cached(_normalize_query(query), max_results)


def format_search_results_for_llm(results: List[TavilySearchResult], max_chars: int = 1800) -> str:
    if not results:
        return "(no results)"

    parts: List[str] = []
    for idx, r in enumerate(results, start=1):
        parts.append(f"[{idx}] {r.title}\n{r.content}\nURL: {r.url}")

    text = "\n\n".join(parts).strip()
    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "..."
