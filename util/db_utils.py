import sqlite3
from typing import Any, Optional, Union


def fetch_one_or_default(fetch_one_result: Union[list, tuple], default_value: Any) -> Any:
    return fetch_one_result[0] if fetch_one_result and fetch_one_result[0] else default_value


def execute_db(db_path: str, query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False) -> \
Optional[Any]:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(query, params)
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = cursor
        conn.commit()
        return result
    finally:
        conn.close()
