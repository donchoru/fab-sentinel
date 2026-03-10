"""룰 평가 엔진 — SQL 또는 도구(Tool) 실행 + 임계치 비교."""

from __future__ import annotations

import json
import logging
import operator
from typing import Any

from db.oracle import execute

logger = logging.getLogger(__name__)

_OPS = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}


async def evaluate_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """규칙을 평가하고 결과 반환.

    Returns:
        {
            "violated": bool,
            "severity": "warning" | "critical" | None,
            "measured_value": float | None,
            "rows": list[dict],
        }
    """
    check_type = rule.get("check_type", "threshold")

    if check_type == "threshold":
        return await _eval_threshold(rule)
    elif check_type == "delta":
        return await _eval_delta(rule)
    elif check_type == "absence":
        return await _eval_absence(rule)
    elif check_type == "llm":
        return await _eval_llm_delegate(rule)
    else:
        logger.warning("Unknown check_type: %s", check_type)
        return {"violated": False, "severity": None, "measured_value": None, "rows": []}


async def _eval_threshold(rule: dict[str, Any]) -> dict[str, Any]:
    """임계치 비교: 데이터의 첫 번째 값 vs 임계치."""
    rows = await _get_rule_data(rule)
    if not rows:
        return {"violated": False, "severity": None, "measured_value": None, "rows": []}

    measured = _extract_value(rule, rows)
    if measured is None:
        return {"violated": False, "severity": None, "measured_value": None, "rows": rows}

    op_fn = _OPS.get(rule.get("threshold_op", ">"), operator.gt)
    critical_val = rule.get("critical_value")
    warning_val = rule.get("warning_value")

    severity = None
    if critical_val is not None and op_fn(measured, critical_val):
        severity = "critical"
    elif warning_val is not None and op_fn(measured, warning_val):
        severity = "warning"

    return {
        "violated": severity is not None,
        "severity": severity,
        "measured_value": measured,
        "rows": rows,
    }


async def _eval_delta(rule: dict[str, Any]) -> dict[str, Any]:
    """변화율 비교: 절대값으로 비교."""
    rows = await _get_rule_data(rule)
    if not rows:
        return {"violated": False, "severity": None, "measured_value": None, "rows": []}

    measured = _extract_value(rule, rows)
    if measured is None:
        return {"violated": False, "severity": None, "measured_value": None, "rows": rows}

    op_fn = _OPS.get(rule.get("threshold_op", ">"), operator.gt)
    critical_val = rule.get("critical_value")
    warning_val = rule.get("warning_value")

    severity = None
    if critical_val is not None and op_fn(abs(measured), critical_val):
        severity = "critical"
    elif warning_val is not None and op_fn(abs(measured), warning_val):
        severity = "warning"

    return {
        "violated": severity is not None,
        "severity": severity,
        "measured_value": measured,
        "rows": rows,
    }


async def _eval_absence(rule: dict[str, Any]) -> dict[str, Any]:
    """데이터 부재 검사: 결과가 비어있으면 이상."""
    rows = await _get_rule_data(rule)
    violated = len(rows) == 0

    return {
        "violated": violated,
        "severity": "warning" if violated else None,
        "measured_value": 0 if violated else len(rows),
        "rows": rows,
    }


async def _eval_llm_delegate(rule: dict[str, Any]) -> dict[str, Any]:
    """LLM에게 판단 위임: 데이터만 가져오고 violated=True로 표시.
    실제 판단은 detection_agent가 LLM 분석으로 수행."""
    rows = await _get_rule_data(rule)
    measured = _extract_value(rule, rows) if rows else None

    return {
        "violated": True,  # LLM이 최종 판단
        "severity": "warning",
        "measured_value": measured,
        "rows": rows,
    }


# ── 데이터 소스 분기 ──

async def _get_rule_data(rule: dict[str, Any]) -> list[dict[str, Any]]:
    """규칙의 source_type에 따라 SQL 또는 도구로 데이터 조회."""
    source_type = rule.get("source_type", "sql")

    if source_type == "tool":
        return await _execute_tool(rule)
    else:
        return await _execute_sql(rule)


async def _execute_sql(rule: dict[str, Any]) -> list[dict[str, Any]]:
    """SQL 쿼리 실행."""
    sql = rule.get("query_template", "")
    if not sql:
        return []
    try:
        return await execute(sql)
    except Exception:
        logger.exception("Rule query failed: rule_id=%s", rule.get("rule_id"))
        return []


async def _execute_tool(rule: dict[str, Any]) -> list[dict[str, Any]]:
    """등록된 도구 호출 → 결과 rows 반환."""
    from agent.tool_registry import registry

    tool_name = rule.get("tool_name", "")
    if not tool_name:
        logger.warning("Rule has source_type=tool but no tool_name: %s", rule.get("rule_id"))
        return []

    # 도구 파라미터 파싱
    args_str = rule.get("tool_args") or "{}"
    try:
        args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
    except (json.JSONDecodeError, TypeError):
        args = {}

    try:
        result_str = await registry.dispatch(tool_name, args)
        result = json.loads(result_str)
    except Exception:
        logger.exception("Tool %s failed: rule_id=%s", tool_name, rule.get("rule_id"))
        return []

    if "error" in result:
        logger.warning("Tool %s error: %s", tool_name, result["error"])
        return []

    # 도구 결과에서 rows 추출 (첫 번째 값이 list인 항목)
    for v in result.values():
        if isinstance(v, list):
            return v

    return []


# ── 값 추출 ──

def _extract_value(rule: dict[str, Any], rows: list[dict[str, Any]]) -> float | None:
    """규칙에 따라 측정값 추출.

    - tool_column="_count" → 행 수
    - tool_column이 지정됨 → 첫 행에서 해당 컬럼
    - 미지정 → 첫 행의 첫 숫자 컬럼
    """
    col = rule.get("tool_column", "")

    if col == "_count":
        return float(len(rows))

    if not rows:
        return None

    if col and col in rows[0]:
        v = rows[0][col]
        if isinstance(v, (int, float)):
            return float(v)
        return None

    # 폴백: 첫 행의 첫 숫자 컬럼
    for v in rows[0].values():
        if isinstance(v, (int, float)):
            return float(v)
    return None
