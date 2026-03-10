"""알림 라우터 — DB 기록 전용.

외부 알림 채널 없이, sentinel_alert_history에 메시지 본문을 기록.
Streamlit 대시보드에서 조회.
"""

from __future__ import annotations

import logging
from typing import Any

from db import queries

logger = logging.getLogger(__name__)


async def send_alert(anomaly: dict[str, Any], rca_result: dict[str, Any] | None = None) -> None:
    """알림 메시지 포매팅 → sentinel_alert_history에 INSERT."""
    message = _format_message(anomaly, rca_result)

    await queries.insert_alert({
        "anomaly_id": anomaly["anomaly_id"],
        "channel": "dashboard",
        "recipient": "",
        "message": message,
        "delivered": 1,
        "error_msg": "",
    })

    logger.info("Alert saved: anomaly_id=%d", anomaly["anomaly_id"])


def _format_message(anomaly: dict[str, Any], rca_result: dict[str, Any] | None = None) -> str:
    """DB row에서 마크다운 형식 알림 메시지 생성."""
    severity = (anomaly.get("severity") or "warning").upper()

    lines = [
        f"## [{severity}] 이상 감지 알림",
        "",
        f"**이상 ID**: {anomaly.get('anomaly_id')}",
        f"**제목**: {anomaly.get('title', '')}",
        f"**심각도**: {severity}",
        f"**감지 시각**: {anomaly.get('detected_at', '')}",
        f"**카테고리**: {anomaly.get('category', '')}",
        f"**영향 대상**: {anomaly.get('affected_entity', '')}",
    ]

    measured = anomaly.get("measured_value")
    threshold = anomaly.get("threshold_value")
    if measured is not None:
        lines.append(f"- 측정값: **{measured}** (임계치: {threshold})")

    description = anomaly.get("description")
    if description:
        lines.append("")
        lines.append(f"### 설명")
        lines.append(description)

    # RCA 결과
    if rca_result:
        root_cause = rca_result.get("root_cause")
        if root_cause:
            lines.append("")
            lines.append("### 원인 분석 (RCA)")
            lines.append(f"**근본 원인**: {root_cause}")

            evidence = rca_result.get("evidence", [])
            if evidence:
                lines.append("")
                lines.append("**근거**:")
                for e in evidence:
                    lines.append(f"- {e}")

            impact = rca_result.get("impact_scope")
            if impact:
                lines.append(f"**영향 범위**: {impact}")

            conf = rca_result.get("confidence", 0)
            lines.append(f"**분석 신뢰도**: {conf:.0%}")

        actions = rca_result.get("suggested_actions", [])
        if actions:
            lines.append("")
            lines.append("### 권장 조치")
            for i, action in enumerate(actions, 1):
                lines.append(f"{i}. {action}")

    return "\n".join(lines)
