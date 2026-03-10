-- FAB 이상감지 시스템 Oracle DDL

-- 1. 감지 규칙
CREATE TABLE detection_rules (
    rule_id        NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_name      VARCHAR2(200)  NOT NULL,
    category       VARCHAR2(50)   NOT NULL,   -- logistics / wip / equipment
    subcategory    VARCHAR2(100),
    query_template CLOB,                       -- SQL with :bind_var (source_type=sql)
    check_type     VARCHAR2(30)   DEFAULT 'threshold' NOT NULL,
                   -- threshold / delta / absence / llm
    source_type    VARCHAR2(10)   DEFAULT 'sql',  -- sql / tool
    tool_name      VARCHAR2(100),               -- 도구명 (source_type=tool)
    tool_args      CLOB,                        -- 도구 파라미터 JSON
    tool_column    VARCHAR2(100),               -- 결과에서 추출할 컬럼명
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
CREATE TABLE anomalies (
    anomaly_id      NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id         NUMBER         REFERENCES detection_rules(rule_id),
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
    status          VARCHAR2(30)   DEFAULT 'detected',
                    -- detected / acknowledged / investigating / resolved / false_positive
    detected_at     TIMESTAMP      DEFAULT SYSTIMESTAMP,
    acknowledged_at TIMESTAMP,
    resolved_at     TIMESTAMP,
    resolved_by     VARCHAR2(100),
    notes           CLOB
);

CREATE INDEX idx_anomalies_status ON anomalies(status);
CREATE INDEX idx_anomalies_detected ON anomalies(detected_at);
CREATE INDEX idx_anomalies_rule ON anomalies(rule_id);
CREATE INDEX idx_anomalies_correlation ON anomalies(correlation_id);

-- 3. 상관 그룹
CREATE TABLE correlations (
    correlation_id   NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title            VARCHAR2(500),
    anomaly_count    NUMBER         DEFAULT 0,
    correlation_type VARCHAR2(30),  -- temporal / causal / spatial
    root_cause_guess CLOB,
    created_at       TIMESTAMP      DEFAULT SYSTIMESTAMP,
    updated_at       TIMESTAMP      DEFAULT SYSTIMESTAMP
);

ALTER TABLE anomalies
    ADD CONSTRAINT fk_anomaly_correlation
    FOREIGN KEY (correlation_id) REFERENCES correlations(correlation_id);

-- 4. 감지 사이클 로그
CREATE TABLE detection_cycles (
    cycle_id        NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at      TIMESTAMP      NOT NULL,
    completed_at    TIMESTAMP,
    rules_evaluated NUMBER         DEFAULT 0,
    anomalies_found NUMBER         DEFAULT 0,
    duration_ms     NUMBER
);
