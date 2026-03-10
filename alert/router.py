"""알림 라우터 — 규칙 기반 채널 매핑 + 토픽 구독.

alert.request 메시지에는 이상 정보 + RCA 결과가 모두 포함되어 있으므로
알림 본문에 전체 맥락을 담을 수 있음.
"""

from __future__ import annotations

import logging
from typing import Any

from alert.base import BaseAlertChannel
from alert.dashboard import DashboardChannel
from alert.email_channel import EmailChannel
from alert.messenger import MessengerChannel
from bus.topic import Message, bus, TOPIC_ALERT_REQUEST
from db import queries

logger = logging.getLogger(__name__)

_channels: dict[str, BaseAlertChannel] = {
    "dashboard": DashboardChannel(),
    "email": EmailChannel(),
    "messenger": MessengerChannel(),
}

SEVERITY_ORDER = {"warning": 1, "critical": 2}


def register() -> None:
    """토픽 버스에 알림 라우터 등록."""
    bus.subscribe(TOPIC_ALERT_REQUEST, handle_alert_request)
    logger.info("Alert router registered on topic=%s", TOPIC_ALERT_REQUEST)


async def handle_alert_request(msg: Message) -> None:
    """alert.request 토픽 수신 → 라우팅 규칙에 따라 발송."""
    payload = msg.payload
    anomaly_id = payload.get("anomaly_id")
    severity = payload.get("severity", "warning")
    category = payload.get("category", "")

    message = _format_message(payload)

    routes = await queries.get_alert_routes(enabled_only=True)
    matched_routes = _match_routes(routes, category, severity)

    if not matched_routes:
        matched_routes = [{"channel": "dashboard", "recipient": "", "escalation_delay_min": 0}]

    for route in matched_routes:
        channel_name = route["channel"]
        channel = _channels.get(channel_name)
        if not channel:
            logger.warning("Unknown channel: %s", channel_name)
            continue

        anomaly_data = {
            "anomaly_id": anomaly_id,
            "severity": severity,
            "title": payload.get("title", ""),
            "_recipient": route.get("recipient", ""),
            "_webhook_url": "",
        }

        delivered = await channel.send(anomaly_data, message)

        await queries.insert_alert({
            "anomaly_id": anomaly_id,
            "channel": channel_name,
            "recipient": route.get("recipient", ""),
            "delivered": 1 if delivered else 0,
            "error_msg": "" if delivered else "delivery_failed",
        })


def _match_routes(
    routes: list[dict[str, Any]], category: str, severity: str
) -> list[dict[str, Any]]:
    matched = []
    sev_level = SEVERITY_ORDER.get(severity, 0)

    for route in routes:
        route_cat = route.get("category")
        if route_cat and route_cat != category:
            continue
        min_sev = SEVERITY_ORDER.get(route.get("severity_min", "warning"), 1)
        if sev_level < min_sev:
            continue
        if route.get("escalation_delay_min", 0) == 0:
            matched.append(route)

    return matched


def _format_message(payload: dict[str, Any]) -> str:
    """알림 메시지 포맷 — 전체 맥락 포함."""
    severity = payload.get("severity", "warning").upper()
    detection = payload.get("detection", {})
    threshold = detection.get("threshold", {})

    lines = [
        f"## [{severity}] 이상 감지 알림",
        "",
        f"**이상 ID**: {payload.get('anomaly_id')}",
        f"**제목**: {payload.get('title', '')}",
        f"**심각도**: {severity}",
        f"**감지 시각**: {payload.get('detected_at', '')}",
        f"**카테고리**: {payload.get('category', '')} / {payload.get('subcategory', '')}",
        f"**영향 대상**: {payload.get('affected_entity', '')}",
    ]

    # 감지 정보
    if detection:
        lines.append("")
        lines.append("### 감지 정보")
        lines.append(f"- 규칙: {detection.get('rule_name', '')}")
        lines.append(f"- 검사 유형: {detection.get('check_type', '')}")
        measured = detection.get('measured_value')
        if measured is not None:
            op = threshold.get('operator', '>')
            warn = threshold.get('warning', 'N/A')
            crit = threshold.get('critical', 'N/A')
            lines.append(f"- 측정값: **{measured}** (경고: {warn}, 위험: {crit}, 연산자: {op})")

    # RCA 결과
    root_cause = payload.get("root_cause")
    if root_cause:
        lines.append("")
        lines.append("### 원인 분석 (RCA)")
        lines.append(f"**근본 원인**: {root_cause}")

        evidence = payload.get("evidence", [])
        if evidence:
            lines.append("")
            lines.append("**근거**:")
            for e in evidence:
                lines.append(f"- {e}")

        impact = payload.get("impact_scope")
        if impact:
            lines.append(f"")
            lines.append(f"**영향 범위**: {impact}")

        related = payload.get("related_entities", [])
        if related:
            lines.append(f"**관련 설비**: {', '.join(related)}")

        conf = payload.get("rca_confidence", 0)
        lines.append(f"**분석 신뢰도**: {conf:.0%}")

    # 권장 조치
    actions = payload.get("suggested_actions", [])
    if actions:
        lines.append("")
        lines.append("### 권장 조치")
        for i, action in enumerate(actions, 1):
            lines.append(f"{i}. {action}")

    return "\n".join(lines)
