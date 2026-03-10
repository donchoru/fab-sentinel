"""SQLite backend — Oracle DB를 대체하여 시뮬레이터에서 사용.

db.oracle 모듈의 함수들을 monkey-patch하여
기존 tools/queries 코드 수정 없이 SQLite로 동작.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from simulator.sql_compat import oracle_to_sqlite

logger = logging.getLogger(__name__)

_db_path: str = ""
_conn: sqlite3.Connection | None = None


def init_sqlite(db_path: str = "simulator.db") -> None:
    """SQLite DB 초기화 + db.oracle 모듈 monkey-patch."""
    global _db_path, _conn
    _db_path = db_path
    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA foreign_keys=ON")

    # db.oracle 함수들을 SQLite 버전으로 교체
    import db.oracle as oracle_mod
    oracle_mod.execute = _execute
    oracle_mod.execute_dml = _execute_dml
    oracle_mod.execute_returning = _execute_returning
    oracle_mod.init_pool = _noop_async
    oracle_mod.close_pool = _noop_async

    logger.info("SQLite backend initialized: %s", db_path)


async def _noop_async() -> None:
    pass


async def _execute(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """SELECT 쿼리 실행."""
    translated = oracle_to_sqlite(sql)
    try:
        cursor = _conn.execute(translated, params or {})
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        logger.error("SQLite query failed:\nOriginal: %s\nTranslated: %s\nParams: %s", sql, translated, params)
        raise


async def _execute_dml(sql: str, params: dict[str, Any] | None = None) -> int:
    """INSERT/UPDATE/DELETE 실행."""
    translated = oracle_to_sqlite(sql)
    try:
        cursor = _conn.execute(translated, params or {})
        _conn.commit()
        return cursor.rowcount
    except Exception:
        logger.error("SQLite DML failed:\nOriginal: %s\nTranslated: %s", sql, translated)
        raise


async def _execute_returning(sql: str, params: dict[str, Any] | None = None, returning_col: str = "rule_id") -> Any:
    """INSERT ... RETURNING → SQLite lastrowid."""
    # RETURNING 절 제거
    translated = oracle_to_sqlite(sql)
    translated = translated.split("RETURNING")[0].strip()
    # :out_id 파라미터 제거
    p = dict(params or {})
    p.pop("out_id", None)
    try:
        cursor = _conn.execute(translated, p)
        _conn.commit()
        return cursor.lastrowid
    except Exception:
        logger.error("SQLite INSERT failed:\nOriginal: %s\nTranslated: %s", sql, translated)
        raise


def get_conn() -> sqlite3.Connection:
    """직접 커넥션 접근 (시더/시나리오용)."""
    if _conn is None:
        raise RuntimeError("SQLite not initialized")
    return _conn
