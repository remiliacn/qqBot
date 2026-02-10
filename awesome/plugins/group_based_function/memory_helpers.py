import re
from dataclasses import dataclass

from loguru import logger

from Services.memory_db import memory_db, MemoryEntry

GROUP_USER_ID = 'GROUP_MEMORY'


@dataclass(frozen=True)
class MemoryWriteResult:
    approved: int
    pending: int


def extract_mentioned_user_ids(message: str) -> list[str]:
    pattern = r'<mention>.*?（(\d+)）</mention>'
    matches = re.findall(pattern, message)
    return [user_id for user_id in matches if user_id and user_id.isdigit()]


def format_memories_for_llm(user_id: str, *, limit: int = 12, group_id: str = '') -> str:
    try:
        memories = memory_db.get_memories_by_user(user_id, limit=limit, only_approved=True)
    except BaseException as err:
        logger.error(f'Failed to load memories for llm: {err}')
        memories = []

    # Also load group memories for the current group
    group_memories = []
    if group_id:
        try:
            group_memories = memory_db.get_memories(
                group_id=group_id,
                user_id=GROUP_USER_ID,
                limit=5,
                only_approved=True
            )
        except BaseException as err:
            logger.error(f'Failed to load group memories for llm: {err}')

    all_memories = list(memories) + list(group_memories)
    if not all_memories:
        return ''

    lines = ['\n\n【记忆】']
    for idx, m in enumerate(all_memories, start=1):
        _parse_memory_entries(idx, lines, m)

    logger.info(f'Retrieved memories: {lines}')
    return '\n'.join(lines)


def _parse_memory_entries(idx: int, lines: list[str], m: MemoryEntry):
    if m.is_global:
        lines.append(f'{idx}. [记忆ID:{m.memory_id}] [通用知识] {m.content}')
    elif m.user_id == GROUP_USER_ID:
        lines.append(f'{idx}. [记忆ID:{m.memory_id}] [群聊回忆·参考] {m.content}')
    elif m.nickname:
        sanitized_nickname = sanitize_user_input(m.nickname)
        lines.append(f'{idx}. [记忆ID:{m.memory_id}] [{sanitized_nickname}（UID：{m.user_id}）] {m.content}')
    else:
        lines.append(f'{idx}. [记忆ID:{m.memory_id}] [UID：{m.user_id}] {m.content}')


def format_memories_for_multiple_users(
        speaker_user_id: str,
        mentioned_user_ids: list[str],
        *,
        limit_per_user: int = 8,
        group_id: str = '',
) -> str:
    all_user_ids = [speaker_user_id] + [uid for uid in mentioned_user_ids if uid != speaker_user_id]

    if not all_user_ids:
        return ''

    all_memories_text = []

    # First, add group memories for this group
    if group_id:
        try:
            group_memories = memory_db.get_memories(
                group_id=group_id,
                user_id=GROUP_USER_ID,
                limit=5,
                only_approved=True
            )
            if group_memories:
                memory_items = [f'  - [记忆ID:{m.memory_id}] {m.content}' for m in group_memories]
                all_memories_text.append('[群聊回忆·参考]:\n' + '\n'.join(memory_items))
        except BaseException as err:
            logger.error(f'Failed to load group memories for group {group_id}: {err}')

    # Then add user-specific memories
    for user_id in all_user_ids:
        try:
            memories = memory_db.get_memories_by_user(user_id, limit=limit_per_user, only_approved=True)
        except BaseException as err:
            logger.error(f'Failed to load memories for user {user_id}: {err}')
            memories = []

        if not memories:
            continue

        first_memory = next((m for m in memories if m.user_id == user_id), None)
        if first_memory and first_memory.nickname:
            sanitized_nickname = sanitize_user_input(first_memory.nickname)
            user_label = f'{sanitized_nickname}（UID：{user_id}）'
        else:
            user_label = f'UID：{user_id}'

        memory_items = []
        for idx, m in enumerate(memories):
            _parse_memory_entries(idx, memory_items, m)

        all_memories_text.append(f'{user_label}:\n' + '\n'.join(memory_items))

    if not all_memories_text:
        return ''

    logger.info(f'Retrieved memories: {all_memories_text}')
    return ('\n\n【记忆】\n' + '\n\n'.join(all_memories_text)
            + '\n请注意不要混淆不同人的记忆。注意甄别发言人和记忆的uid是否对应。')


def persist_memory_tags(
        group_id: str,
        user_id: str,
        memories: list[object],
        *,
        approve_threshold: float = 0.75,
        nickname: str = '',
) -> MemoryWriteResult:
    approved = 0
    pending = 0

    sanitized_nickname = sanitize_user_input(nickname)
    logger.info(f'Persisting memories for group_id={group_id}, user_id={user_id}, nickname={sanitized_nickname}')
    for mem in memories:
        content = str(getattr(mem, 'content', '') or '').strip()
        confidence_raw = getattr(mem, 'confidence', 0.0)
        is_global = bool(getattr(mem, 'is_global', False))

        try:
            confidence = float(confidence_raw)
        except BaseException as err:
            logger.error(f'Failed to parse memory confidence: {err}')
            confidence = 0.0

        if not content:
            continue

        is_approved = confidence >= approve_threshold
        ok = memory_db.add_memory(
            group_id=str(group_id),
            user_id=str(user_id),
            content=content,
            confidence=confidence,
            is_approved=is_approved,
            is_global=is_global,
            nickname=sanitized_nickname,
        )
        if not ok:
            continue

        if is_approved:
            approved += 1
        else:
            pending += 1

    return MemoryWriteResult(approved=approved, pending=pending)


def persist_group_memory_from_summary(group_id: str, summary: str) -> bool:
    if not summary or not summary.strip():
        return False

    summary = summary.strip()

    existing_memory = memory_db.get_group_summary_memory(str(group_id), GROUP_USER_ID)

    if existing_memory and existing_memory.content:
        old_summary = existing_memory.content.strip()
        combined_summary = f"{old_summary}\n{summary}"

        if len(combined_summary) > 400:
            final_summary = summary
            logger.info(f'Combined summary too long, using new summary only for group_id={group_id}')
        else:
            final_summary = combined_summary
            logger.info(f'Combined old and new summary for group_id={group_id}')
    else:
        final_summary = summary
        logger.info(f'No existing group memory, creating new one for group_id={group_id}')

    # Check if the summary contains interesting content
    interesting_indicators = [
        '决定',
        '计划',
        '讨论',
        '共识',
        '约定',
        '活动',
        '事件',
        '庆祝',
        '分享',
        '经验',
        '建议',
        '推荐',
        '喜欢',
        '不喜欢',
        '偏好',
        '习惯',
    ]

    summary_lower = final_summary.lower()
    has_interesting_content = any(indicator in summary_lower for indicator in interesting_indicators)

    if has_interesting_content:
        confidence = 0.85
    else:
        boring_patterns = [
            '时间',
            '几点',
            '日期',
            '星期',
            '天气',
            '今天',
            '明天',
            '昨天',
            '现在',
            '刚才',
            '一会',
            '等下',
            '稍后',
        ]

        if any(pattern in summary_lower for pattern in boring_patterns):
            if len(final_summary) < 20:
                logger.info(f'Skipped boring group memory: {final_summary}')
                return False

        if len(final_summary) < 30:
            logger.info(f'Skipped uninteresting group memory: {final_summary}')
            return False

        confidence = 0.75

    try:
        # Use upsert to ensure only one group memory exists
        ok = memory_db.upsert_group_summary_memory(
            group_id=str(group_id),
            content=final_summary,
            confidence=confidence,
            group_user_id=GROUP_USER_ID,
        )
        if ok:
            logger.success(f'Upserted group memory for group_id={group_id}: {final_summary}')
        return ok
    except BaseException as err:
        logger.error(f'Failed to persist group memory: {err}')
        return False


def sanitize_user_input(text: str) -> str:
    if not text:
        return text
    sanitized = text.replace('<', '＜').replace('>', '＞').replace('[', '［').replace(']', '］')
    return sanitized
