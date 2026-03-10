"""규칙 CRUD + 테스트 + 도구 카탈로그 API."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import queries
from db.oracle import execute
from rules.loader import sync_db_to_yaml
from rules.models import RuleCreate, RuleUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("")
async def list_rules():
    return await queries.get_active_rules()


@router.get("/{rule_id}")
async def get_rule(rule_id: int):
    rule = await queries.get_rule(rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    return rule


@router.post("", status_code=201)
async def create_rule(body: RuleCreate):
    data = body.model_dump(exclude_none=True)
    if "llm_enabled" in data:
        data["llm_enabled"] = 1 if data["llm_enabled"] else 0
    if "enabled" in data:
        data["enabled"] = 1 if data["enabled"] else 0
    rule_id = await queries.create_rule(data)
    await sync_db_to_yaml()
    return {"rule_id": rule_id}


@router.patch("/{rule_id}")
async def update_rule(rule_id: int, body: RuleUpdate):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(400, "No fields to update")
    if "llm_enabled" in data:
        data["llm_enabled"] = 1 if data["llm_enabled"] else 0
    if "enabled" in data:
        data["enabled"] = 1 if data["enabled"] else 0
    updated = await queries.update_rule(rule_id, data)
    if not updated:
        raise HTTPException(404, "Rule not found")
    await sync_db_to_yaml()
    return {"updated": updated}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: int):
    deleted = await queries.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(404, "Rule not found")
    await sync_db_to_yaml()
    return {"deleted": deleted}


@router.post("/{rule_id}/test")
async def test_rule(rule_id: int):
    """규칙 데이터 소스(SQL 또는 도구) 실행해서 결과 확인."""
    rule = await queries.get_rule(rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")

    source_type = rule.get("source_type", "sql")

    try:
        if source_type == "tool":
            from agent.tool_registry import registry
            tool_name = rule.get("tool_name", "")
            args_str = rule.get("tool_args") or "{}"
            args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
            result_str = await registry.dispatch(tool_name, args)
            result = json.loads(result_str)
            rows = []
            for v in result.values():
                if isinstance(v, list):
                    rows = v
                    break
            return {
                "rule_id": rule_id,
                "rule_name": rule["rule_name"],
                "source": f"tool:{tool_name}",
                "row_count": len(rows),
                "rows": rows[:50],
            }
        else:
            sql = rule.get("query_template", "")
            if not sql:
                raise HTTPException(400, "Rule has no query_template")
            rows = await execute(sql)
            return {
                "rule_id": rule_id,
                "rule_name": rule["rule_name"],
                "source": "sql",
                "row_count": len(rows),
                "rows": rows[:50],
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"실행 오류: {e}")


# ── 도구 카탈로그 ──

TOOL_CATALOG = {
    "get_conveyor_load": {
        "label": "컨베이어 부하율",
        "category": "logistics",
        "description": "존별 컨베이어 부하율(%) 조회",
        "params": [
            {"name": "zone", "label": "존 ID", "type": "string", "required": False},
        ],
        "columns": [
            {"name": "load_pct", "label": "부하율 (%)"},
            {"name": "carrier_count", "label": "캐리어 수"},
            {"name": "capacity", "label": "용량"},
        ],
    },
    "get_transfer_throughput": {
        "label": "반송 처리량",
        "category": "logistics",
        "description": "라인별 최근 1시간 반송 처리량 및 평균 처리시간",
        "params": [
            {"name": "line_id", "label": "라인 ID", "type": "string", "required": False},
        ],
        "columns": [
            {"name": "moves_1h", "label": "반송 건수 (/시간)"},
            {"name": "avg_time_sec", "label": "평균 처리시간 (초)"},
        ],
    },
    "get_bottleneck_zones": {
        "label": "물류 병목 존",
        "category": "logistics",
        "description": "대기 시간 임계치 초과 병목 존 감지",
        "params": [
            {"name": "wait_threshold_sec", "label": "대기 임계치 (초)", "type": "integer", "required": False},
        ],
        "columns": [
            {"name": "avg_wait", "label": "평균 대기시간 (초)"},
            {"name": "max_wait", "label": "최대 대기시간 (초)"},
            {"name": "carrier_count", "label": "대기 캐리어 수"},
        ],
    },
    "get_agv_utilization": {
        "label": "AGV/OHT 가동률",
        "category": "logistics",
        "description": "반송 설비 상태별 대수 및 비율",
        "params": [
            {"name": "vehicle_type", "label": "설비 유형 (AGV/OHT)", "type": "string", "required": False},
        ],
        "columns": [
            {"name": "pct", "label": "비율 (%)"},
            {"name": "count", "label": "대수"},
        ],
    },
    "get_wip_levels": {
        "label": "WIP 수준",
        "category": "wip",
        "description": "공정별 현재 WIP 목표 대비 비율",
        "params": [
            {"name": "process", "label": "공정 (TFT/CELL/MODULE)", "type": "string", "required": False},
        ],
        "columns": [
            {"name": "wip_ratio_pct", "label": "WIP 비율 (%)"},
            {"name": "current_wip", "label": "현재 WIP"},
            {"name": "target_wip", "label": "목표 WIP"},
        ],
    },
    "get_flow_balance": {
        "label": "WIP 흐름 밸런스",
        "category": "wip",
        "description": "공정별 유입/유출 밸런스",
        "params": [
            {"name": "hours", "label": "분석 기간 (시간)", "type": "integer", "required": False},
        ],
        "columns": [
            {"name": "net_wip", "label": "순 증가량"},
            {"name": "inflow", "label": "유입량"},
            {"name": "outflow", "label": "유출량"},
        ],
    },
    "get_queue_length": {
        "label": "큐 대기 길이",
        "category": "wip",
        "description": "스텝별 대기 LOT 수 및 대기시간",
        "params": [
            {"name": "step_id", "label": "스텝 ID", "type": "string", "required": False},
        ],
        "columns": [
            {"name": "queue_count", "label": "대기 LOT 수"},
            {"name": "avg_wait_min", "label": "평균 대기시간 (분)"},
            {"name": "max_wait_min", "label": "최대 대기시간 (분)"},
        ],
    },
    "get_aging_lots": {
        "label": "에이징 LOT",
        "category": "wip",
        "description": "기준시간 초과 장기 체류 LOT 조회",
        "params": [
            {"name": "hours_threshold", "label": "에이징 기준 (시간)", "type": "integer", "required": False},
        ],
        "columns": [
            {"name": "hours_in_step", "label": "체류시간 (시간)"},
            {"name": "_count", "label": "에이징 LOT 수"},
        ],
    },
    "get_wip_trend": {
        "label": "WIP 추이",
        "category": "wip",
        "description": "시간별 WIP 변화 트렌드",
        "params": [
            {"name": "process", "label": "공정 (TFT/CELL/MODULE)", "type": "string", "required": True},
            {"name": "hours", "label": "조회 기간 (시간)", "type": "integer", "required": False},
        ],
        "columns": [
            {"name": "total_wip", "label": "총 WIP"},
        ],
    },
    "get_equipment_status": {
        "label": "설비 상태",
        "category": "equipment",
        "description": "설비 현재 상태 (RUN/IDLE/DOWN/PM)",
        "params": [
            {"name": "equipment_id", "label": "설비 ID", "type": "string", "required": False},
            {"name": "line_id", "label": "라인 ID", "type": "string", "required": False},
        ],
        "columns": [
            {"name": "_count", "label": "설비 수"},
        ],
    },
    "get_equipment_utilization": {
        "label": "설비 가동률",
        "category": "equipment",
        "description": "설비 가동률(%) — RUN 시간 비율",
        "params": [
            {"name": "line_id", "label": "라인 ID", "type": "string", "required": False},
            {"name": "hours", "label": "분석 기간 (시간)", "type": "integer", "required": False},
        ],
        "columns": [
            {"name": "utilization_pct", "label": "가동률 (%)"},
            {"name": "down_minutes", "label": "다운 시간 (분)"},
        ],
    },
    "get_unscheduled_downs": {
        "label": "비계획정지",
        "category": "equipment",
        "description": "비계획정지(Unscheduled Down) 이력",
        "params": [
            {"name": "hours", "label": "조회 기간 (시간)", "type": "integer", "required": False},
            {"name": "line_id", "label": "라인 ID", "type": "string", "required": False},
        ],
        "columns": [
            {"name": "down_min", "label": "정지시간 (분)"},
            {"name": "_count", "label": "정지 건수"},
        ],
    },
    "get_pm_schedule": {
        "label": "PM 일정",
        "category": "equipment",
        "description": "예방보전(PM) 일정 및 지연 현황",
        "params": [
            {"name": "line_id", "label": "라인 ID", "type": "string", "required": False},
        ],
        "columns": [
            {"name": "_count", "label": "PM 건수"},
        ],
    },
    "get_equipment_alarms": {
        "label": "설비 알람",
        "category": "equipment",
        "description": "설비 알람 이력",
        "params": [
            {"name": "equipment_id", "label": "설비 ID", "type": "string", "required": False},
            {"name": "hours", "label": "조회 기간 (시간)", "type": "integer", "required": False},
        ],
        "columns": [
            {"name": "_count", "label": "알람 건수"},
        ],
    },
}


@router.get("/tools/catalog")
async def list_tools():
    """사용 가능한 도구 카탈로그."""
    return TOOL_CATALOG
