import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger

DB_PATH = Path(__file__).parent.parent / 'data' / 'db' / 'meme_database.db'


@dataclass
class MemeEntry:
    meme_id: int
    keyword: str
    image_path: str
    description: str


class MemeDatabase:
    def __init__(self) -> None:
        self.db_path = DB_PATH
        self._init_db()

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
                    CREATE TABLE IF NOT EXISTS memes
                    (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword     TEXT UNIQUE NOT NULL,
                        image_path  TEXT        NOT NULL,
                        description TEXT        NOT NULL,
                        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    '''
                )
                conn.commit()
                logger.info('Meme database initialized successfully')
        except BaseException as err:
            logger.error(f'Failed to initialize meme database: {err}')

    def add_meme(self, keyword: str, image_path: str, description: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT OR
                    REPLACE INTO memes (keyword, image_path, description, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ''',
                    (keyword.lower().strip(), image_path, description)
                )
                conn.commit()
                logger.success(f'Added/updated meme: keyword={keyword}, path={image_path}')
                return True
        except BaseException as err:
            logger.error(f'Failed to add meme: {err}')
            return False

    def get_meme_by_keyword(self, keyword: str) -> Optional[MemeEntry]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, keyword, image_path, description FROM memes WHERE keyword = ?',
                    (keyword.lower().strip(),)
                )
                row = cursor.fetchone()
                if row:
                    return MemeEntry(
                        meme_id=row['id'],
                        keyword=row['keyword'],
                        image_path=row['image_path'],
                        description=row['description']
                    )
                return None
        except BaseException as err:
            logger.error(f'Failed to get meme: {err}')
            return None

    def get_all_memes(self) -> list[MemeEntry]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, keyword, image_path, description FROM memes ORDER BY keyword')
                rows = cursor.fetchall()
                return [
                    MemeEntry(
                        meme_id=row['id'],
                        keyword=row['keyword'],
                        image_path=row['image_path'],
                        description=row['description']
                    )
                    for row in rows
                ]
        except BaseException as err:
            logger.error(f'Failed to get all memes: {err}')
            return []

    def delete_meme(self, keyword: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM memes WHERE keyword = ?', (keyword.lower().strip(),))
                conn.commit()
                if cursor.rowcount > 0:
                    logger.success(f'Deleted meme: keyword={keyword}')
                    return True
                return False
        except BaseException as err:
            logger.error(f'Failed to delete meme: {err}')
            return False


meme_db = MemeDatabase()
