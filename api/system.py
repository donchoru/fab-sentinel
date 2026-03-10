"""시스템 API — 헬스체크, 수동 트리거, 통계, 토픽 버스 모니터링."""

from __future__ import annotations

from fastapi import APIRouter

from bus.topic import bus
from detection.scheduler import run_detection_cycle
from correlation.engine import analyze_correlations
from alert.escalation import check_escalations
from db.oracle import execute

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    try:
        rows = await execute("SELECT 1 AS ok FROM DUAL")
        db_ok = bool(rows)
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "db": "connected" if db_ok else "disconnected",
    }


@router.post("/api/detect/trigger")
async def trigger_detection():
    """감지 사이클 수동 트리거."""
    result = await run_detection_cycle()
    return result


@router.post("/api/correlations/analyze")
async def trigger_correlation():
    """상관관계 분석 수동 트리거."""
    groups = await analyze_correlations()
    return {"correlation_groups": groups}


@router.post("/api/escalations/check")
async def trigger_escalation():
    """에스컬레이션 수동 트리거."""
    count = await check_escalations()
    return {"escalated": count}


@router.get("/api/stats")
async def stats():
    """시스템 통계."""
    rules = await execute("SELECT COUNT(*) AS cnt FROM sentinel_rules WHERE enabled = 1")
    anomalies_24h = await execute(
        """SELECT COUNT(*) AS cnt FROM sentinel_anomalies
           WHERE detected_at >= SYSTIMESTAMP - INTERVAL '24' HOUR"""
    )
    cycles_24h = await execute(
        """SELECT COUNT(*) AS cnt, AVG(duration_ms) AS avg_ms
           FROM sentinel_detection_cycles
           WHERE started_at >= SYSTIMESTAMP - INTERVAL '24' HOUR"""
    )

    return {
        "active_rules": rules[0]["cnt"] if rules else 0,
        "anomalies_24h": anomalies_24h[0]["cnt"] if anomalies_24h else 0,
        "cycles_24h": cycles_24h[0] if cycles_24h else {},
    }


# ── 토픽 버스 모니터링 ──

@router.get("/api/bus/metrics")
async def bus_metrics():
    """토픽 버스 메트릭.

    토픽별 발행/처리/실패 건수, 평균 처리시간, 큐 깊이 등.
    """
    return bus.get_metrics()


@router.get("/api/bus/messages")
async def bus_messages(limit: int = 50):
    """최근 처리된 메시지 목록 (최대 100건)."""
    return {"messages": bus.get_recent_messages(limit=limit)}
