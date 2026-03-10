"""감지 주기 오케스트레이션."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from db import queries
from detection.evaluator import evaluate_and_detect

logger = logging.getLogger(__name__)


_MAX_CONCURRENT = 10  # 동시 평가 최대 규칙 수


async def run_detection_cycle() -> dict[str, Any]:
    """감지 사이클 1회 실행 (병렬).

    1. 활성 규칙 로드
    2. 규칙별 평가 — asyncio.gather 병렬 (세마포어로 동시성 제한)
    3. 이상 생성 + DB 저장 (evaluator가 처리)
    4. 사이클 로그 기록

    Returns: cycle summary dict
    """
    start = time.monotonic()
    cycle_id = await queries.start_cycle()
    logger.info("Detection cycle %d started", cycle_id)

    rules = await queries.get_active_rules()
    sem = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _eval_one(rule: dict[str, Any]) -> dict[str, Any] | None:
        async with sem:
            try:
                return await evaluate_and_detect(rule)
            except Exception:
                logger.exception("Rule evaluation failed: rule_id=%s", rule.get("rule_id"))
                return None

    results = await asyncio.gather(*[_eval_one(r) for r in rules])
    anomalies_found = sum(1 for r in results if r is not None)

    duration_ms = int((time.monotonic() - start) * 1000)
    await queries.complete_cycle(cycle_id, len(rules), anomalies_found, duration_ms)

    summary = {
        "cycle_id": cycle_id,
        "rules_evaluated": len(rules),
        "anomalies_found": anomalies_found,
        "duration_ms": duration_ms,
    }
    logger.info("Detection cycle %d completed: %s", cycle_id, summary)
    return summary
