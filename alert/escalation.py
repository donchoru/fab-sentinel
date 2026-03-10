"""에스컬레이션 — 미확인 이상 재알림 (DB 기록)."""

from __future__ import annotations

import logging
from typing import Any

from alert.router import send_alert
from db import queries
from db.oracle import execute

logger = logging.getLogger(__name__)


async def check_escalations() -> int:
    """미확인 이상에 대한 에스컬레이션 확인.

    escalation_delay_min > 0인 라우팅 규칙과 매칭되는
    detected 상태 이상을 찾아 재알림.

    Returns: escalated count
    """
    routes = await queries.get_alert_routes(enabled_only=True)
    esc_routes = [r for r in routes if r.get("escalation_delay_min", 0) > 0]
    if not esc_routes:
        return 0

    count = 0
    for route in esc_routes:
        delay_min = route["escalation_delay_min"]
        category = route.get("category")

        cat_where = "AND a.category = :cat" if category else ""
        params: dict[str, Any] = {"delay": delay_min}
        if category:
            params["cat"] = category

        unacked = await execute(
            f"""SELECT a.anomaly_id, a.severity, a.title, a.category,
                       a.affected_entity, a.detected_at, a.measured_value,
                       a.threshold_value, a.description,
                       a.llm_analysis, a.llm_suggestion
                FROM sentinel_anomalies a
                WHERE a.status = 'detected'
                  AND a.detected_at <= SYSTIMESTAMP - NUMTODSINTERVAL(:delay, 'MINUTE')
                  {cat_where}
                  AND NOT EXISTS (
                      SELECT 1 FROM sentinel_alert_history h
                      WHERE h.anomaly_id = a.anomaly_id
                        AND h.channel = :channel
                  )""",
            {**params, "channel": route["channel"]},
        )

        for anomaly in unacked:
            # [ESCALATED] 접두사 붙여서 재알림
            escalated = dict(anomaly)
            escalated["title"] = f"[ESCALATED] {anomaly.get('title', '')}"
            await send_alert(escalated)
            count += 1

    if count:
        logger.info("Escalated %d anomalies", count)
    return count
