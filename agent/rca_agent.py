"""원인분석(RCA) 에이전트 — anomaly.detected 토픽 구독 → 근본원인 분석.

발행하는 메시지에는 원래 이상 정보 + RCA 분석 결과가 모두 포함됨.
메시지만 봐도 "무슨 이상이 왜 발생했고, 어떻게 해야 하는지" 전부 파악 가능.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from agent.agent_loop import run_agent_loop
from agent.prompts import RCA_SYSTEM
from bus.topic import Message, bus, TOPIC_ANOMALY_DETECTED, TOPIC_RCA_COMPLETED, TOPIC_ALERT_REQUEST
from db import queries

logger = logging.getLogger(__name__)


def register() -> None:
    """토픽 버스에 RCA 에이전트 핸들러 등록."""
    bus.subscribe(TOPIC_ANOMALY_DETECTED, handle_anomaly)
    logger.info("RCA agent registered on topic=%s", TOPIC_ANOMALY_DETECTED)


async def handle_anomaly(msg: Message) -> None:
    """anomaly.detected 토픽 메시지 수신 → RCA 분석 실행."""
    payload = msg.payload
    anomaly_id = payload["anomaly_id"]
    logger.info("RCA agent received anomaly_id=%d", anomaly_id)

    try:
        result = await _run_rca(payload)

        # DB에 분석 결과 저장
        await queries.update_anomaly_rca(
            anomaly_id=anomaly_id,
            analysis=result.get("root_cause", "분석 실패"),
            suggestion=json.dumps(
                result.get("suggested_actions", []),
                ensure_ascii=False,
            ),
        )

        logger.info(
            "RCA completed: anomaly_id=%d root_cause=%s confidence=%.2f",
            anomaly_id,
            result.get("root_cause", "?")[:80],
            result.get("confidence", 0),
        )

        completed_at = datetime.now().isoformat()

        # 원본 이상 정보를 그대로 포함한 자기완결형 메시지
        anomaly_context = {
            "anomaly_id": payload["anomaly_id"],
            "detected_at": payload.get("detected_at", ""),
            "title": payload.get("title", ""),
            "severity": payload.get("severity", "warning"),
            "category": payload.get("category", ""),
            "subcategory": payload.get("subcategory", ""),
            "affected_entity": payload.get("affected_entity", ""),
            "detection": payload.get("detection", {}),
            "detection_analysis": payload.get("analysis", ""),
        }

        # rca.completed 토픽 — 이상 정보 + RCA 결과 전부 포함
        await bus.publish(
            topic=TOPIC_RCA_COMPLETED,
            payload={
                # ── 식별 ──
                "anomaly_id": anomaly_id,
                "completed_at": completed_at,

                # ── 원래 이상 정보 (감지 에이전트가 보낸 것 그대로) ──
                "anomaly": anomaly_context,

                # ── RCA 분석 결과 ──
                "rca": {
                    "root_cause": result.get("root_cause", ""),
                    "evidence": result.get("evidence", []),
                    "impact_scope": result.get("impact_scope", ""),
                    "suggested_actions": result.get("suggested_actions", []),
                    "confidence": result.get("confidence", 0),
                    "related_entities": result.get("related_entities", []),
                },
            },
            source="rca_agent",
        )

        # alert.request 토픽 — 알림에 필요한 전체 맥락 포함
        await bus.publish(
            topic=TOPIC_ALERT_REQUEST,
            payload={
                # ── 식별 ──
                "anomaly_id": anomaly_id,

                # ── 이상 요약 ──
                "title": payload.get("title", ""),
                "severity": payload.get("severity", "warning"),
                "category": payload.get("category", ""),
                "subcategory": payload.get("subcategory", ""),
                "affected_entity": payload.get("affected_entity", ""),
                "detected_at": payload.get("detected_at", ""),

                # ── 감지 정보 ──
                "detection": {
                    "rule_name": payload.get("detection", {}).get("rule_name", ""),
                    "check_type": payload.get("detection", {}).get("check_type", ""),
                    "measured_value": payload.get("detection", {}).get("measured_value"),
                    "threshold": payload.get("detection", {}).get("threshold", {}),
                },

                # ── RCA 결과 ──
                "root_cause": result.get("root_cause", ""),
                "evidence": result.get("evidence", []),
                "impact_scope": result.get("impact_scope", ""),
                "suggested_actions": result.get("suggested_actions", []),
                "related_entities": result.get("related_entities", []),
                "rca_confidence": result.get("confidence", 0),
            },
            source="rca_agent",
        )

    except Exception:
        logger.exception("RCA failed for anomaly_id=%d", anomaly_id)
        await queries.update_anomaly_rca(
            anomaly_id=anomaly_id,
            analysis="RCA 분석 중 오류 발생",
            suggestion="수동 분석 필요",
        )


async def _run_rca(payload: dict[str, Any]) -> dict[str, Any]:
    """ReAct 루프로 근본원인 분석."""
    user_msg = _build_rca_message(payload)
    return await run_agent_loop(
        system_prompt=RCA_SYSTEM,
        user_message=user_msg,
        max_rounds=3,
    )


def _build_rca_message(payload: dict[str, Any]) -> str:
    detection = payload.get("detection", {})
    threshold = detection.get("threshold", {})
    evidence = payload.get("evidence_summary", [])

    return f"""## 이상 감지 — 근본원인 분석 요청

**이상 ID**: {payload['anomaly_id']}
**감지 시각**: {payload.get('detected_at', '')}
**제목**: {payload.get('title', '')}
**심각도**: {payload.get('severity', 'warning')}
**카테고리**: {payload.get('category', '')} / {payload.get('subcategory', '')}
**영향 엔티티**: {payload.get('affected_entity', '')}

### 감지 규칙
- 규칙명: {detection.get('rule_name', '')}
- 검사 유형: {detection.get('check_type', '')}
- 측정값: {detection.get('measured_value', '')}
- 임계치: 경고 {threshold.get('warning', 'N/A')} / 위험 {threshold.get('critical', 'N/A')} (연산자: {threshold.get('operator', '>')})

### 감지 에이전트 분석
{payload.get('analysis', '정보 없음')}

### 근거 데이터 요약
{chr(10).join(f'- {e}' for e in evidence) if evidence else '(없음)'}

위 이상의 근본 원인을 분석하세요.
제공된 도구로 관련 설비/공정/물류 데이터를 추가 조회하여
원인을 좁혀가세요.
"""
