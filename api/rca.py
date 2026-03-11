"""원인분석(RCA) API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from db import queries

router = APIRouter(prefix="/api/rca", tags=["rca"])


@router.get("/{anomaly_id}")
async def get_rca(anomaly_id: int):
    rca = await queries.get_rca_by_anomaly(anomaly_id)
    if not rca:
        raise HTTPException(404, "RCA not found")
    return rca


@router.get("")
async def list_rca(status: str | None = None, limit: int = 50):
    return await queries.get_rca_list(status=status, limit=limit)
