-- FAB-SENTINEL Oracle DDL

-- 1. 감지 규칙
CREATE TABLE sentinel_rules (
    rule_id        NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_name      VARCHAR2(200)  NOT NULL,
    category       VARCHAR2(50)   NOT NULL,   -- logistics / wip / equipment
    subcategory    VARCHAR2(100),
    query_template CLOB           NOT NULL,   -- SQL with :bind_var
    check_type     VARCHAR2(30)   DEFAULT 'threshold' NOT NULL,
                   -- threshold / delta / absence / llm
    threshold_op   VARCHAR2(10)   DEFAULT '>',
    warning_value  NUMBER,
    critical_value NUMBER,
    eval_interval  NUMBER         DEFAULT 300, -- seconds
    llm_enabled    NUMBER(1)      DEFAULT 0,
    llm_prompt     CLOB,
    enabled        NUMBER(1)      DEFAULT 1,
    created_at     TIMESTAMP      DEFAULT SYSTIMESTAMP,
    updated_at     TIMESTAMP      DEFAULT SYSTIMESTAMP
);

-- 2. 감지된 이상
CREATE TABLE sentinel_anomalies (
    anomaly_id      NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id         NUMBER         REFERENCES sentinel_rules(rule_id),
    correlation_id  NUMBER,
    category        VARCHAR2(50)   NOT NULL,
    severity        VARCHAR2(20)   NOT NULL,   -- warning / critical
    title           VARCHAR2(500)  NOT NULL,
    description     CLOB,
    measured_value  NUMBER,
    threshold_value NUMBER,
    affected_entity VARCHAR2(200), -- equipment_id, zone, line
    llm_analysis    CLOB,
    llm_suggestion  CLOB,
    rca_status      VARCHAR2(20)   DEFAULT 'pending',
                    -- pending / processing / done / failed
    status          VARCHAR2(30)   DEFAULT 'detected',
                    -- detected / acknowledged / investigating / resolved / false_positive
    detected_at     TIMESTAMP      DEFAULT SYSTIMESTAMP,
    acknowledged_at TIMESTAMP,
    resolved_at     TIMESTAMP,
    resolved_by     VARCHAR2(100),
    notes           CLOB
);

CREATE INDEX idx_anomalies_status ON sentinel_anomalies(status);
CREATE INDEX idx_anomalies_rca_status ON sentinel_anomalies(rca_status);
CREATE INDEX idx_anomalies_detected ON sentinel_anomalies(detected_at);
CREATE INDEX idx_anomalies_rule ON sentinel_anomalies(rule_id);
CREATE INDEX idx_anomalies_correlation ON sentinel_anomalies(correlation_id);

-- 3. 상관 그룹
CREATE TABLE sentinel_correlations (
    correlation_id   NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title            VARCHAR2(500),
    anomaly_count    NUMBER         DEFAULT 0,
    correlation_type VARCHAR2(30),  -- temporal / causal / spatial
    root_cause_guess CLOB,
    created_at       TIMESTAMP      DEFAULT SYSTIMESTAMP,
    updated_at       TIMESTAMP      DEFAULT SYSTIMESTAMP
);

ALTER TABLE sentinel_anomalies
    ADD CONSTRAINT fk_anomaly_correlation
    FOREIGN KEY (correlation_id) REFERENCES sentinel_correlations(correlation_id);

-- 4. 알림 이력
CREATE TABLE sentinel_alert_history (
    alert_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    anomaly_id  NUMBER         REFERENCES sentinel_anomalies(anomaly_id),
    channel     VARCHAR2(50)   NOT NULL,  -- dashboard
    recipient   VARCHAR2(200),
    message     CLOB,
    sent_at     TIMESTAMP      DEFAULT SYSTIMESTAMP,
    delivered   NUMBER(1)      DEFAULT 0,
    error_msg   VARCHAR2(500)
);

CREATE INDEX idx_alerts_anomaly ON sentinel_alert_history(anomaly_id);

-- 5. 알림 라우팅 설정
CREATE TABLE sentinel_alert_routes (
    route_id             NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category             VARCHAR2(50),   -- NULL = 전체
    severity_min         VARCHAR2(20)    DEFAULT 'warning',
    channel              VARCHAR2(50)    NOT NULL,
    recipient            VARCHAR2(200),
    escalation_delay_min NUMBER          DEFAULT 0,
    enabled              NUMBER(1)       DEFAULT 1
);

-- 6. 감지 사이클 로그
CREATE TABLE sentinel_detection_cycles (
    cycle_id        NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at      TIMESTAMP      NOT NULL,
    completed_at    TIMESTAMP,
    rules_evaluated NUMBER         DEFAULT 0,
    anomalies_found NUMBER         DEFAULT 0,
    duration_ms     NUMBER
);
