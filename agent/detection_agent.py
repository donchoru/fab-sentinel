"""이상감지 에이전트 — 이상 감지 후 토픽 발행.

발행하는 메시지에는 이상의 전체 맥락이 포함됨:
누가 어떤 규칙으로 무엇을 감지했고, 측정값/임계치는 얼마이며,
어떤 설비/라인이 영향을 받는지 — 메시지만 보면 전부 파악 가능.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from agent.agent_loop import run_agent_loop
from agent.prompts import DETECTION_SYSTEM
from bus.topic import bus, TOPIC_ANOMALY_DETECTED
from db import queries

logger = logging.getLogger(__name__)


async def analyze_and_publish(
    rule: dict[str, Any],
    measured_value: float,
    query_result: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """LLM으로 이상 분석 후 토픽에 발행."""
    user_msg = _build_user_message(rule, measured_value, query_result)

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
    }

    anomaly_id = await queries.insert_anomaly(anomaly_data)
    detected_at = datetime.now().isoformat()
    logger.info("Anomaly created: id=%d rule=%s severity=%s", anomaly_id, rule["rule_name"], severity)

    # 자기완결형 메시지 발행
    await bus.publish(
        topic=TOPIC_ANOMALY_DETECTED,
        payload=_build_detected_message(
            anomaly_id=anomaly_id,
            detected_at=detected_at,
            rule=rule,
            severity=severity,
            title=result.get("title", rule["rule_name"]),
            analysis=result.get("analysis", ""),
            measured_value=measured_value,
            threshold_value=threshold_value,
            affected_entity=result.get("affected_entity", ""),
            confidence=result.get("confidence", 0),
            evidence_summary=_summarize_evidence(query_result),
        ),
        source="detection_agent",
    )

    return {**anomaly_data, "anomaly_id": anomaly_id}


async def analyze_without_llm(
    rule: dict[str, Any],
    measured_value: float,
    severity: str,
) -> dict[str, Any]:
    """LLM 없이 임계치 기반 이상 생성 + 토픽 발행."""
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
    }

    anomaly_id = await queries.insert_anomaly(anomaly_data)
    detected_at = datetime.now().isoformat()
    logger.info("Anomaly (no-llm) created: id=%d rule=%s", anomaly_id, rule["rule_name"])

    await bus.publish(
        topic=TOPIC_ANOMALY_DETECTED,
        payload=_build_detected_message(
            anomaly_id=anomaly_id,
            detected_at=detected_at,
            rule=rule,
            severity=severity,
            title=title,
            analysis=f"측정값 {measured_value} {op} 임계치 {threshold_value}",
            measured_value=measured_value,
            threshold_value=threshold_value,
            affected_entity="",
            confidence=1.0,
            evidence_summary=[],
        ),
        source="detection_agent",
    )

    return {**anomaly_data, "anomaly_id": anomaly_id}


def _build_detected_message(
    *,
    anomaly_id: int,
    detected_at: str,
    rule: dict[str, Any],
    severity: str,
    title: str,
    analysis: str,
    measured_value: float,
    threshold_value: float | None,
    affected_entity: str,
    confidence: float,
    evidence_summary: list[str],
) -> dict[str, Any]:
    """anomaly.detected 토픽 메시지 — 자기완결형.

    이 메시지 하나만 봐도 무슨 이상이 왜 감지됐는지 전부 파악 가능.
    """
    return {
        # ── 식별 ──
        "anomaly_id": anomaly_id,
        "detected_at": detected_at,

        # ── 무엇을 감지했는가 ──
        "title": title,
        "severity": severity,
        "category": rule.get("category", ""),
        "subcategory": rule.get("subcategory", ""),
        "affected_entity": affected_entity,

        # ── 어떻게 감지했는가 (규칙 정보) ──
        "detection": {
            "rule_id": rule.get("rule_id"),
            "rule_name": rule.get("rule_name", ""),
            "check_type": rule.get("check_type", ""),
            "measured_value": measured_value,
            "threshold": {
                "operator": rule.get("threshold_op", ">"),
                "warning": rule.get("warning_value"),
                "critical": rule.get("critical_value"),
            },
            "confidence": confidence,
        },

        # ── 감지 에이전트의 판단 ──
        "analysis": analysis,

        # ── 근거 데이터 요약 (원본 데이터는 포함하지 않음) ──
        "evidence_summary": evidence_summary,
    }


def _summarize_evidence(query_result: list[dict[str, Any]], max_items: int = 5) -> list[str]:
    """쿼리 결과를 사람이 읽을 수 있는 요약 문장 목록으로 변환."""
    summaries = []
    for row in query_result[:max_items]:
        parts = []
        for k, v in row.items():
            if v is not None:
                parts.append(f"{k}={v}")
        if parts:
            summaries.append(", ".join(parts))
    if len(query_result) > max_items:
        summaries.append(f"... 외 {len(query_result) - max_items}건")
    return summaries


def _build_user_message(
    rule: dict[str, Any],
    measured_value: float,
    query_result: list[dict[str, Any]],
) -> str:
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

위 데이터를 분석하여 실제 이상 여부를 판단하세요.
필요시 도구를 사용하여 추가 데이터를 조회하세요.
"""
