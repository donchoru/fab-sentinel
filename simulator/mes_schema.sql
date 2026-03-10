-- MES 더미 테이블 (SQLite)

-- 컨베이어 상태
CREATE TABLE IF NOT EXISTS mes_conveyor_status (
    zone_id TEXT NOT NULL,
    line_id TEXT NOT NULL,
    carrier_count INTEGER DEFAULT 0,
    capacity INTEGER DEFAULT 100,
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (zone_id, line_id)
);

-- 반송 로그
CREATE TABLE IF NOT EXISTS mes_transfer_log (
    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    carrier_id TEXT NOT NULL,
    from_zone TEXT,
    to_zone TEXT,
    line_id TEXT,
    transfer_time TEXT DEFAULT (datetime('now', 'localtime')),
    transfer_time_sec REAL DEFAULT 0,
    status TEXT DEFAULT 'COMPLETED'
);

-- 캐리어 큐 (대기)
CREATE TABLE IF NOT EXISTS mes_carrier_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id TEXT NOT NULL,
    line_id TEXT NOT NULL,
    carrier_id TEXT,
    wait_time_sec REAL DEFAULT 0
);

-- 반송 설비 상태 (AGV/OHT)
CREATE TABLE IF NOT EXISTS mes_vehicle_status (
    vehicle_id TEXT PRIMARY KEY,
    vehicle_type TEXT NOT NULL,  -- AGV / OHT
    status TEXT NOT NULL         -- RUN / IDLE / ERROR / CHARGING
);

-- WIP 요약
CREATE TABLE IF NOT EXISTS mes_wip_summary (
    process TEXT NOT NULL,       -- TFT / CELL / MODULE
    step_id TEXT NOT NULL,
    step_name TEXT,
    current_wip INTEGER DEFAULT 0,
    target_wip INTEGER DEFAULT 100,
    PRIMARY KEY (process, step_id)
);

-- WIP 흐름
CREATE TABLE IF NOT EXISTS mes_wip_flow (
    flow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    process TEXT NOT NULL,
    step_id TEXT NOT NULL,
    direction TEXT NOT NULL,    -- IN / OUT
    qty INTEGER DEFAULT 0,
    flow_time TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 큐 상태
CREATE TABLE IF NOT EXISTS mes_queue_status (
    step_id TEXT PRIMARY KEY,
    step_name TEXT,
    queue_count INTEGER DEFAULT 0,
    avg_wait_min REAL DEFAULT 0,
    max_wait_min REAL DEFAULT 0
);

-- LOT 상태
CREATE TABLE IF NOT EXISTS mes_lot_status (
    lot_id TEXT PRIMARY KEY,
    product_id TEXT,
    current_step TEXT,
    step_name TEXT,
    step_in_time TEXT DEFAULT (datetime('now', 'localtime')),
    hold_flag INTEGER DEFAULT 0,
    hold_reason TEXT
);

-- WIP 스냅샷 (시간별)
CREATE TABLE IF NOT EXISTS mes_wip_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TEXT DEFAULT (datetime('now', 'localtime')),
    process TEXT NOT NULL,
    wip_count INTEGER DEFAULT 0
);

-- 설비 현재 상태
CREATE TABLE IF NOT EXISTS mes_equipment_status (
    equipment_id TEXT PRIMARY KEY,
    equipment_name TEXT,
    line_id TEXT,
    process TEXT,
    status TEXT DEFAULT 'IDLE',  -- RUN / IDLE / DOWN / PM
    last_status_change TEXT DEFAULT (datetime('now', 'localtime')),
    current_recipe TEXT
);

-- 설비 이력
CREATE TABLE IF NOT EXISTS mes_equipment_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id TEXT NOT NULL,
    equipment_name TEXT,
    line_id TEXT,
    status TEXT NOT NULL,
    duration_min REAL DEFAULT 0,
    event_time TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 비계획정지 이력
CREATE TABLE IF NOT EXISTS mes_down_history (
    down_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id TEXT NOT NULL,
    equipment_name TEXT,
    line_id TEXT,
    down_type TEXT DEFAULT 'UNSCHEDULED',
    down_code TEXT,
    down_reason TEXT,
    start_time TEXT DEFAULT (datetime('now', 'localtime')),
    end_time TEXT
);

-- PM 일정
CREATE TABLE IF NOT EXISTS mes_pm_schedule (
    pm_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id TEXT NOT NULL,
    equipment_name TEXT,
    line_id TEXT,
    pm_type TEXT,
    scheduled_date TEXT,
    status TEXT DEFAULT 'PENDING'
);

-- 설비 알람
CREATE TABLE IF NOT EXISTS mes_equipment_alarms (
    alarm_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id TEXT NOT NULL,
    alarm_code TEXT,
    alarm_name TEXT,
    severity TEXT DEFAULT 'WARNING',
    alarm_time TEXT DEFAULT (datetime('now', 'localtime')),
    clear_time TEXT,
    acknowledged INTEGER DEFAULT 0
);

-- Sentinel 테이블 (SQLite 버전)
CREATE TABLE IF NOT EXISTS sentinel_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    query_template TEXT NOT NULL,
    check_type TEXT DEFAULT 'threshold',
    threshold_op TEXT DEFAULT '>',
    warning_value REAL,
    critical_value REAL,
    eval_interval INTEGER DEFAULT 300,
    llm_enabled INTEGER DEFAULT 0,
    llm_prompt TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS sentinel_anomalies (
    anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER REFERENCES sentinel_rules(rule_id),
    correlation_id INTEGER,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    measured_value REAL,
    threshold_value REAL,
    affected_entity TEXT,
    llm_analysis TEXT,
    llm_suggestion TEXT,
    rca_status TEXT DEFAULT 'pending',
    status TEXT DEFAULT 'detected',
    detected_at TEXT DEFAULT (datetime('now', 'localtime')),
    acknowledged_at TEXT,
    resolved_at TEXT,
    resolved_by TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS sentinel_correlations (
    correlation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    anomaly_count INTEGER DEFAULT 0,
    correlation_type TEXT,
    root_cause_guess TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS sentinel_alert_history (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    anomaly_id INTEGER REFERENCES sentinel_anomalies(anomaly_id),
    channel TEXT NOT NULL,
    recipient TEXT,
    message TEXT,
    sent_at TEXT DEFAULT (datetime('now', 'localtime')),
    delivered INTEGER DEFAULT 0,
    error_msg TEXT
);

CREATE TABLE IF NOT EXISTS sentinel_alert_routes (
    route_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    severity_min TEXT DEFAULT 'warning',
    channel TEXT NOT NULL,
    recipient TEXT,
    escalation_delay_min INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sentinel_detection_cycles (
    cycle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT DEFAULT (datetime('now', 'localtime')),
    completed_at TEXT,
    rules_evaluated INTEGER DEFAULT 0,
    anomalies_found INTEGER DEFAULT 0,
    duration_ms INTEGER
);
