import sqlite3
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

DB_PATH = Path(__file__).parent.parent / 'data' / 'db' / 'meme_database.db'
AUTO_APPROVE_CONFIDENCE_THRESHOLD = 0.8


@dataclass
class MemoryEntry:
    memory_id: int
    group_id: str
    user_id: str
    nickname: str
    content: str
    confidence: float
    is_approved: bool
    is_global: bool
    created_at: str
    updated_at: str


class MemoryDatabase:
    def __init__(self) -> None:
        self.db_path = DB_PATH
        self.auto_approve_threshold = AUTO_APPROVE_CONFIDENCE_THRESHOLD
        self._init_db()

    def set_auto_approve_threshold(self, threshold: float) -> None:
        self.auto_approve_threshold = max(0.0, min(1.0, threshold))

    @staticmethod
    def _is_generic_question(content: str) -> bool:
        content_lower = content.lower().strip()

        generic_patterns = [
            '什么时间',
            '几点',
            '现在时间',
            '今天几号',
            '什么日期',
            '星期几',
            '哪天',
            '多少号',
            '几月',
            '哪年',
            '今天是',
            '现在是',
        ]

        if len(content_lower) < 4:
            return False

        if any(pattern in content_lower for pattern in generic_patterns):
            return True

        if content_lower.count('?') > 0 or content_lower.count('？') > 0:
            time_date_keywords = ['时间', '日期', '几点', '几号', '星期', 'time', 'date', 'day', 'hour']
            if any(keyword in content_lower for keyword in time_date_keywords):
                return True

        return False

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    CREATE TABLE IF NOT EXISTS memories
                    (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id    TEXT NOT NULL,
                        user_id     TEXT NOT NULL,
                        nickname    TEXT NOT NULL DEFAULT '',
                        content     TEXT NOT NULL,
                        confidence  REAL NOT NULL,
                        is_approved BOOLEAN       DEFAULT 0,
                        is_global   BOOLEAN       DEFAULT 0,
                        created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
                        updated_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (group_id, user_id, content)
                    )
                    '''
                )

                cursor.execute("PRAGMA table_info(memories)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'is_global' not in columns:
                    cursor.execute('ALTER TABLE memories ADD COLUMN is_global BOOLEAN DEFAULT 0')
                    logger.info('Added is_global column to memories table')

                if 'nickname' not in columns:
                    cursor.execute("ALTER TABLE memories ADD COLUMN nickname TEXT NOT NULL DEFAULT ''")
                    logger.info('Added nickname column to memories table')

                cursor.execute(
                    '''
                    CREATE INDEX IF NOT EXISTS idx_memories_group_user_approved
                        ON memories (group_id, user_id, is_approved, created_at)
                    '''
                )
                cursor.execute(
                    '''
                    CREATE INDEX IF NOT EXISTS idx_memories_global
                        ON memories (is_global, is_approved, created_at)
                    '''
                )
                conn.commit()
                logger.info('Memory database initialized successfully')
        except BaseException as err:
            logger.error(f'Failed to initialize memory database: {err}')

    def _execute_query_and_fetch_memories(
            self,
            query: str,
            params: tuple,
            error_context: str
    ) -> list[MemoryEntry]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [
                    MemoryEntry(
                        memory_id=row['id'],
                        group_id=row['group_id'],
                        user_id=row['user_id'],
                        nickname=row['nickname'] if 'nickname' in row.keys() else '',
                        content=row['content'],
                        confidence=float(row['confidence']),
                        is_approved=bool(row['is_approved']),
                        is_global=bool(row['is_global']) if 'is_global' in row.keys() else False,
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    for row in rows
                ]
        except BaseException as err:
            logger.error(f'{error_context}: {err}')
            return []

    def add_memory(
            self,
            group_id: str,
            user_id: str,
            content: str,
            confidence: float,
            *,
            is_approved: bool,
            is_global: bool = False,
            nickname: str = '',
    ) -> bool:
        try:
            if not group_id or not user_id or not content:
                return False

            if self._is_generic_question(content):
                logger.info(f'Skipped generic question memory: "{content}"')
                return False

            should_auto_approve = confidence >= self.auto_approve_threshold
            final_approval = is_approved or should_auto_approve

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if memory already exists
                cursor.execute(
                    'SELECT nickname FROM memories WHERE group_id = ? AND user_id = ? AND content = ?',
                    (group_id, user_id, content)
                )
                existing = cursor.fetchone()

                # If memory exists and new nickname is empty, preserve the existing nickname
                final_nickname = nickname
                if existing and not nickname:
                    existing_nickname = existing['nickname'] if 'nickname' in existing.keys() else ''
                    if existing_nickname:
                        final_nickname = existing_nickname
                        logger.debug(f'Preserving existing nickname: {final_nickname}')

                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO memories
                    (group_id, user_id, nickname, content, confidence, is_approved, is_global, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''',
                    (group_id, user_id, final_nickname, content, confidence, int(final_approval), int(is_global))
                )
                conn.commit()
                approval_status = 'auto-approved' if should_auto_approve else (
                    'approved' if final_approval else 'pending')
                global_status = ', global' if is_global else ''
                logger.success(
                    f'Added/updated memory'
                    f' [{approval_status}{global_status}]:'
                    f' group_id={group_id}, user_id={user_id}, nickname={final_nickname}, confidence={confidence:.2f}'
                )
                return True
        except BaseException as err:
            logger.error(f'Failed to add memory: {err}')
            return False

    def get_memories(
            self,
            group_id: str,
            user_id: str,
            *,
            limit: int = 12,
            only_approved: bool = True,
    ) -> list[MemoryEntry]:
        query = (
            'SELECT id, group_id, user_id, nickname, content, confidence,'
            ' is_approved, is_global, created_at, updated_at '
            'FROM memories WHERE group_id = ? AND user_id = ?'
        )
        params: list[object] = [group_id, user_id]
        if only_approved:
            query += ' AND is_approved = 1'
        query += ' ORDER BY datetime(created_at) DESC LIMIT ?'
        params.append(int(limit))

        return self._execute_query_and_fetch_memories(
            query,
            tuple(params),
            'Failed to get memories'
        )

    def get_memories_by_user(
            self,
            user_id: str,
            *,
            limit: int = 12,
            only_approved: bool = True,
    ) -> list[MemoryEntry]:
        query = (
            'SELECT id, group_id, user_id, nickname,'
            ' content, confidence, is_approved, is_global, created_at, updated_at '
            'FROM memories WHERE (user_id = ? OR is_global = 1)'
        )
        params: list[object] = [str(user_id)]
        if only_approved:
            query += ' AND is_approved = 1'
        query += ' ORDER BY datetime(created_at) DESC LIMIT ?'
        params.append(int(limit))

        return self._execute_query_and_fetch_memories(
            query,
            tuple(params),
            'Failed to get memories by user'
        )

    def get_memories_by_group(
            self,
            group_id: str,
            *,
            limit: int = 12,
            only_approved: bool = True,
    ) -> list[MemoryEntry]:
        query = (
            'SELECT id, group_id, user_id, nickname,'
            ' content, confidence, is_approved, is_global, created_at, updated_at '
            'FROM memories WHERE group_id = ?'
        )
        params: list[object] = [str(group_id)]
        if only_approved:
            query += ' AND is_approved = 1'
        query += ' ORDER BY datetime(created_at) DESC LIMIT ?'
        params.append(int(limit))

        return self._execute_query_and_fetch_memories(
            query,
            tuple(params),
            'Failed to get memories by group'
        )

    def get_pending_memories(self, *, limit: int = 20) -> list[MemoryEntry]:
        query = (
            'SELECT id, group_id, user_id, nickname,'
            ' content, confidence, is_approved, is_global, created_at, updated_at '
            'FROM memories WHERE is_approved = 0 '
            'ORDER BY datetime(created_at) DESC LIMIT ?'
        )

        return self._execute_query_and_fetch_memories(
            query,
            (int(limit),),
            'Failed to get pending memories'
        )

    def get_global_memories(self, *, limit: int = 20, only_approved: bool = True) -> list[MemoryEntry]:
        query = (
            'SELECT id, group_id, user_id, nickname,'
            ' content, confidence, is_approved, is_global, created_at, updated_at '
            'FROM memories WHERE is_global = 1'
        )
        params: list[object] = []
        if only_approved:
            query += ' AND is_approved = 1'
        query += ' ORDER BY datetime(created_at) DESC LIMIT ?'
        params.append(int(limit))

        return self._execute_query_and_fetch_memories(
            query,
            tuple(params),
            'Failed to get global memories'
        )

    def approve_memory(self, memory_id: int, *, approved: bool) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE memories SET is_approved = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (int(bool(approved)), int(memory_id))
                )
                conn.commit()
                return cursor.rowcount > 0
        except BaseException as err:
            logger.error(f'Failed to update memory approval: {err}')
            return False

    def delete_memory(self, memory_id: int) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM memories WHERE id = ?', (int(memory_id),))
                conn.commit()
                if cursor.rowcount > 0:
                    logger.success(f'Deleted memory with id={memory_id}')
                    return True
                logger.warning(f'No memory found with id={memory_id}')
                return False
        except BaseException as err:
            logger.error(f'Failed to delete memory: {err}')
            return False

    def get_memory_by_id(self, memory_id: int) -> MemoryEntry | None:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, group_id, user_id, nickname, content, confidence,'
                    ' is_approved, is_global, created_at, updated_at '
                    'FROM memories WHERE id = ?',
                    (int(memory_id),)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return MemoryEntry(
                    memory_id=row['id'],
                    group_id=row['group_id'],
                    user_id=row['user_id'],
                    nickname=row['nickname'] if 'nickname' in row.keys() else '',
                    content=row['content'],
                    confidence=float(row['confidence']),
                    is_approved=bool(row['is_approved']),
                    is_global=bool(row['is_global']) if 'is_global' in row.keys() else False,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
        except BaseException as err:
            logger.error(f'Failed to get memory by id: {err}')
            return None

    def get_group_summary_memory(self, group_id: str, group_user_id: str = 'GROUP_MEMORY') -> MemoryEntry | None:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, group_id, user_id, nickname, content, confidence,'
                    ' is_approved, is_global, created_at, updated_at '
                    'FROM memories WHERE group_id = ? AND user_id = ? '
                    'ORDER BY datetime(updated_at) DESC LIMIT 1',
                    (str(group_id), str(group_user_id))
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return MemoryEntry(
                    memory_id=row['id'],
                    group_id=row['group_id'],
                    user_id=row['user_id'],
                    nickname=row['nickname'] if 'nickname' in row.keys() else '',
                    content=row['content'],
                    confidence=float(row['confidence']),
                    is_approved=bool(row['is_approved']),
                    is_global=bool(row['is_global']) if 'is_global' in row.keys() else False,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
        except BaseException as err:
            logger.error(f'Failed to get group summary memory: {err}')
            return None

    def upsert_group_summary_memory(
            self,
            group_id: str,
            content: str,
            confidence: float,
            group_user_id: str = 'GROUP_MEMORY'
    ) -> bool:
        try:
            if not group_id or not content:
                return False

            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    'DELETE FROM memories WHERE group_id = ? AND user_id = ?',
                    (str(group_id), str(group_user_id))
                )

                cursor.execute(
                    '''
                    INSERT INTO memories
                    (group_id, user_id, nickname, content, confidence, is_approved, is_global, updated_at)
                    VALUES (?, ?, '', ?, ?, 1, 0, CURRENT_TIMESTAMP)
                    ''',
                    (str(group_id), str(group_user_id), content, float(confidence))
                )
                conn.commit()
                logger.success(
                    f'Upserted group summary memory for group_id={group_id}, confidence={confidence:.2f}'
                )
                return True
        except BaseException as err:
            logger.error(f'Failed to upsert group summary memory: {err}')
            return False


memory_db = MemoryDatabase()
