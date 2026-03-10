"""규칙 CRUD + 테스트 + 자연어 생성 API."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import queries
from db.oracle import execute
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
    return {"updated": updated}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: int):
    deleted = await queries.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(404, "Rule not found")
    return {"deleted": deleted}


@router.post("/{rule_id}/test")
async def test_rule(rule_id: int):
    """규칙 SQL만 실행해서 결과 확인 (이상 생성 안 함)."""
    rule = await queries.get_rule(rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")

    sql = rule.get("query_template", "")
    if not sql:
        raise HTTPException(400, "Rule has no query_template")

    try:
        rows = await execute(sql)
        return {
            "rule_id": rule_id,
            "rule_name": rule["rule_name"],
            "row_count": len(rows),
            "rows": rows[:50],
        }
    except Exception as e:
        raise HTTPException(400, f"Query error: {e}")


# ── 테이블 스키마 조회 ──

MES_TABLES = {
    "mes_conveyor_status": {
        "label": "컨베이어 상태",
        "columns": ["zone_id", "line_id", "carrier_count", "capacity", "updated_at"],
    },
    "mes_transfer_log": {
        "label": "반송 로그",
        "columns": ["transfer_id", "carrier_id", "from_zone", "to_zone", "line_id", "transfer_time", "transfer_time_sec", "status"],
    },
    "mes_carrier_queue": {
        "label": "캐리어 대기 큐",
        "columns": ["queue_id", "zone_id", "line_id", "carrier_id", "wait_time_sec"],
    },
    "mes_vehicle_status": {
        "label": "반송 설비(AGV/OHT)",
        "columns": ["vehicle_id", "vehicle_type", "status"],
    },
    "mes_wip_summary": {
        "label": "WIP 요약",
        "columns": ["process", "step_id", "step_name", "current_wip", "target_wip"],
    },
    "mes_wip_flow": {
        "label": "WIP 흐름",
        "columns": ["flow_id", "process", "step_id", "direction", "qty", "flow_time"],
    },
    "mes_queue_status": {
        "label": "큐 상태",
        "columns": ["step_id", "step_name", "queue_count", "avg_wait_min", "max_wait_min"],
    },
    "mes_lot_status": {
        "label": "LOT 상태",
        "columns": ["lot_id", "product_id", "current_step", "step_name", "step_in_time", "hold_flag", "hold_reason"],
    },
    "mes_wip_snapshot": {
        "label": "WIP 스냅샷",
        "columns": ["snapshot_id", "snapshot_time", "process", "wip_count"],
    },
    "mes_equipment_status": {
        "label": "설비 현재 상태",
        "columns": ["equipment_id", "equipment_name", "line_id", "process", "status", "last_status_change", "current_recipe"],
    },
    "mes_equipment_history": {
        "label": "설비 이력",
        "columns": ["history_id", "equipment_id", "equipment_name", "line_id", "status", "duration_min", "event_time"],
    },
    "mes_down_history": {
        "label": "비계획정지 이력",
        "columns": ["down_id", "equipment_id", "equipment_name", "line_id", "down_type", "down_code", "down_reason", "start_time", "end_time"],
    },
    "mes_pm_schedule": {
        "label": "PM 일정",
        "columns": ["pm_id", "equipment_id", "equipment_name", "line_id", "pm_type", "scheduled_date", "status"],
    },
    "mes_equipment_alarms": {
        "label": "설비 알람",
        "columns": ["alarm_id", "equipment_id", "alarm_code", "alarm_name", "severity", "alarm_time", "clear_time", "acknowledged"],
    },
}


@router.get("/schema/tables")
async def list_tables():
    """MES 테이블 스키마 목록."""
    return MES_TABLES


# ── 자연어 규칙 생성 ──

RULE_GEN_SYSTEM = """너는 반도체 FAB 공정 이상감지 시스템의 규칙 생성기야.
사용자가 자연어로 이상 조건을 설명하면, 감지 규칙을 JSON으로 생성해.

사용 가능한 MES 테이블:
- mes_conveyor_status: zone_id, line_id, carrier_count, capacity
- mes_transfer_log: carrier_id, from_zone, to_zone, line_id, transfer_time_sec, status
- mes_carrier_queue: zone_id, line_id, carrier_id, wait_time_sec
- mes_vehicle_status: vehicle_id, vehicle_type, status (RUN/IDLE/ERROR/CHARGING)
- mes_wip_summary: process, step_id, step_name, current_wip, target_wip
- mes_wip_flow: process, step_id, direction (IN/OUT), qty
- mes_queue_status: step_id, step_name, queue_count, avg_wait_min, max_wait_min
- mes_lot_status: lot_id, product_id, current_step, step_in_time, hold_flag
- mes_equipment_status: equipment_id, equipment_name, line_id, process, status (RUN/IDLE/DOWN/PM)
- mes_equipment_history: equipment_id, line_id, status, duration_min, event_time
- mes_down_history: equipment_id, down_type, down_code, down_reason, start_time, end_time
- mes_pm_schedule: equipment_id, pm_type, scheduled_date, status
- mes_equipment_alarms: equipment_id, alarm_code, alarm_name, severity, alarm_time
- mes_wip_snapshot: snapshot_id, snapshot_time, process, wip_count

반드시 아래 JSON 형식으로만 응답해. 추가 설명 없이 JSON만:
{
  "rule_name": "규칙 이름 (한글, 간결하게)",
  "category": "logistics|wip|equipment 중 하나",
  "subcategory": "세부 카테고리",
  "query_template": "SELECT 쿼리 (Oracle SQL, 숫자 컬럼이 첫번째 값으로 오게)",
  "check_type": "threshold|delta|absence|llm 중 하나",
  "threshold_op": ">|<|>=|<= 중 하나",
  "warning_value": 경고 임계치 (숫자),
  "critical_value": 위험 임계치 (숫자),
  "llm_enabled": true|false,
  "llm_prompt": "LLM에게 판단을 맡길 경우의 프롬프트 (없으면 null)",
  "explanation": "이 규칙이 무엇을 감지하는지 설명"
}

핵심 규칙:
- check_type이 "llm"이면 llm_enabled=true, llm_prompt 필수
- check_type이 "threshold"이면 query_template의 SELECT 결과 첫번째 숫자 컬럼을 threshold_op으로 비교
- 자연어 조건이 복잡하면 check_type="llm"으로 하고, 판단을 LLM에게 맡겨
- query_template에는 관련 데이터를 조회하는 SQL을 작성 (충분한 컨텍스트 제공)
- eval_interval은 포함하지 마 (기본값 사용)

★ 판단 패턴 가이드:

1) 단순 임계값 — "재공이 100개 넘으면 이상"
   → check_type="threshold", threshold_op=">", warning_value=80, critical_value=100
   → query_template: SELECT current_wip FROM mes_wip_summary WHERE ...

2) 상대적 비교 — "특정 공정만 유독 높으면 이상 (전체 대비)"
   → check_type="llm" (AI가 비교 판단)
   → query_template: 전체 공정 데이터를 한번에 조회 (공정별 WIP + 전체 평균)
   → llm_prompt: "각 공정의 재공을 전체 평균과 비교해. 평균 대비 2배 이상인 공정이 있으면 이상. 전체적으로 높은 건 정상."

3) 추세/변화 — "최근 1시간 동안 재공이 계속 증가하면 이상"
   → check_type="llm"
   → query_template: 시간순 데이터 조회
   → llm_prompt: "시간 흐름에 따른 추세를 봐. 지속 증가 패턴이면 이상."

4) 복합 조건 — "설비가 DOWN인데 알람도 없으면 이상"
   → check_type="llm"
   → query_template: 설비 상태 + 알람을 JOIN해서 조회
   → llm_prompt: "설비가 DOWN 상태인데 최근 알람이 없으면 비정상. 알람이 있으면 정상 대응 중."

5) 비율 기반 — "에러 상태 AGV가 전체의 30% 이상이면 이상"
   → check_type="threshold" (비율 계산 SQL)
   → query_template: SELECT ROUND(에러수*100.0/전체수, 1) FROM ...

★ 중요: 사용자가 "~만 높으면", "다른 건 괜찮은데 이것만", "평소와 다르면" 같은
  상대적/맥락적 표현을 쓰면 반드시 check_type="llm"으로 하고,
  query_template에 비교 대상 데이터를 모두 포함시켜라.
"""


class NaturalRuleRequest(BaseModel):
    description: str


@router.post("/generate")
async def generate_rule(body: NaturalRuleRequest):
    """자연어 설명에서 감지 규칙 자동 생성."""
    from agent.llm_client import llm_client

    try:
        response = await llm_client.simple_chat(
            system=RULE_GEN_SYSTEM,
            user=body.description,
        )

        # JSON 추출 (```json ... ``` 블록이 있을 수 있음)
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        rule = json.loads(text)
        return rule

    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON: %s", response[:200])
        raise HTTPException(422, f"LLM이 올바른 JSON을 반환하지 않았습니다. 다시 시도해주세요.")
    except Exception as e:
        logger.exception("Rule generation failed")
        raise HTTPException(500, f"규칙 생성 실패: {e}")
