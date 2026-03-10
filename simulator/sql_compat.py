"""Oracle → SQLite SQL 변환기.

기존 agent tools 쿼리가 Oracle SQL로 작성되어 있으므로
SQLite에서 실행하기 전에 변환.
"""

from __future__ import annotations

import re


def oracle_to_sqlite(sql: str) -> str:
    """Oracle SQL → SQLite 호환 SQL 변환."""
    s = sql

    # SYSTIMESTAMP / SYSDATE → datetime('now', 'localtime')
    s = re.sub(r"\bSYSTIMESTAMP\b", "datetime('now', 'localtime')", s)
    s = re.sub(r"\bSYSDATE\b", "datetime('now', 'localtime')", s)

    # SYSTIMESTAMP - INTERVAL '1' HOUR → datetime('now', 'localtime', '-1 hour')
    s = re.sub(
        r"datetime\('now', 'localtime'\)\s*-\s*INTERVAL\s+'(\d+)'\s+HOUR",
        r"datetime('now', 'localtime', '-\1 hour')",
        s,
    )
    s = re.sub(
        r"datetime\('now', 'localtime'\)\s*-\s*INTERVAL\s+'(\d+)'\s+MINUTE",
        r"datetime('now', 'localtime', '-\1 minute')",
        s,
    )

    # SYSTIMESTAMP - NUMTODSINTERVAL(:var, 'HOUR')
    s = re.sub(
        r"datetime\('now', 'localtime'\)\s*-\s*NUMTODSINTERVAL\(:(\w+),\s*'HOUR'\)",
        r"datetime('now', 'localtime', '-' || :\1 || ' hour')",
        s,
    )
    s = re.sub(
        r"datetime\('now', 'localtime'\)\s*-\s*NUMTODSINTERVAL\(:(\w+),\s*'MINUTE'\)",
        r"datetime('now', 'localtime', '-' || :\1 || ' minute')",
        s,
    )

    # NVL(x, y) → COALESCE(x, y)
    s = re.sub(r"\bNVL\(", "COALESCE(", s)

    # NULLIF stays the same (SQLite supports it)

    # TRUNC(x, 'HH24') → strftime('%Y-%m-%d %H:00:00', x)
    s = re.sub(r"TRUNC\((\w+),\s*'HH24'\)", r"strftime('%Y-%m-%d %H:00:00', \1)", s)

    # ROUND stays the same

    # OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY → LIMIT :lim OFFSET :off
    # (반드시 FETCH-only 패턴보다 먼저 실행해야 함)
    s = re.sub(
        r"OFFSET\s+:(\w+)\s+ROWS\s+FETCH\s+NEXT\s+:(\w+)\s+ROWS\s+ONLY",
        r"LIMIT :\2 OFFSET :\1",
        s,
    )

    # FETCH NEXT :lim ROWS ONLY → LIMIT :lim (바인드 변수)
    s = re.sub(r"FETCH\s+NEXT\s+:(\w+)\s+ROWS\s+ONLY", r"LIMIT :\1", s)

    # FETCH NEXT <number> ROWS ONLY → LIMIT <number> (리터럴)
    s = re.sub(r"FETCH\s+NEXT\s+(\d+)\s+ROWS\s+ONLY", r"LIMIT \1", s)

    # (SYSDATE - col) * 24 → (julianday('now', 'localtime') - julianday(col)) * 24
    s = re.sub(
        r"\(datetime\('now', 'localtime'\)\s*-\s*(\w+)\)\s*\*\s*24",
        r"(julianday('now', 'localtime') - julianday(\1)) * 24",
        s,
    )

    # NUMBER GENERATED ALWAYS AS IDENTITY → INTEGER PRIMARY KEY AUTOINCREMENT
    s = re.sub(
        r"NUMBER\s+GENERATED\s+ALWAYS\s+AS\s+IDENTITY\s+PRIMARY\s+KEY",
        "INTEGER PRIMARY KEY AUTOINCREMENT",
        s,
    )

    # FROM DUAL → (remove)
    s = re.sub(r"\s+FROM\s+DUAL\b", "", s)

    # CHR(10) → char(10)
    s = re.sub(r"\bCHR\(", "char(", s)

    # Oracle bind :var → SQLite :var (same, but named params)
    # Already compatible

    return s
