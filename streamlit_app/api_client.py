"""FAB 이상감지 API 클라이언트 — httpx 동기."""

from __future__ import annotations

import os

import httpx

BASE_URL = os.getenv("API_URL", "http://localhost:8600")
_client = httpx.Client(base_url=BASE_URL, timeout=10.0)


def _get(path: str, params: dict | None = None) -> dict | list:
    r = _client.get(path, params=params)
    r.raise_for_status()
    return r.json()


def _post(path: str, json: dict | None = None, params: dict | None = None) -> dict:
    r = _client.post(path, json=json, params=params)
    r.raise_for_status()
    return r.json()


def _patch(path: str, json: dict | None = None) -> dict:
    r = _client.patch(path, json=json)
    r.raise_for_status()
    return r.json()


# ── 대시보드 ──

def get_overview() -> dict:
    return _get("/api/dashboard/overview")


def get_stats() -> dict:
    return _get("/api/stats")


def get_health() -> dict:
    return _get("/health")


# ── 차트 ──

def get_timeline(hours: int = 24) -> dict:
    return _get("/api/dashboard/timeline", {"hours": hours})


def get_heatmap() -> dict:
    return _get("/api/dashboard/heatmap")


# ── 이상 ──

def get_anomalies(status: str | None = None, limit: int = 100) -> list:
    params: dict = {"limit": limit}
    if status:
        params["status"] = status
    return _get("/api/anomalies", params)


def get_active_anomalies() -> list:
    return _get("/api/anomalies/active")


def update_anomaly_status(anomaly_id: int, status: str, resolved_by: str = "") -> dict:
    body = {"status": status}
    if resolved_by:
        body["resolved_by"] = resolved_by
    return _patch(f"/api/anomalies/{anomaly_id}/status", body)


# ── 규칙 ──

def get_rules() -> list:
    return _get("/api/rules")


def create_rule(data: dict) -> dict:
    return _post("/api/rules", json=data)


def update_rule(rule_id: int, data: dict) -> dict:
    return _patch(f"/api/rules/{rule_id}", data)


def delete_rule(rule_id: int) -> dict:
    r = _client.delete(f"/api/rules/{rule_id}")
    r.raise_for_status()
    return r.json()


def test_rule(rule_id: int) -> dict:
    return _post(f"/api/rules/{rule_id}/test")


def get_tool_catalog() -> dict:
    return _get("/api/rules/tools/catalog")


# ── 수동 트리거 ──

def trigger_detection() -> dict:
    return _post("/api/detect/trigger")
