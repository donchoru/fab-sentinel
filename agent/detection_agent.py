"""이상감지 에이전트 — 이상 감지 후 DB 저장."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from agent.agent_loop import run_agent_loop
from agent.prompts import DETECTION_SYSTEM
from config import settings
from db import queries

logger = logging.getLogger(__name__)


async def analyze_and_save(
    rule: dict[str, Any],
    measured_value: float,
    query_result: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """LLM으로 이상 분석 후 DB 저장."""
    user_msg = await _build_user_message(rule, measured_value, query_result)

    result = await run_agent_loop(
        system_prompt=DETECTION_SYSTEM,
        user_message=user_msg,
        max_rounds=3,
    )

    if result.get("parse_error"):
        logger.warning("Detection LLM parse error for rule=%s", rule["rule_name"])
        return None

    if not result.get("is_anomaly", False):
        logger.info("Rule %s: no anomaly (confidence=%.2f)", rule["rule_name"], result.get("confidence", 0))
        return None

    severity = result.get("severity", "warning")
    threshold_value = rule.get("critical_value") if severity == "critical" else rule.get("warning_value")

    anomaly_data = {
        "rule_id": rule["rule_id"],
        "category": rule["category"],
        "severity": severity,
        "title": result.get("title", rule["rule_name"]),
        "description": result.get("analysis", ""),
        "measured_value": measured_value,
        "threshold_value": threshold_value,
        "affected_entity": result.get("affected_entity", ""),
        "rca_status": "pending",
    }

    anomaly_id = await queries.insert_anomaly(anomaly_data)
    logger.info("Anomaly created: id=%d rule=%s severity=%s", anomaly_id, rule["rule_name"], severity)

    return {**anomaly_data, "anomaly_id": anomaly_id}


async def analyze_without_llm(
    rule: dict[str, Any],
    measured_value: float,
    severity: str,
) -> dict[str, Any]:
    """LLM 없이 임계치 기반 이상 생성."""
    title = f"[{rule['category'].upper()}] {rule['rule_name']} - {severity}"
    threshold_value = rule.get("critical_value") if severity == "critical" else rule.get("warning_value")
    op = rule.get("threshold_op", ">")

    anomaly_data = {
        "rule_id": rule["rule_id"],
        "category": rule["category"],
        "severity": severity,
        "title": title,
        "description": f"측정값 {measured_value} {op} 임계치 {threshold_value}",
        "measured_value": measured_value,
        "threshold_value": threshold_value,
        "affected_entity": "",
        "rca_status": "pending",
    }

    anomaly_id = await queries.insert_anomaly(anomaly_data)
    logger.info("Anomaly (no-llm) created: id=%d rule=%s", anomaly_id, rule["rule_name"])

    return {**anomaly_data, "anomaly_id": anomaly_id}


async def _build_user_message(
    rule: dict[str, Any],
    measured_value: float,
    query_result: list[dict[str, Any]],
) -> str:
    # RAG 전문지식 검색 (lazy import — pymilvus 없어도 동작)
    rag_context = ""
    if settings.rag.enabled:
        try:
            from rag.retriever import retrieve_context, build_search_query
            search_query = build_search_query(rule, f"측정값 {measured_value}")
            rag_context = await retrieve_context(
                query=search_query,
                category=rule.get("category"),
                top_k=settings.rag.top_k,
                min_score=settings.rag.min_score,
            )
        except Exception:
            logger.warning("RAG retrieval failed for rule=%s, proceeding without", rule["rule_name"])

    return f"""## 규칙 위반 감지

**규칙**: {rule['rule_name']}
**카테고리**: {rule['category']} / {rule.get('subcategory', '')}
**검사 유형**: {rule['check_type']}
**측정값**: {measured_value}
**경고 임계치**: {rule.get('warning_value', 'N/A')}
**위험 임계치**: {rule.get('critical_value', 'N/A')}

### 쿼리 결과 (원본 데이터)
```json
{json.dumps(query_result[:20], default=str, ensure_ascii=False, indent=2)}
```

{rule.get('llm_prompt', '')}

{rag_context}

위 데이터를 분석하여 실제 이상 여부를 판단하세요.
전문지식이 있다면 참고하여 더 정확한 판단을 내리세요.
필요시 도구를 사용하여 추가 데이터를 조회하세요.
"""
