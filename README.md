# FAB-SENTINEL

반도체 FAB 폐쇄망 환경에서 물류 부하 / 재공(WIP) / 설비 이상을 AI 에이전트가 주기적으로 감지하고, 근본원인을 분석하여 알림하는 시스템.

오픈소스 프레임워크(LangChain 등) 없이, OpenAI 호환 사내 LLM + Oracle DB 기반으로 자체 구축.

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        FAB-SENTINEL                             │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │ Scheduler │───→│  Detection   │───→│   Topic Bus           │  │
│  │(APSched)  │    │  Agent       │    │                       │  │
│  │ 매 5분    │    │  (ReAct)     │    │  anomaly.detected ──┐ │  │
│  └──────────┘    └──────────────┘    │                     │ │  │
│                                      │  ┌──────────────────▼ │  │
│                                      │  │  RCA Agent         │ │  │
│                                      │  │  (근본원인 분석)    │ │  │
│                                      │  │  ReAct 3라운드     │ │  │
│                                      │  └──────┬─────────────┘ │  │
│                                      │         │               │  │
│                                      │  rca.completed          │  │
│                                      │  alert.request ───────┐ │  │
│                                      └───────────────────────│─┘  │
│                                                              │    │
│                                      ┌───────────────────────▼─┐  │
│                                      │   Alert Router          │  │
│                                      │   ├ Dashboard (WebSocket)│  │
│                                      │   ├ Email (SMTP)        │  │
│                                      │   └ Messenger (Webhook) │  │
│                                      └─────────────────────────┘  │
│                                                                   │
│  ┌────────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│  │ Rule       │   │ Correlation  │   │ Web API (FastAPI)      │  │
│  │ Engine     │   │ Engine       │   │ + Rule CRUD            │  │
│  │ SQL+임계치 │   │ 시간/공간/인과│   │ + 모니터링 대시보드    │  │
│  └────────────┘   └──────────────┘   └────────────────────────┘  │
│                                                                   │
│                         ┌───────────┐                            │
│                         │ Oracle DB │                             │
│                         │ MES 데이터 │                            │
│                         │ + SENTINEL │                            │
│                         │   테이블   │                            │
│                         └───────────┘                            │
└───────────────────────────────────────────────────────────────────┘
```

---

## 핵심 설계: 토픽 기반 에이전트 분리

이상감지와 원인분석을 **토픽 버스(Pub/Sub)**로 분리했습니다.

```
감지 에이전트                    RCA 에이전트                     알림 라우터
     │                              │                              │
     │  publish                     │  subscribe                   │  subscribe
     ▼                              ▼                              ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │                         Topic Bus                                    │
 │                                                                      │
 │   [anomaly.detected] ──→ RCA 에이전트가 수신, 근본원인 분석          │
 │   [rca.completed]    ──→ 분석 완료 이벤트                            │
 │   [alert.request]    ──→ 알림 라우터가 수신, 채널별 발송             │
 └──────────────────────────────────────────────────────────────────────┘
```

**감지 에이전트**는 이상을 발견하면 토픽에 계속 던지기만 합니다. **RCA 에이전트**가 그걸 받아서 ReAct 루프로 추가 DB 조회 → 근본원인 분석 → 결과를 DB에 저장하고, 알림을 요청합니다.

### 토픽 버스 모니터링

토픽별 발행/처리/실패 건수, 처리 시간, 최근 메시지 이력을 API로 확인할 수 있습니다.

```
GET /api/bus/metrics
```
```json
{
  "bus": {
    "running": true,
    "started_at": "2026-03-10T09:00:00",
    "queue_depth": 0,
    "subscriber_count": 3
  },
  "totals": {
    "published": 42,
    "delivered": 40,
    "failed": 2,
    "pending": 0
  },
  "topics": {
    "anomaly.detected": {
      "published": 15,
      "delivered": 14,
      "failed": 1,
      "pending": 0,
      "avg_processing_ms": 3200.5,
      "min_processing_ms": 1500.2,
      "max_processing_ms": 8100.0
    },
    "rca.completed": {
      "published": 14,
      "delivered": 14,
      "failed": 0,
      "pending": 0,
      "avg_processing_ms": 12.3
    },
    "alert.request": {
      "published": 13,
      "delivered": 12,
      "failed": 1,
      "pending": 0,
      "avg_processing_ms": 85.7
    }
  },
  "subscribers": {
    "anomaly.detected": ["rca_agent.handle_anomaly"],
    "alert.request": ["alert.router.handle_alert_request"]
  }
}
```

```
GET /api/bus/messages?limit=20
```
```json
{
  "messages": [
    {
      "topic": "anomaly.detected",
      "source": "detection_agent",
      "timestamp": "2026-03-10T14:35:12",
      "status": "delivered",
      "processing_ms": 3150.2,
      "anomaly_id": 42,
      "severity": "critical",
      "title": "LINE03 컨베이어 부하율 95% 초과"
    },
    {
      "topic": "rca.completed",
      "source": "rca_agent",
      "timestamp": "2026-03-10T14:35:15",
      "status": "delivered",
      "processing_ms": 8.1,
      "anomaly_id": 42,
      "severity": "critical",
      "title": "LINE03 컨베이어 부하율 95% 초과"
    }
  ]
}
```

### 메시지 큐 교체

현재는 `asyncio.Queue` 기반 인프로세스 버스이지만, `bus/topic.py`의 내부 구현만 교체하면 외부 MQ로 전환 가능합니다:

| MQ | 적합한 경우 |
|----|------------|
| **RabbitMQ** | 폐쇄망 내 설치 가능, 안정적 메시지 보장 필요 시 |
| **Kafka** | 대량 이벤트 스트림, 이력 보존, 다수 컨슈머 |
| **Redis Streams** | 이미 Redis 운용 중, 가벼운 큐 필요 시 |

인터페이스(`publish`, `subscribe`)가 동일하므로 **agent, alert 코드 수정 없이** 교체됩니다.

---

## 프로젝트 구조

```
fab-sentinel/
├── main.py                     # FastAPI + APScheduler + WebSocket 진입점
├── config.py                   # 환경설정 (DB, LLM, 스케줄, 알림)
├── requirements.txt            # 폐쇄망 사전 번들 패키지 (8개)
│
├── bus/
│   └── topic.py                # 토픽 버스 (Pub/Sub) — MQ 교체 지점
│
├── db/
│   ├── oracle.py               # Oracle 비동기 커넥션 풀 (oracledb thin)
│   ├── schema.sql              # DDL (sentinel_* 테이블 6개)
│   └── queries.py              # 공통 쿼리 (anomaly/rule/alert CRUD)
│
├── agent/
│   ├── llm_client.py           # OpenAI 호환 LLM 클라이언트 (httpx)
│   ├── tool_registry.py        # @registry.tool 데코레이터 → JSON Schema 자동 생성
│   ├── agent_loop.py           # ReAct 에이전트 루프 (최대 3라운드)
│   ├── prompts.py              # 시스템 프롬프트 (감지 / RCA / 상관)
│   ├── detection_agent.py      # 이상감지 에이전트 → anomaly.detected 발행
│   ├── rca_agent.py            # 원인분석 에이전트 → 토픽 구독 → 분석
│   └── tools/                  # DB 쿼리 도구 (~15개)
│       ├── logistics.py        # 컨베이어 부하, 반송 처리량, 병목존, AGV 가동률
│       ├── wip.py              # WIP 수준, 흐름 밸런스, 큐 길이, 에이징, 트렌드
│       └── equipment.py        # 설비 상태, 가동률, 비계획정지, PM, 알람 이력
│
├── rules/
│   ├── models.py               # Pydantic 모델 (RuleCreate, RuleUpdate)
│   └── engine.py               # 룰 평가 엔진 (threshold/delta/absence/llm)
│
├── detection/
│   ├── scheduler.py            # 감지 사이클 오케스트레이션
│   └── evaluator.py            # 규칙별 평가 → 에이전트 연동
│
├── correlation/
│   └── engine.py               # 상관관계 엔진 (시간·공간·인과)
│
├── alert/
│   ├── base.py                 # BaseAlertChannel ABC
│   ├── dashboard.py            # 대시보드 (DB + WebSocket 실시간)
│   ├── email_channel.py        # SMTP 이메일
│   ├── messenger.py            # 사내 메신저 웹훅
│   ├── router.py               # 알림 라우팅 (토픽 구독 → 채널 매핑)
│   └── escalation.py           # 에스컬레이션 (미확인 시 상위 알림)
│
├── lifecycle/
│   └── manager.py              # 이상 상태머신 (detected→acknowledged→resolved)
│
└── api/
    ├── rules.py                # 규칙 CRUD + 테스트 실행
    ├── anomalies.py            # 이상 목록 + 상태 변경 + 노트
    ├── correlations.py         # 상관그룹 조회
    ├── alerts.py               # 알림 라우팅 설정 + 이력
    ├── dashboard.py            # 대시보드 데이터 (개요, 타임라인, 히트맵)
    └── system.py               # 헬스체크, 수동 트리거, 통계
```

---

## AI 에이전트 상세

### ReAct 패턴

두 에이전트 모두 동일한 ReAct 루프(`agent_loop.py`)를 사용합니다:

```
1. 시스템 프롬프트 + 컨텍스트 → LLM 전달
2. LLM이 tool_call 요청 → DB 쿼리 실행 → 결과 반환
3. 최대 3라운드 반복
4. 최종 JSON 응답 반환
```

### 감지 에이전트 (detection_agent.py)

규칙 위반이 감지되면 LLM에게 실제 이상 여부를 판단시킵니다.

```json
// LLM 응답 형식
{
  "is_anomaly": true,
  "confidence": 0.85,
  "severity": "critical",
  "title": "LINE03 컨베이어 부하율 95% 초과",
  "analysis": "TFT 공정 LINE03 존의 부하율이...",
  "affected_entity": "LINE03-ZONE-A"
}
```

이상 확인 시 `anomaly.detected` 토픽에 발행 → RCA 에이전트로 넘어감.

### RCA 에이전트 (rca_agent.py)

토픽을 구독하고 있다가 이상을 받으면 근본원인을 분석합니다:

```json
// LLM 응답 형식
{
  "root_cause": "CELL 공정 EQ-201 비계획정지로 상류 WIP 적체",
  "evidence": [
    "EQ-201 14:23 DOWN (알람코드 A-501)",
    "LINE03 WIP 30분간 45% 증가",
    "컨베이어 부하율 동시 상승"
  ],
  "impact_scope": "TFT→CELL 라인 전체, 예상 2시간 영향",
  "suggested_actions": [
    "EQ-201 알람 코드 A-501 점검",
    "LINE03 WIP 우회 경로 검토",
    "PM 일정 앞당김 검토"
  ],
  "confidence": 0.78,
  "related_entities": ["EQ-201", "LINE03-ZONE-A", "LINE03-ZONE-B"]
}
```

### 도구 목록 (15개)

| 카테고리 | 도구 | 설명 |
|----------|------|------|
| 물류 | `get_conveyor_load` | 컨베이어 부하율(%) |
| 물류 | `get_transfer_throughput` | 반송 처리량 (moves/hr) |
| 물류 | `get_bottleneck_zones` | 병목 존 감지 |
| 물류 | `get_agv_utilization` | AGV/OHT 가동률 |
| 물류 | `get_zone_transfer_history` | 존별 반송 이력 |
| WIP | `get_wip_levels` | 공정별 WIP 수준 |
| WIP | `get_flow_balance` | 유입/유출 밸런스 |
| WIP | `get_queue_length` | 큐 길이 |
| WIP | `get_aging_lots` | 에이징 LOT |
| WIP | `get_wip_trend` | WIP 추이 트렌드 |
| 설비 | `get_equipment_status` | 설비 현재 상태 |
| 설비 | `get_equipment_utilization` | 설비 가동률 |
| 설비 | `get_unscheduled_downs` | 비계획정지 이력 |
| 설비 | `get_pm_schedule` | PM 일정 |
| 설비 | `get_equipment_alarms` | 설비 알람 이력 |

각 도구는 `@registry.tool` 데코레이터로 등록되며, OpenAI function calling JSON Schema가 자동 생성됩니다.

---

## 감지 규칙 시스템

### 규칙 유형 4가지

| 유형 | 동작 | 예시 |
|------|------|------|
| **threshold** | 값 > 임계치 | 컨베이어 부하율 > 90% |
| **delta** | 변화율 > 임계치 | WIP 1시간 변화율 > 30% |
| **absence** | 데이터 없음 | 30분간 반송 기록 없음 |
| **llm** | LLM에게 판단 위임 | 복합 패턴 감지 |

### 규칙 예시

```json
{
  "rule_name": "컨베이어 부하율 과부하",
  "category": "logistics",
  "subcategory": "conveyor",
  "query_template": "SELECT zone_id, ROUND(carrier_count/NULLIF(capacity,0)*100,1) AS load_pct FROM mes_conveyor_status ORDER BY load_pct DESC FETCH NEXT 1 ROWS ONLY",
  "check_type": "threshold",
  "threshold_op": ">",
  "warning_value": 85,
  "critical_value": 95,
  "eval_interval": 300,
  "llm_enabled": true
}
```

### 동적 추가

1. `POST /api/rules` → DB 저장
2. `POST /api/rules/{id}/test` → SQL 실행 결과만 확인
3. 다음 감지 사이클부터 자동 반영

---

## 감지 흐름

```
매 5분 (APScheduler)
  │
  ├─ 1. DB에서 활성 규칙 로드
  │
  ├─ 2. 규칙별 SQL 실행 + 임계치 비교
  │     ├─ threshold: 측정값 > 임계값?
  │     ├─ delta: 변화율 > 임계값?
  │     ├─ absence: 데이터 없음?
  │     └─ llm: LLM 판단 위임
  │
  ├─ 3. 위반 → 감지 에이전트 (llm_enabled인 경우)
  │     └─ ReAct: 추가 DB 조회 → 이상 확인 → anomaly.detected 토픽 발행
  │
  ├─ 4. RCA 에이전트 (토픽 구독)
  │     └─ ReAct: 추가 DB 조회 → 근본원인 분석 → DB 저장 → alert.request 발행
  │
  ├─ 5. 알림 라우터 (토픽 구독)
  │     └─ 라우팅 규칙에 따라 대시보드/이메일/메신저 발송
  │
  └─ 6. 상관관계 분석
        ├─ 시간적: 10분 내 동시 발생
        ├─ 공간적: 같은 라인/존
        └─ 인과적: TFT→CELL→MODULE 흐름
```

---

## 이상 상태머신

```
detected → acknowledged → investigating → resolved
    │            │               │
    └────────────┴───────────────┴──→ false_positive
```

---

## Oracle DB 스키마

6개 테이블:

| 테이블 | 용도 |
|--------|------|
| `sentinel_rules` | 감지 규칙 (SQL 쿼리 + 임계치) |
| `sentinel_anomalies` | 감지된 이상 + LLM 분석 결과 |
| `sentinel_correlations` | 상관 그룹 |
| `sentinel_alert_history` | 알림 발송 이력 |
| `sentinel_alert_routes` | 알림 라우팅 설정 |
| `sentinel_detection_cycles` | 감지 사이클 로그 |

DDL: `db/schema.sql`

---

## API 엔드포인트

| 영역 | 엔드포인트 | 설명 |
|------|-----------|------|
| 규칙 | `GET /api/rules` | 규칙 목록 |
| 규칙 | `POST /api/rules` | 규칙 생성 |
| 규칙 | `PATCH /api/rules/{id}` | 규칙 수정 |
| 규칙 | `DELETE /api/rules/{id}` | 규칙 삭제 |
| 규칙 | `POST /api/rules/{id}/test` | SQL 테스트 실행 |
| 이상 | `GET /api/anomalies` | 이상 목록 (필터: status) |
| 이상 | `GET /api/anomalies/active` | 활성 이상 |
| 이상 | `PATCH /api/anomalies/{id}/status` | 상태 변경 |
| 이상 | `POST /api/anomalies/{id}/notes` | 노트 추가 |
| 상관 | `GET /api/correlations` | 상관그룹 목록 |
| 상관 | `GET /api/correlations/{id}` | 상관그룹 + 이상 상세 |
| 알림 | `GET /api/alerts/routes` | 라우팅 규칙 |
| 알림 | `POST /api/alerts/routes` | 라우팅 추가 |
| 알림 | `PATCH /api/alerts/routes/{id}` | 라우팅 수정 |
| 알림 | `GET /api/alerts/history` | 발송 이력 |
| 대시보드 | `GET /api/dashboard/overview` | 현황 요약 |
| 대시보드 | `GET /api/dashboard/timeline` | 시간별 타임라인 |
| 대시보드 | `GET /api/dashboard/heatmap` | 카테고리×심각도 히트맵 |
| 시스템 | `GET /health` | 헬스체크 |
| 시스템 | `POST /api/detect/trigger` | 수동 감지 실행 |
| 시스템 | `POST /api/correlations/analyze` | 수동 상관분석 |
| 시스템 | `POST /api/escalations/check` | 수동 에스컬레이션 |
| 시스템 | `GET /api/stats` | 통계 |
| 버스 | `GET /api/bus/metrics` | 토픽별 발행/처리/실패 메트릭 |
| 버스 | `GET /api/bus/messages` | 최근 처리 메시지 목록 |
| 실시간 | `WS /ws/anomalies` | WebSocket 실시간 알림 |

---

## 알림 시스템

| 채널 | 구현 | 설정 |
|------|------|------|
| 대시보드 | WebSocket 실시간 | 기본 활성 |
| 이메일 | aiosmtplib | `SMTP_HOST`, `SMTP_PORT` 등 |
| 메신저 | HTTP 웹훅 | `MESSENGER_WEBHOOK_URL` |

**라우팅**: `sentinel_alert_routes` 테이블로 "카테고리 + 심각도 → 채널 + 수신자" 매핑

**에스컬레이션**: 미확인 이상은 `escalation_delay_min` 후 상위 채널로 재알림

---

## 설치 및 실행

### 환경변수 (.env)

```env
# Oracle
ORACLE_USER=sentinel
ORACLE_PASSWORD=password
ORACLE_DSN=dbhost:1521/FABDB

# LLM (OpenAI 호환 API)
LLM_BASE_URL=http://llm-server:8080/v1
LLM_API_KEY=your-key
LLM_MODEL=model-name

# 알림 (선택)
SMTP_HOST=smtp.fab.local
SMTP_PORT=587
SMTP_FROM=sentinel@fab.local
MESSENGER_WEBHOOK_URL=https://messenger.fab.local/webhook

# 스케줄
DETECTION_INTERVAL_SEC=300
```

### 설치 (폐쇄망)

```bash
# wheels 디렉토리에서 오프라인 설치
pip install --no-index --find-links=./wheels -r requirements.txt

# 또는 온라인
pip install -r requirements.txt
```

### DB 초기화

```bash
sqlplus sentinel/password@FABDB @db/schema.sql
```

### 실행

```bash
python main.py
# → http://0.0.0.0:8600
```

---

## 의존성

```
fastapi          # Web API
uvicorn          # ASGI 서버
httpx            # LLM API + 웹훅 호출
oracledb         # Oracle thin 모드 (Client 불필요)
apscheduler      # 주기적 감지 스케줄러
pydantic         # 데이터 검증
aiosmtplib       # 비동기 이메일
websockets       # WebSocket 실시간
python-dotenv    # 환경변수
```

8개 패키지. 폐쇄망에서는 wheels로 사전 번들.

---

## 기술 스택

- **Python 3.12+**
- **FastAPI** — 비동기 Web API
- **oracledb thin** — Oracle Instant Client 없이 순수 Python 연결
- **APScheduler** — 감지 주기 스케줄링
- **httpx** — LLM API 호출 + 웹훅
- **asyncio.Queue** — 인프로세스 토픽 버스 (MQ 교체 가능)
- **ReAct 패턴** — LLM + Tool Use 에이전트 루프
