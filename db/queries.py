"""DB 쿼리 — 감지 규칙, 이상, 상관, 사이클, 사용자."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from db.oracle import execute, execute_dml, execute_returning


# ── Users ──

async def get_all_users() -> list[dict[str, Any]]:
    return await execute("SELECT * FROM users ORDER BY user_id")


async def get_user(user_id: int) -> dict[str, Any] | None:
    rows = await execute("SELECT * FROM users WHERE user_id = :id", {"id": user_id})
    return rows[0] if rows else None


async def get_user_by_username(username: str) -> dict[str, Any] | None:
    rows = await execute("SELECT * FROM users WHERE username = :username", {"username": username})
    return rows[0] if rows else None


async def create_user(data: dict[str, Any]) -> int:
    cols = ", ".join(data.keys())
    vals = ", ".join(f":{k}" for k in data.keys())
    sql = f"INSERT INTO users ({cols}) VALUES ({vals}) RETURNING user_id INTO :out_id"
    return int(await execute_returning(sql, data))


async def update_user(user_id: int, data: dict[str, Any]) -> int:
    sets = ", ".join(f"{k} = :{k}" for k in data.keys())
    data["id"] = user_id
    return await execute_dml(
        f"UPDATE users SET {sets} WHERE user_id = :id",
        data,
    )


async def delete_user(user_id: int) -> int:
    return await execute_dml("DELETE FROM users WHERE user_id = :id", {"id": user_id})


# ── Rules ──

async def get_active_rules() -> list[dict[str, Any]]:
    return await execute(
        "SELECT * FROM detection_rules WHERE enabled = 1 ORDER BY rule_id"
    )


async def get_all_rules() -> list[dict[str, Any]]:
    return await execute("SELECT * FROM detection_rules ORDER BY rule_id")


async def get_rule(rule_id: int) -> dict[str, Any] | None:
    rows = await execute("SELECT * FROM detection_rules WHERE rule_id = :id", {"id": rule_id})
    return rows[0] if rows else None


async def create_rule(data: dict[str, Any]) -> int:
    cols = ", ".join(data.keys())
    vals = ", ".join(f":{k}" for k in data.keys())
    sql = f"INSERT INTO detection_rules ({cols}) VALUES ({vals}) RETURNING rule_id INTO :out_id"
    return int(await execute_returning(sql, data))


async def update_rule(rule_id: int, data: dict[str, Any]) -> int:
    sets = ", ".join(f"{k} = :{k}" for k in data.keys())
    data["id"] = rule_id
    return await execute_dml(
        f"UPDATE detection_rules SET {sets}, updated_at = SYSTIMESTAMP WHERE rule_id = :id",
        data,
    )


async def delete_rule(rule_id: int) -> int:
    return await execute_dml("DELETE FROM detection_rules WHERE rule_id = :id", {"id": rule_id})


# ── Anomalies ──

async def insert_anomaly(data: dict[str, Any]) -> int:
    cols = ", ".join(data.keys())
    vals = ", ".join(f":{k}" for k in data.keys())
    sql = f"INSERT INTO anomalies ({cols}) VALUES ({vals}) RETURNING anomaly_id INTO :out_id"
    return int(await execute_returning(sql, data))


async def get_anomalies(
    status: str | None = None, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    where = "WHERE status = :status" if status else ""
    params: dict[str, Any] = {"lim": limit, "off": offset}
    if status:
        params["status"] = status
    return await execute(
        f"""SELECT * FROM anomalies {where}
            ORDER BY detected_at DESC
            OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY""",
        params,
    )


async def get_active_anomalies() -> list[dict[str, Any]]:
    return await execute(
        "SELECT * FROM anomalies WHERE status IN ('detected', 'in_progress') ORDER BY detected_at DESC"
    )


async def update_anomaly_status(anomaly_id: int, status: str, resolved_by: str | None = None) -> int:
    extra = ""
    params: dict[str, Any] = {"id": anomaly_id, "status": status}
    if status == "resolved":
        extra = ", resolved_at = SYSTIMESTAMP, resolved_by = :resolved_by"
        params["resolved_by"] = resolved_by
    return await execute_dml(
        f"UPDATE anomalies SET status = :status{extra} WHERE anomaly_id = :id",
        params,
    )


async def add_anomaly_note(anomaly_id: int, note: str) -> int:
    return await execute_dml(
        "UPDATE anomalies SET notes = notes || CHR(10) || :note WHERE anomaly_id = :id",
        {"id": anomaly_id, "note": note},
    )




# ── RCA ──

async def insert_rca(data: dict[str, Any]) -> int:
    cols = ", ".join(data.keys())
    vals = ", ".join(f":{k}" for k in data.keys())
    sql = f"INSERT INTO rca_analyses ({cols}) VALUES ({vals}) RETURNING rca_id INTO :out_id"
    return int(await execute_returning(sql, data))


async def get_rca_by_anomaly(anomaly_id: int) -> dict[str, Any] | None:
    rows = await execute(
        "SELECT * FROM rca_analyses WHERE anomaly_id = :id ORDER BY created_at DESC FETCH NEXT 1 ROWS ONLY",
        {"id": anomaly_id},
    )
    return rows[0] if rows else None


async def get_rca_list(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    where = "WHERE r.status = :status" if status else ""
    params: dict[str, Any] = {"lim": limit}
    if status:
        params["status"] = status
    return await execute(
        f"""SELECT r.*, a.title as anomaly_title, a.severity, a.category
            FROM rca_analyses r
            JOIN anomalies a ON r.anomaly_id = a.anomaly_id
            {where}
            ORDER BY r.created_at DESC
            FETCH NEXT :lim ROWS ONLY""",
        params,
    )


async def update_rca(rca_id: int, data: dict[str, Any]) -> int:
    sets = ", ".join(f"{k} = :{k}" for k in data.keys())
    data["id"] = rca_id
    return await execute_dml(
        f"UPDATE rca_analyses SET {sets} WHERE rca_id = :id",
        data,
    )


# ── Detection Cycles ──

async def start_cycle() -> int:
    return int(
        await execute_returning(
            "INSERT INTO detection_cycles (started_at) VALUES (SYSTIMESTAMP) RETURNING cycle_id INTO :out_id"
        )
    )


async def complete_cycle(cycle_id: int, rules_evaluated: int, anomalies_found: int, duration_ms: int) -> None:
    await execute_dml(
        """UPDATE detection_cycles
           SET completed_at = SYSTIMESTAMP, rules_evaluated = :rules,
               anomalies_found = :anomalies, duration_ms = :dur
           WHERE cycle_id = :id""",
        {"id": cycle_id, "rules": rules_evaluated, "anomalies": anomalies_found, "dur": duration_ms},
    )
