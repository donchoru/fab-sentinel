"""규칙별 평가기 — 룰 엔진 + 감지 에이전트 연동."""

from __future__ import annotations

import logging
from typing import Any

from agent.detection_agent import analyze_and_save, analyze_without_llm
from rules.engine import evaluate_rule

logger = logging.getLogger(__name__)


async def evaluate_and_detect(rule: dict[str, Any]) -> dict[str, Any] | None:
    """단일 규칙 평가 → 위반 시 이상 생성 + DB 저장.

    Returns anomaly dict if anomaly created, None otherwise.
    """
    result = await evaluate_rule(rule)

    if not result["violated"]:
        return None

    severity = result["severity"] or "warning"
    measured = result["measured_value"]
    rows = result["rows"]

    # LLM 분석 활성화된 규칙 → 감지 에이전트가 분석 + DB 저장
    if rule.get("llm_enabled"):
        return await analyze_and_save(rule, measured, rows)

    # LLM 비활성화 → 바로 이상 생성 + DB 저장
    return await analyze_without_llm(rule, measured, severity)
