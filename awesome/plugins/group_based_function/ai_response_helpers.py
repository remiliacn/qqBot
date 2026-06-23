import re
from dataclasses import dataclass
from time import time
from typing import Callable, Optional

from loguru import logger
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from Services.meme_db import meme_db
from util.helper_util import construct_message_chain


@dataclass(frozen=True)
class ParsedTag:
    tag_name: str
    content: str
    attributes: dict[str, str]
    start_pos: int
    end_pos: int


def _extract_tags_with_positions(text: str, tag_name: str) -> tuple[str, list[ParsedTag]]:
    pattern = rf'<{tag_name}(.*?)>(.*?)</{tag_name}>'
    parsed_tags: list[ParsedTag] = []

    for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
        attrs_str = match.group(1) or ''
        content = match.group(2).strip()

        attributes: dict[str, str] = {}
        if attrs_str:
            attr_pattern = r'(\w+)\s*=\s*["\']?([^"\'\s>]+)["\']?'
            for attr_match in re.finditer(attr_pattern, attrs_str):
                attributes[attr_match.group(1).lower()] = attr_match.group(2)

        parsed_tags.append(ParsedTag(
            tag_name=tag_name,
            content=content,
            attributes=attributes,
            start_pos=match.start(),
            end_pos=match.end()
        ))

    cleaned_text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    logger.info(f'[_extract_tags_with_positions] tag_name={tag_name}, found {len(parsed_tags)} tags')
    return cleaned_text, parsed_tags


def parse_image_tags_from_response(response: str) -> tuple[str, list[str]]:
    cleaned_response, tags = _extract_tags_with_positions(response, 'image')
    image_keywords = [tag.content for tag in tags if tag.content]
    return cleaned_response.strip(), image_keywords


def parse_mention_tags_from_response(response: str) -> tuple[str, list[str]]:
    cleaned_response, tags = _extract_tags_with_positions(response, 'mention')

    user_ids: list[str] = []
    for tag in tags:
        payload = tag.content.strip()
        if payload and payload.isdigit():
            user_ids.append(payload)

    return cleaned_response.strip(), user_ids


@dataclass(frozen=True)
class MemoryTag:
    content: str
    confidence: float
    is_global: bool = False


@dataclass(frozen=True)
class MemoryParseResult:
    cleaned_text: str
    memory_entries: list[MemoryTag]


def parse_memory_tags_from_response(response: str) -> MemoryParseResult:
    import json

    logger.info(f'[parse_memory_tags] Input: {repr(response[:200])}...' if len(
        response) > 200 else f'[parse_memory_tags] Input: {repr(response)}')

    # Pattern to match JSON-like memory tags: [MEMORY]{"content":"...", "confidence":0.x, "isGlobal":false}[/MEMORY]
    memory_entries: list[MemoryTag] = []

    matches = list(re.findall(r'\[MEMORY](.+?)\[/MEMORY]', response))

    for match in matches:
        json_str = match.strip()
        if not json_str:
            continue

        logger.info(f'[parse_memory_tags] Extracted JSON: {repr(json_str)}')

        try:
            mem_data = json.loads(json_str)
            content = str(mem_data.get('content', '')).strip()

            if not content:
                continue

            confidence = float(mem_data.get('confidence', 0.0))
            confidence = max(0.0, min(1.0, confidence))

            is_global_raw = mem_data.get('isGlobal', False)
            # Only accept boolean True or numeric 1 as truthy values
            if isinstance(is_global_raw, bool):
                is_global = is_global_raw
            elif isinstance(is_global_raw, (int, float)):
                is_global = is_global_raw == 1 or is_global_raw == 1.0
            else:
                is_global = False

            memory_entries.append(MemoryTag(content=content, confidence=confidence, is_global=is_global))
            logger.info(
                f'Parsed memory tag: confidence={confidence:.2f}, is_global={is_global}, content_length={len(content)}')
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as err:
            logger.error(f'Failed to parse memory JSON: {err}, json_str={repr(json_str)}')
            continue

    cleaned_response = re.sub(r'\[MEMORY](.+?)\[/MEMORY]', '', response, flags=re.IGNORECASE | re.DOTALL).strip()
    return MemoryParseResult(cleaned_text=cleaned_response, memory_entries=memory_entries)


@dataclass(frozen=True)
class DeleteMemoryRequest:
    memory_id: int


def parse_delmem_tags_from_response(response: str) -> tuple[str, list[DeleteMemoryRequest]]:
    # Pattern to match [DELMEM]123[/DELMEM]
    pattern = r'\[DELMEM\](.*?)\[/DELMEM\]'

    delete_requests: list[DeleteMemoryRequest] = []

    for match in re.finditer(pattern, response, re.IGNORECASE | re.DOTALL):
        memory_id_str = match.group(1).strip()
        if not memory_id_str:
            continue

        if not memory_id_str.isdigit():
            logger.warning(f'Invalid memory id in delmem tag: {memory_id_str}')
            continue

        memory_id = int(memory_id_str)
        delete_requests.append(DeleteMemoryRequest(memory_id=memory_id))
        logger.info(f'Parsed delete memory request: memory_id={memory_id}')

    cleaned_response = re.sub(pattern, '', response, flags=re.IGNORECASE | re.DOTALL).strip()
    return cleaned_response, delete_requests


def strip_tag_from_response(response: str) -> str:
    first_strip = re.sub(r'<.*?>.*?</.*?>', '', response)
    return re.sub(r'<.*?>', '', first_strip)


@dataclass(frozen=True)
class BanRequest:
    user_id: str
    duration_seconds: int
    banned_until_ts: Optional[int] = None


def parse_ban_tags_from_response(response: str) -> tuple[str, list[BanRequest]]:
    cleaned_response, tags = _extract_tags_with_positions(response, 'ban')

    default_minutes = 300
    max_minutes = 300
    duration_by_user: dict[str, int] = {}

    for tag in tags:
        payload = tag.content
        if not payload:
            continue

        if '||' in payload:
            parts = [p.strip() for p in payload.split('||', 1)]
            parsed_user_id = parts[0] if len(parts) > 0 else ''
            parsed_minutes = parts[1] if len(parts) > 1 else ''
        else:
            parsed_user_id = payload
            parsed_minutes = tag.attributes.get('duration', '')

        if not parsed_user_id.isdigit():
            continue

        minutes = default_minutes
        if parsed_minutes and parsed_minutes.isdigit():
            minutes = int(parsed_minutes)

        if minutes <= 0:
            minutes = default_minutes

        minutes = min(minutes, max_minutes)
        duration_seconds = minutes * 60

        prev = duration_by_user.get(parsed_user_id)
        if prev is None or duration_seconds > prev:
            duration_by_user[parsed_user_id] = duration_seconds

        logger.info(f'Parsed ban request: user_id={parsed_user_id}, duration_minutes={minutes}')

    ban_requests = [BanRequest(user_id=uid, duration_seconds=duration) for uid, duration in duration_by_user.items()]
    return cleaned_response.strip(), ban_requests


@dataclass
class TagParseContext:
    text: str
    image_keywords: list[str]
    ban_requests: list[BanRequest]
    mention_user_ids: list[str]
    memory_entries: list[MemoryTag]
    delete_memory_requests: list[DeleteMemoryRequest]


TagHandler = Callable[[TagParseContext], TagParseContext]


def _handle_image_tags(ctx: TagParseContext) -> TagParseContext:
    cleaned, image_keywords = parse_image_tags_from_response(ctx.text)
    if image_keywords:
        ctx.image_keywords.extend(image_keywords)
    ctx.text = cleaned
    return ctx


def _handle_ban_tags(ctx: TagParseContext) -> TagParseContext:
    cleaned, ban_requests = parse_ban_tags_from_response(ctx.text)
    if ban_requests:
        ctx.ban_requests.extend(ban_requests)
    ctx.text = cleaned
    return ctx


def _handle_mention_tags(ctx: TagParseContext) -> TagParseContext:
    cleaned, mention_user_ids = parse_mention_tags_from_response(ctx.text)
    if mention_user_ids:
        ctx.mention_user_ids.extend(mention_user_ids)
    ctx.text = cleaned
    return ctx


def _handle_memory_tags(ctx: TagParseContext) -> TagParseContext:
    result = parse_memory_tags_from_response(ctx.text)
    if result.memory_entries:
        ctx.memory_entries.extend(result.memory_entries)
    ctx.text = result.cleaned_text
    return ctx


def _handle_delmem_tags(ctx: TagParseContext) -> TagParseContext:
    cleaned, delete_requests = parse_delmem_tags_from_response(ctx.text)
    if delete_requests:
        ctx.delete_memory_requests.extend(delete_requests)
    ctx.text = cleaned
    return ctx


def parse_ai_response_tags(text: str) -> TagParseContext:
    ctx = TagParseContext(
        text=text,
        image_keywords=[],
        ban_requests=[],
        mention_user_ids=[],
        memory_entries=[],
        delete_memory_requests=[]
    )

    handlers: tuple[TagHandler, ...] = (
        _handle_memory_tags,
        _handle_delmem_tags,
        _handle_image_tags,
        _handle_ban_tags,
        _handle_mention_tags,
    )

    for handler in handlers:
        ctx = handler(ctx)

    ctx.text = strip_tag_from_response(ctx.text).strip()
    logger.info(f'[parse_ai_response_tags] After strip all tags: {repr(ctx.text)}')
    return ctx


@dataclass(frozen=True)
class MemeMessageSpec:
    reply: Optional[MessageSegment]
    text: str
    image_keywords: list[str]
    mention_user_ids: list[str]
    dedupe_images: bool = True
    dedupe_mentions: bool = True


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def normalize_reply(reply_message: MessageSegment | str | None) -> Optional[MessageSegment]:
    if reply_message is None:
        return None
    if isinstance(reply_message, MessageSegment):
        return reply_message
    return None


def build_message_from_spec(spec: MemeMessageSpec) -> Message:
    message_parts: list[MessageSegment] = []

    if spec.reply is not None:
        message_parts.append(spec.reply)

    keywords = [k.strip() for k in spec.image_keywords if k and k.strip()]
    if spec.dedupe_images:
        keywords = _dedupe_keep_order(keywords)

    for keyword in keywords:
        meme = meme_db.get_meme_by_keyword(keyword)
        if not meme:
            logger.warning(f'Meme keyword not found: {keyword}')
            continue

        image_path = getattr(meme, 'image_path', '')
        if not image_path:
            logger.warning(f'Meme image path is empty for keyword: {keyword}')
            continue

        message_parts.append(MessageSegment.image(f'file:///{image_path}'))
        logger.info(f'Using meme: {keyword} -> {image_path}')

    mention_user_ids = [uid.strip() for uid in spec.mention_user_ids if uid and uid.strip()]
    mention_user_ids = [uid for uid in mention_user_ids if uid.isdigit()]
    if spec.dedupe_mentions:
        mention_user_ids = _dedupe_keep_order(mention_user_ids)

    for user_id in mention_user_ids:
        message_parts.append(MessageSegment.at(user_id))
        message_parts.append(MessageSegment.text(' '))

    text = spec.text.strip('。').strip()
    if text:
        message_parts.append(MessageSegment.text(text))

    return construct_message_chain(*message_parts)


def build_meme_message(
        reply_message: MessageSegment | str | None,
        ai_text: str,
        image_keywords: list[str],
        mention_user_ids: list[str],
) -> Message:
    spec = MemeMessageSpec(
        reply=normalize_reply(reply_message),
        text=ai_text,
        image_keywords=image_keywords,
        mention_user_ids=mention_user_ids,
    )
    return build_message_from_spec(spec)


def compute_banned_until_ts(duration_seconds: int, *, banned_until_ts: Optional[int]) -> int:
    if banned_until_ts is not None and banned_until_ts > 0:
        return int(banned_until_ts)
    return int(time()) + int(duration_seconds)
