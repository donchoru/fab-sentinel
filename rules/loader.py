"""규칙 YAML 로더 — rules.yaml ↔ DB 동기화.

rules.yaml이 규칙의 원본(source of truth).
- 서버 시작 시: YAML → DB 동기화
- UI에서 규칙 변경 시: DB 변경 → YAML 파일 갱신
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

RULES_YAML = Path(__file__).resolve().parent.parent / "rules.yaml"

# YAML ↔ DB 필드 매핑
_YAML_TO_DB = {"name": "rule_name", "query": "query_template", "tool": "tool_name"}
_DB_TO_YAML = {v: k for k, v in _YAML_TO_DB.items()}


def _yaml_to_db(rule: dict) -> dict:
    """YAML 규칙 → DB 컬럼 형식."""
    db = {}
    for k, v in rule.items():
        col = _YAML_TO_DB.get(k, k)
        if col in ("llm_enabled", "enabled"):
            v = 1 if v else 0
        db[col] = v
    return db


def _db_to_yaml(rule: dict) -> dict:
    """DB row → YAML 형식."""
    skip = {"rule_id", "created_at", "updated_at"}
    out: dict[str, Any] = {}
    for k, v in rule.items():
        if k in skip:
            continue
        key = _DB_TO_YAML.get(k, k)
        if key in ("llm_enabled", "enabled"):
            v = bool(v)
        # float → int (정수인 경우)
        if isinstance(v, float) and v == int(v):
            v = int(v)
        out[key] = v
    # 불필요한 필드 정리
    if not out.get("llm_enabled") and not out.get("llm_prompt"):
        out.pop("llm_prompt", None)
    # sql 소스면 tool 필드 제거, tool 소스면 query 필드 제거
    if out.get("source_type") == "tool":
        out.pop("query", None)
    else:
        out.pop("source_type", None)
        out.pop("tool", None)
        out.pop("tool_args", None)
        out.pop("tool_column", None)
    # None 값 제거
    out = {k: v for k, v in out.items() if v is not None}
    return out


# ── YAML 블록 스타일 Dumper ──

class _BlockDumper(yaml.Dumper):
    """멀티라인 문자열을 | 블록 스타일로 출력."""
    pass


def _str_representer(dumper: yaml.Dumper, data: str):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_BlockDumper.add_representer(str, _str_representer)


# ── YAML 파일 I/O ──

def load_from_yaml(path: Path | str | None = None) -> list[dict]:
    """rules.yaml에서 규칙 목록 로드."""
    p = Path(path) if path else RULES_YAML
    if not p.exists():
        logger.warning("rules.yaml not found: %s", p)
        return []
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rules", [])


def save_to_yaml(rules: list[dict], path: Path | str | None = None) -> None:
    """규칙 목록을 rules.yaml에 저장."""
    p = Path(path) if path else RULES_YAML
    # YAML 헤더 주석
    header = (
        "# FAB 이상감지 규칙 정의\n"
        "# 이 파일이 규칙의 원본입니다. 서버 시작 시 DB에 자동 동기화됩니다.\n"
        "# UI에서 규칙을 추가/수정/삭제하면 이 파일도 자동 갱신됩니다.\n\n"
    )
    with open(p, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.dump(
            {"rules": rules},
            f,
            Dumper=_BlockDumper,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
    logger.info("Saved %d rules to %s", len(rules), p)


# ── SQLite 동기화 (시뮬레이터용) ──

def sync_to_sqlite(conn) -> int:
    """YAML → SQLite DB 동기화. 기존 규칙 전부 교체."""
    yaml_rules = load_from_yaml()
    if not yaml_rules:
        return 0

    conn.execute("DELETE FROM detection_rules")

    count = 0
    for rule in yaml_rules:
        db = _yaml_to_db(rule)
        conn.execute(
            """INSERT INTO detection_rules
               (rule_name, category, subcategory, query_template, check_type,
                source_type, tool_name, tool_args, tool_column,
                threshold_op, warning_value, critical_value,
                eval_interval, llm_enabled, llm_prompt, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                db.get("rule_name"),
                db.get("category"),
                db.get("subcategory"),
                db.get("query_template"),
                db.get("check_type", "threshold"),
                db.get("source_type", "sql"),
                db.get("tool_name"),
                db.get("tool_args"),
                db.get("tool_column"),
                db.get("threshold_op", ">"),
                db.get("warning_value", 0),
                db.get("critical_value", 0),
                db.get("eval_interval", 300),
                db.get("llm_enabled", 0),
                db.get("llm_prompt") or "",
                db.get("enabled", 1),
            ),
        )
        count += 1

    conn.commit()
    logger.info("Synced %d rules from YAML → SQLite", count)
    return count


# ── Oracle DB 동기화 (운영용) ──

async def sync_to_db() -> int:
    """YAML → Oracle DB 동기화. YAML이 원본."""
    from db import queries
    from db.oracle import execute

    yaml_rules = load_from_yaml()
    if not yaml_rules:
        return 0

    db_rules = await execute("SELECT * FROM detection_rules ORDER BY rule_id")
    db_by_name = {r["rule_name"]: r for r in db_rules}
    yaml_names: set[str] = set()

    count = 0
    for rule in yaml_rules:
        db_data = _yaml_to_db(rule)
        name = db_data["rule_name"]
        yaml_names.add(name)

        if name in db_by_name:
            await queries.update_rule(db_by_name[name]["rule_id"], db_data)
        else:
            await queries.create_rule(db_data)
        count += 1

    # YAML에 없는 DB 규칙 삭제
    for name, db_rule in db_by_name.items():
        if name not in yaml_names:
            await queries.delete_rule(db_rule["rule_id"])
            logger.info("Deleted rule not in YAML: %s", name)

    logger.info("Synced %d rules from YAML → DB", count)
    return count


async def sync_db_to_yaml() -> None:
    """DB → YAML 동기화. UI에서 규칙 변경 후 호출."""
    from db.oracle import execute

    db_rules = await execute("SELECT * FROM detection_rules ORDER BY rule_id")
    yaml_rules = [_db_to_yaml(r) for r in db_rules]
    save_to_yaml(yaml_rules)
