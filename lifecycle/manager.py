"""이상 상태 전환 관리 — detected → in_progress → resolved."""

from __future__ import annotations

from db import queries

# 허용된 상태 전환
TRANSITIONS = {
    "detected": ["in_progress", "resolved"],
    "in_progress": ["resolved"],
    "resolved": [],
}


class InvalidTransitionError(Exception):
    pass


async def transition(anomaly_id: int, new_status: str, resolved_by: str | None = None) -> str:
    """이상 상태를 전환한다.

    Returns:
        새 상태 문자열

    Raises:
        ValueError: anomaly_id가 존재하지 않을 때
        InvalidTransitionError: 허용되지 않은 전환일 때
    """
    anomalies = await queries.get_anomalies(limit=1000)
    current = next((a for a in anomalies if a.get("anomaly_id") == anomaly_id), None)
    if current is None:
        raise ValueError(f"Anomaly {anomaly_id} not found")

    current_status = current.get("status", "")
    allowed = TRANSITIONS.get(current_status, [])

    if new_status not in allowed:
        raise InvalidTransitionError(
            f"'{current_status}' → '{new_status}' 전환 불가 (허용: {allowed})"
        )

    await queries.update_anomaly_status(anomaly_id, new_status, resolved_by)
    return new_status
