# FLOPI — FAB AI 이상감지 시스템

**반도체 FAB 폐쇄망 환경**에서 **물류 / 재공(WIP) / 설비** 이상을 AI가 주기적으로 감지하여 대시보드로 제공하는 시스템입니다.

> Oracle 없이 **SQLite + 더미 데이터**로 즉시 실행 가능합니다. 5분이면 전체 시스템을 체험할 수 있습니다.

---

## 왜 만들었나?

| 기존 문제 | FLOPI의 해결 |
|-----------|-------------|
| MES 데이터는 있지만 이상 감지는 수동 | **15개 데이터 도구 + 규칙 엔진**으로 자동 감지 |
| 단순 임계치만으로는 복합 이상 판단 불가 | **AI(LLM)가 데이터 패턴을 분석**하여 맥락적 판단 |
| 이상 발생 시 원인 추적에 시간 소요 | **RCA(근본원인분석)** AI가 원인·기여요인·근거·조치 제시 |
| 규칙 추가/변경마다 개발자 필요 | **대시보드에서 비개발자도 규칙 추가** (조건 감시 / AI 판단) |
| 이상 처리 이력 추적 불가 | **상태 관리 + 사용자 추적** (누가 언제 처리했는지) |

---

## 핵심 기능

### 1. 규칙 기반 이상감지

등록된 규칙을 **주기적으로 자동 평가**하여 이상을 감지합니다.

```
매 N초 (스케줄러)
  ├─ 활성 규칙 로드 (DB <- rules.yaml 동기화)
  ├─ 규칙별 도구 실행 + 평가 (asyncio.gather 병렬)
  │     ├─ threshold : 측정값 > 임계치?     (예: 컨베이어 부하율 > 90%)
  │     ├─ delta     : 변화율 > 임계치?     (예: WIP 1시간 변화율 > 30%)
  │     ├─ absence   : 데이터 없음?         (예: 30분간 반송 기록 없음)
  │     └─ llm       : AI에게 판단 위임     (예: 설비 복합 이상 패턴)
  └─ 위반 시 (llm_enabled) → LLM 1회 판단 → 이상 등록
```

### 2. AI 에이전트 — 자연어 이상감지

규칙에 `llm_enabled: true`가 설정되면, 임계치 위반 시 **LLM이 실제 이상인지 최종 판단**합니다.

```
[규칙 위반] 컨베이어 부하율 96% (임계치 90%)
    ↓
  도구 데이터 수집 (get_conveyor_load)
    ↓
  LLM에 전달 (규칙 + 측정값 + 데이터 + 프롬프트)
    ↓
  LLM 응답: { is_anomaly: true, confidence: 0.92, severity: "critical", ... }
    ↓
  confidence >= 0.7 → 이상 등록 (DB INSERT)
```

**멀티 라운드 에이전트**: LLM이 추가 도구를 호출할 수 있습니다 (최대 3라운드).
예: 컨베이어 이상 감지 → LLM이 `get_equipment_alarms("EQ-005")` 추가 호출 → 설비 알람 확인 후 최종 판단

### 3. RCA — AI 근본원인분석

감지된 이상에 대해 AI가 **근본 원인, 기여 요인, 분석 근거, 권장 조치**를 자동 생성합니다.

```
근본 원인:  EQ-005 베어링 마모 → 비계획정지 → 캐리어 적체
기여 요인:  PM 2주 지연, 진동 경고 미조치, 윤활유 교체 누락
분석 근거:  mes_equipment_alarms: A-501 알람, mes_pm_schedule: 2주 경과
권장 조치:  1. 베어링 즉시 교체  2. 유사 설비 선제 점검  3. PM 자동 알림 도입
신뢰도:    92%
```

### 4. 대시보드 — 5개 페이지

| 페이지 | 기능 |
|--------|------|
| **대시보드** | KPI 카드 (활성 위험/경고/24h 이상/활성 규칙), 상태 분포 차트, 최근 이상 타임라인, 수동 감지 |
| **이상 목록** | 상태별 필터, 좌우 분할 (목록 + 상세), AI 분석/제안, RCA 카드, 상태 전이 |
| **규칙 관리** | 2탭 추가 (조건 감시 / AI 판단), 도구 카탈로그 15개, 테스트 실행, 작성자 추적 |
| **감지 로그** | 감지 사이클 이력 (규칙 수, 이상 수, 소요시간), 상태별 이상 통계 |
| **사용자 관리** | 사용자 CRUD, 역할 관리 (admin만 접근 가능) |

### 5. 사용자 관리 + 역할 기반 접근제어

| 역할 | 권한 |
|------|------|
| **admin** (관리자) | 모든 기능: 규칙 관리, 이상 처리, 사용자 관리, 수동 감지 |
| **operator** (운영자) | 규칙 생성/수정, 이상 상태 변경, 수동 감지 (**사용자 관리 불가**) |
| **viewer** (열람자) | 읽기 전용: 대시보드, 이상 목록, 규칙 목록, 감지 로그 열람 |

- 규칙 생성/수정 시 **작성자가 자동 기록**됩니다.
- 이상 해결 시 **처리자 이름이 기록**됩니다.

### 6. 규칙 생성 — 2가지 방식

#### 방식 1: 조건 감시 (Threshold)

도구를 선택하고 **감시 컬럼 + 경고/위험 임계치**를 설정합니다.

```
규칙명: "컨베이어 부하율 과부하"
  도구:   get_conveyor_load (컨베이어 부하율)
  컬럼:   load_pct (부하율 %)
  조건:   > 85 (경고) / > 95 (위험)
```

| 감시 유형 | 동작 | 예시 |
|-----------|------|------|
| **임계치 초과** | 측정값 > 임계치 | 부하율 > 90% |
| **변화율 초과** | 변화율의 절대값 > 임계치 | WIP 변화율 > 30% |
| **데이터 부재** | 데이터 0건 | 30분간 반송 기록 없음 |

#### 방식 2: AI 판단 (LLM)

도구를 선택하고 **자연어로 이상 조건을 설명**합니다. AI가 매 사이클마다 판단합니다.

```
규칙명: "설비 상태 복합 이상"
  도구:  get_equipment_status (설비 현재 상태)
  조건:  "같은 라인에서 2대 이상 동시 DOWN이면 이상.
          PM 상태는 정상이니 제외해. DOWN인데 알람이 없으면 더 위험해."
```

> **팁**: 숫자 비교는 "조건 감시"에 맡기고, **패턴 인식 / 맥락 판단**처럼 코드로 표현하기 어려운 조건에 "AI 판단"을 사용하세요.

---

## 데이터 도구 — 15개

규칙 평가 및 AI 에이전트가 사용하는 데이터 조회 도구입니다.

### 물류 (Logistics) — 5개

| 도구 | 설명 | 주요 컬럼 |
|------|------|-----------|
| `get_conveyor_load` | 존별 컨베이어 부하율(%) | `load_pct`, `carrier_count`, `capacity` |
| `get_transfer_throughput` | 라인별 반송 처리량 | `moves_1h`, `avg_time_sec` |
| `get_bottleneck_zones` | 대기시간 초과 병목 존 | `avg_wait`, `max_wait`, `carrier_count` |
| `get_agv_utilization` | AGV/OHT 상태별 대수 및 비율 | `pct`, `count` |
| `get_zone_transfer_history` | 존별 최근 반송 이력 | — |

### 재공 (WIP) — 5개

| 도구 | 설명 | 주요 컬럼 |
|------|------|-----------|
| `get_wip_levels` | 공정별 WIP 목표 대비 비율 | `wip_ratio_pct`, `current_wip`, `target_wip` |
| `get_flow_balance` | 공정별 유입/유출 밸런스 | `net_wip`, `inflow`, `outflow` |
| `get_queue_length` | 스텝별 대기 LOT 수 | `queue_count`, `avg_wait_min`, `max_wait_min` |
| `get_aging_lots` | 기준시간 초과 장기 체류 LOT | `hours_in_step`, `_count` |
| `get_wip_trend` | 시간별 WIP 변화 트렌드 | `total_wip` |

### 설비 (Equipment) — 5개

| 도구 | 설명 | 주요 컬럼 |
|------|------|-----------|
| `get_equipment_status` | 설비 현재 상태 (RUN/IDLE/DOWN/PM) | `_count` |
| `get_equipment_utilization` | 설비 가동률(%) | `utilization_pct`, `down_minutes` |
| `get_unscheduled_downs` | 비계획정지 이력 | `down_min`, `_count` |
| `get_pm_schedule` | 예방보전(PM) 일정 및 지연 | `_count` |
| `get_equipment_alarms` | 설비 알람 이력 | `_count` |

---

## 이상 상태 흐름

```
[규칙 위반 감지]
      ↓
  ┌─────────┐    처리 시작    ┌──────────┐    조치 완료    ┌────────┐
  │ 감지됨   │ ────────────→ │ 처리중    │ ────────────→ │ 해결    │
  │ detected │               │in_progress│               │resolved│
  └─────────┘               └──────────┘               └────────┘
      │                                                     ↑
      └─────────── 즉시 해결 ──────────────────────────────┘
```

| 상태 | 설명 |
|------|------|
| **감지됨** (detected) | AI가 이상을 감지하여 등록한 상태 |
| **처리중** (in_progress) | 담당자가 확인하고 조치 중인 상태 |
| **해결** (resolved) | 조치 완료 (처리자 이름 + 시각 기록) |

---

## 빠른 시작 (5분)

### 요구사항

- **Python 3.12 이상** (3.12 / 3.13 / 3.14 모두 가능)
- 운영체제: Windows / macOS / Linux
- Oracle DB 불필요 (SQLite 시뮬레이터 모드)

### 자동 설정 (권장)

```bash
# 저장소 클론
git clone https://github.com/donchoru/fab-sentinel.git
cd fab-sentinel

# 자동 설정 (가상환경 + 패키지 + DB + 기본 계정)
chmod +x setup.sh
./setup.sh --with-demo
```

`--with-demo` 옵션은 5개 이상 시나리오 + RCA 분석 데이터를 자동 주입합니다.

### 수동 설정

```bash
# 1. 가상환경 생성 + 패키지 설치
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. DB 초기화 (테이블 + 정상 데이터 + 규칙 + 관리자 계정)
python init_db.py

# 3. 데모 데이터 주입 (선택)
python data_injector.py --speed 100 --reset
```

---

## 실행

**터미널 2개**를 열어 각각 실행합니다.

### 터미널 1 — API 서버

```bash
source .venv/bin/activate
python main.py --sqlite simulator.db --interval 60
```

```
FAB 이상감지 시스템 running
  Mode: SQLite (simulator.db)
  API: http://localhost:8600
  Detection interval: 60초
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--sqlite` | — | SQLite DB 파일 경로 (없으면 Oracle 모드) |
| `--port` | `8600` | API 포트 |
| `--interval` | `300` | 감지 주기 (초). 데모 시 `60` 권장 |

### 터미널 2 — 대시보드

```bash
source .venv/bin/activate
python -m nicegui_app.main
```

브라우저에서 **http://localhost:3009** 접속.

### 로그인

비로그인 상태에서 좌측 사이드바에 로그인 폼이 표시됩니다.

| 항목 | 값 |
|------|-----|
| 아이디 | `admin` |
| 비밀번호 | `fab-admin` |
| 역할 | 관리자 (admin) |

> `setup.sh`로 초기화 시 기본 관리자 계정이 자동 생성됩니다.

### 회원가입

로그인 폼 하단의 **"회원가입"** 버튼으로 자가 가입이 가능합니다.
- 가입 시 기본 역할: **viewer** (읽기 전용)
- 관리자가 `/users` 페이지에서 역할을 변경할 수 있습니다 (operator, admin)

> 로그인 후 좌측에 사용자 이름 + 역할 뱃지가 표시됩니다.
> admin 계정은 "👥 사용자 관리" 메뉴가 추가로 나타납니다.

---

## 데모 체험 가이드

설정 후 아래 순서로 시스템을 체험해보세요.

### Step 1. 대시보드 확인

로그인 후 메인 대시보드에서:
- **KPI 카드**: 활성 위험/경고/24시간 이상/활성 규칙 수 확인
- **상태 분포 차트**: 감지됨/처리중/해결 비율
- **최근 이상 타임라인**: 최근 5건의 이상 요약

### Step 2. 이상 목록 탐색

좌측 네비에서 "🚨 이상 목록" 클릭:
- 상단 필터로 상태별 조회 (감지됨 / 처리중 / 해결)
- 테이블에서 행 클릭 → 우측에 상세 정보
- **AI 분석**: LLM이 작성한 이상 원인 분석
- **AI 제안**: 권장 조치 목록
- **RCA 카드**: 근본 원인, 기여 요인, 분석 근거, 권장 조치, 신뢰도

### Step 3. 이상 처리

이상 상세에서 (admin/operator):
- "🔧 처리 시작" → 상태가 "처리중"으로 변경
- "✅ 해결" → 상태가 "해결"로 변경 (처리자 이름 자동 기록)

### Step 4. 규칙 관리

좌측 네비에서 "⚙️ 규칙 관리" 클릭:
- 기존 7개 규칙 확인 (목록 테이블)
- 행 클릭 → 우측에 상세 (데이터 소스, 임계치, LLM 설정, 작성자)
- "🧪 테스트" → 규칙의 데이터 소스를 즉시 실행하여 결과 확인
- "➕ 새 규칙 추가" → 조건 감시 또는 AI 판단 탭에서 규칙 추가

### Step 5. 수동 감지 실행

대시보드 하단의 "⚡ 수동 감지 실행" 버튼 클릭:
- 모든 활성 규칙을 즉시 평가
- 결과: "N개 규칙, M개 이상 (Xms)" 알림

### Step 6. 사용자 관리

좌측 네비에서 "👥 사용자 관리" 클릭 (admin만):
- 현재 사용자 목록 확인
- "➕ 새 사용자 추가" → operator/viewer 계정 생성
- 행 클릭 → 역할 변경, 비밀번호 변경, 계정 비활성화/삭제

---

## 이상 데이터 주입기

정상 데이터만으로는 이상이 감지되지 않으므로, **시나리오 기반 데이터 주입기**를 제공합니다.

```bash
python data_injector.py [옵션]
```

### 5개 이상 시나리오

| 순서 | 시나리오 | 주입 내용 | 관련 규칙 |
|------|---------|----------|----------|
| 1 | **컨베이어 과부하** | LINE03-ZONE-A 부하율 96%로 변경 | 컨베이어 부하율 과부하 |
| 2 | **설비 비계획정지** | EQ-005 DOWN + CRITICAL 알람 + 비계획정지 이력 | 설비 비계획정지 발생 |
| 3 | **WIP 적체** | TFT-03 공정 WIP 170%로 급등 + 큐 대기 급증 | WIP 목표 초과 |
| 4 | **에이징 LOT** | 5개 LOT가 24~48시간 동일 공정 체류 | 에이징 LOT 발생 |
| 5 | **AGV 장애** | AGV 3대 ERROR 상태 + 알람 | AGV 가동률 저하 |

주입 후 **이상 + RCA 가상 데이터 7건**도 함께 생성됩니다 (해결 사례 2건 포함).

### 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--db` | `simulator.db` | SQLite DB 파일 |
| `--speed` | `2` | 속도 배율 (100 = 거의 즉시) |
| `--reset` | — | 이전 주입 데이터 초기화 후 재주입 |
| `--loop` | — | 주입 후 상황 점진적 악화 반복 (Ctrl+C로 중지) |

```bash
# 빠르게 테스트
python data_injector.py --speed 100

# 깨끗하게 재주입
python data_injector.py --reset --speed 100

# 라이브 데모 (30초 간격으로 시나리오 주입 + 악화 반복)
python data_injector.py --reset --speed 2 --loop
```

---

## 아키텍처

### 시스템 구성

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│   NiceGUI 대시보드 (:3009)   │     │    FastAPI 서버 (:8600)       │
│                             │     │                              │
│  대시보드 | 이상 | 규칙       │◄───►│  REST API                    │
│  로그 | 사용자               │httpx│  APScheduler (매 N초)         │
│                             │     │  Rule Engine (4가지 평가)      │
│  다크/라이트 테마             │     │  Detection Agent (LLM 판단)   │
│  역할 기반 접근제어           │     │  RCA Agent (원인분석)         │
└─────────────────────────────┘     └──────────┬───────────────────┘
                                               │
                              ┌────────────────┼────────────────┐
                              ▼                ▼                ▼
                     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                     │ 물류 도구 5개 │ │ 재공 도구 5개 │ │ 설비 도구 5개 │
                     │ conveyor     │ │ wip_levels   │ │ equip_status │
                     │ throughput   │ │ flow_balance │ │ utilization  │
                     │ bottleneck   │ │ queue_length │ │ downs        │
                     │ AGV          │ │ aging_lots   │ │ PM           │
                     │ history      │ │ wip_trend    │ │ alarms       │
                     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                            └────────────────┼────────────────┘
                                             ▼
                              ┌──────────────────────────┐
                              │  Oracle (운영) / SQLite   │
                              │                          │
                              │  MES 테이블 14개          │
                              │  감지 테이블 5개          │
                              │  사용자 테이블 1개        │
                              │  rules.yaml (양방향 동기화)│
                              └──────────────────────────┘
```

### 감지 사이클 흐름

```
스케줄러 (매 N초)
  │
  ├─ DB에서 활성 규칙 N개 로드
  │
  ├─ asyncio.gather: N개 규칙 병렬 평가
  │     │
  │     ├─ 규칙 1: get_conveyor_load() → 부하율 96% → 임계치 95% 초과!
  │     │     └─ llm_enabled → LLM 판단 → "이상 확정 (confidence 0.92)"
  │     │           └─ DB INSERT (anomalies)
  │     │
  │     ├─ 규칙 2: get_wip_levels() → WIP 95% → 임계치 130% 이하 → 정상
  │     │
  │     └─ 규칙 N: ...
  │
  └─ 사이클 로그 저장 (규칙 수, 이상 수, 소요시간)
```

---

## 프로젝트 구조

```
fab-sentinel/
├── setup.sh                        # 자동 설정 스크립트 (1회 실행)
├── init_db.py                      # DB 초기화 (테이블 + 시딩 + 규칙 + 관리자)
├── main.py                         # FastAPI + APScheduler 진입점
├── data_injector.py                # 이상 데이터 주입기
├── config.py                       # 환경설정 (DB, LLM, 스케줄)
├── rules.yaml                      # 규칙 원본 (Source of Truth)
├── requirements.txt
│
├── agent/                          # AI 에이전트
│   ├── llm_client.py               # OpenAI 호환 LLM 클라이언트
│   ├── tool_registry.py            # @registry.tool → JSON Schema 자동 생성
│   ├── agent_loop.py               # 에이전트 루프 (멀티 라운드)
│   ├── prompts.py                  # 시스템 프롬프트
│   ├── detection_agent.py          # 이상감지: 도구 데이터 → LLM 판단 → DB
│   ├── rca_agent.py                # 원인분석: 이상 → 근본원인 + 조치
│   └── tools/                      # 데이터 조회 도구 (15개)
│       ├── logistics.py            # 컨베이어, 반송, 병목존, AGV
│       ├── wip.py                  # WIP, 흐름, 큐, 에이징, 트렌드
│       └── equipment.py            # 설비, 가동률, 정지, PM, 알람
│
├── rules/                          # 규칙 시스템
│   ├── models.py                   # Pydantic 모델 (RuleCreate/Update/Response)
│   ├── engine.py                   # 규칙 평가 (threshold/delta/absence/llm)
│   └── loader.py                   # YAML <-> DB 양방향 동기화
│
├── detection/                      # 감지 오케스트레이션
│   ├── scheduler.py                # 감지 사이클 (asyncio.gather 병렬)
│   └── evaluator.py                # 규칙별 평가 → 에이전트 연동
│
├── db/                             # 데이터베이스
│   ├── oracle.py                   # Oracle 비동기 커넥션 풀
│   ├── schema.sql                  # Oracle DDL
│   └── queries.py                  # 공통 쿼리 (규칙, 이상, 사용자, RCA, 사이클)
│
├── api/                            # REST API
│   ├── rules.py                    # 규칙 CRUD + 도구 카탈로그 + 테스트
│   ├── anomalies.py                # 이상 목록 + 상태 변경
│   ├── users.py                    # 사용자 CRUD + 로그인
│   ├── dashboard.py                # 대시보드 데이터
│   ├── rca.py                      # RCA 조회
│   └── system.py                   # 헬스체크, 수동 트리거, 통계
│
├── nicegui_app/                    # NiceGUI 대시보드
│   ├── main.py                     # 앱 진입점 + 레이아웃 + 로그인
│   ├── api_client.py               # httpx 비동기 API 래퍼
│   ├── theme.py                    # 테마 (다크/라이트, 색상, CSS)
│   ├── components.py               # 재사용 컴포넌트 (KPI, 뱃지, 차트)
│   └── pages/
│       ├── dashboard.py            # 대시보드 페이지
│       ├── anomalies.py            # 이상 목록 페이지
│       ├── rules.py                # 규칙 관리 페이지
│       ├── logs.py                 # 감지 로그 페이지
│       └── users.py                # 사용자 관리 페이지
│
├── simulator/                      # SQLite 시뮬레이터
│   ├── sqlite_backend.py           # Oracle → SQLite 몽키패치
│   ├── sql_compat.py               # Oracle SQL → SQLite 자동 변환
│   ├── mes_schema.sql              # MES + 감지 + 사용자 테이블 (SQLite)
│   ├── seeder.py                   # 정상 상태 더미 데이터 생성
│   └── scenarios.py                # 이상 시나리오 5개
│
└── simulator/                      # SQLite 시뮬레이터
```

---

## DB 테이블

### 감지 시스템 테이블 (5개)

| 테이블 | 용도 |
|--------|------|
| `users` | 사용자 계정 (아이디, 비밀번호, 역할, 활성 상태) |
| `detection_rules` | 감지 규칙 (도구 + 임계치 + LLM 프롬프트 + 작성자) |
| `anomalies` | 감지된 이상 + AI 분석 + 처리자 |
| `rca_analyses` | RCA 분석 결과 (근본원인, 기여요인, 조치, 신뢰도) |
| `detection_cycles` | 감지 사이클 로그 (소요시간, 규칙 수, 이상 수) |

### MES 테이블 (14개)

| 영역 | 테이블 | 용도 |
|------|--------|------|
| 물류 | `mes_conveyor_status` | 존별 컨베이어 현재 부하 |
| 물류 | `mes_transfer_log` | 반송 이력 (출발 → 도착, 소요시간) |
| 물류 | `mes_carrier_queue` | 대기 중인 캐리어 큐 |
| 물류 | `mes_vehicle_status` | AGV/OHT 상태 (RUN/IDLE/ERROR/CHARGING) |
| 재공 | `mes_wip_summary` | 공정/스텝별 현재 WIP vs 목표 |
| 재공 | `mes_wip_flow` | WIP 유입/유출 흐름 |
| 재공 | `mes_queue_status` | 스텝별 대기 LOT 수 + 대기시간 |
| 재공 | `mes_lot_status` | LOT별 현재 위치 + 체류시간 |
| 재공 | `mes_wip_snapshot` | 시간별 WIP 스냅샷 (트렌드) |
| 설비 | `mes_equipment_status` | 설비 현재 상태 |
| 설비 | `mes_equipment_history` | 설비 상태 이력 |
| 설비 | `mes_down_history` | 비계획정지 이력 |
| 설비 | `mes_pm_schedule` | PM 일정 |
| 설비 | `mes_equipment_alarms` | 설비 알람 이력 |

---

## API 엔드포인트

### 규칙

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/rules` | 규칙 목록 (`?include_disabled=true` 전체) |
| `GET` | `/api/rules/{id}` | 규칙 상세 |
| `POST` | `/api/rules` | 규칙 생성 |
| `PATCH` | `/api/rules/{id}` | 규칙 수정 |
| `DELETE` | `/api/rules/{id}` | 규칙 삭제 |
| `POST` | `/api/rules/{id}/test` | 도구 테스트 실행 |
| `GET` | `/api/rules/tools/catalog` | 도구 카탈로그 (15개) |

### 이상

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/anomalies` | 이상 목록 (`?status=detected&limit=100`) |
| `GET` | `/api/anomalies/active` | 활성 이상 (detected + in_progress) |
| `PATCH` | `/api/anomalies/{id}/status` | 상태 변경 |

### 사용자

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/users` | 사용자 목록 (비밀번호 제외) |
| `POST` | `/api/users` | 사용자 생성 |
| `PATCH` | `/api/users/{id}` | 사용자 수정 |
| `DELETE` | `/api/users/{id}` | 사용자 삭제 |
| `POST` | `/api/users/login` | 로그인 (username + password → role 반환) |
| `POST` | `/api/users/register` | 자가 회원가입 (기본 viewer 역할) |

### RCA

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/rca/{anomaly_id}` | 이상별 RCA 조회 |
| `GET` | `/api/rca` | RCA 목록 |

### 대시보드 / 시스템

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/dashboard/overview` | 현황 요약 (KPI + 최근 사이클) |
| `GET` | `/api/dashboard/timeline` | 타임라인 (`?hours=24`) |
| `GET` | `/api/dashboard/heatmap` | 히트맵 |
| `GET` | `/api/stats` | 통계 (활성 규칙 수 등) |
| `GET` | `/health` | 헬스체크 |
| `POST` | `/api/detect/trigger` | 수동 감지 실행 |

> API 문서 자동 생성: **http://localhost:8600/docs** (Swagger UI)

---

## LLM 설정

OpenAI 호환 API를 사용하므로 **Gemini / 사내 LLM / Ollama** 등 어떤 LLM이든 연결 가능합니다.

```bash
# Gemini (기본)
export LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
export LLM_API_KEY=your-gemini-key
export LLM_MODEL=gemini-2.0-flash

# 사내 LLM 서버
export LLM_BASE_URL=http://llm-server:8080/v1
export LLM_API_KEY=your-key
export LLM_MODEL=your-model-name

# Ollama (로컬)
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_API_KEY=unused
export LLM_MODEL=qwen2.5:14b
```

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `LLM_BASE_URL` | Gemini OpenAI 엔드포인트 | `/v1/chat/completions` 지원 URL |
| `LLM_API_KEY` | — | API 인증 키 |
| `LLM_MODEL` | `gemini-2.0-flash` | 모델명 |

> **LLM 없이도 기본 동작합니다.** `llm_enabled: false` 규칙은 순수 규칙 엔진으로 평가되므로 API 키 없이도 이상을 감지합니다. LLM은 더 정교한 판단이 필요한 규칙에만 사용됩니다.

---

## 운영 모드 (Oracle)

SQLite 시뮬레이터 대신 실제 Oracle MES DB에 연결합니다.

```bash
export ORACLE_USER=fab
export ORACLE_PASSWORD=password
export ORACLE_DSN=dbhost:1521/FABDB

# --sqlite 플래그 없이 실행 → Oracle 모드
python main.py
python -m nicegui_app.main
```

`simulator/sqlite_backend.py`가 `db.oracle` 모듈을 SQLite로 교체(monkey-patch)하는 방식이므로, **도구/쿼리/에이전트 코드는 Oracle과 SQLite 모두 동일합니다.**

---

## YAML 규칙 관리

`rules.yaml`이 규칙의 **원본(Source of Truth)**입니다.

```yaml
rules:
  - name: 컨베이어 부하율 과부하
    category: logistics
    check_type: threshold
    source_type: tool
    tool: get_conveyor_load
    tool_column: load_pct
    threshold_op: ">"
    warning_value: 85
    critical_value: 95
    llm_enabled: true
    llm_prompt: "컨베이어 부하율이 높습니다. 해당 존의 반송 이력과 병목 여부를 확인하세요."
    enabled: true
```

- **서버 시작 시**: `rules.yaml` → DB 자동 동기화
- **UI에서 규칙 변경 시**: DB 변경 → `rules.yaml` 자동 갱신

직접 `rules.yaml`을 편집해도 되고, 대시보드에서 추가/수정해도 됩니다.

---

## 기술 스택

| 영역 | 기술 | 설명 |
|------|------|------|
| **언어** | Python 3.12+ | 비동기(asyncio) 기반 |
| **API 서버** | FastAPI + Uvicorn | 비동기 Web API (포트 8600) |
| **대시보드** | NiceGUI + Plotly | 5페이지 SPA 대시보드 (포트 3009) |
| **DB (운영)** | Oracle (oracledb thin) | Instant Client 없이 순수 Python 연결 |
| **DB (개발)** | SQLite | Oracle SQL → SQLite 자동 변환 |
| **LLM** | OpenAI 호환 API | Gemini / 사내 LLM / Ollama |
| **스케줄러** | APScheduler | 감지 주기 스케줄링 |
| **AI 패턴** | Tool + LLM + 멀티라운드 | 도구 데이터 → LLM 판단 (최대 3라운드) |
| **인증** | SHA-256 + Session | 역할 기반 접근제어 (admin/operator/viewer) |

---

## FAQ

### Q. LLM API 키가 없으면 사용할 수 없나요?

아닙니다. `llm_enabled: false` 규칙은 순수 규칙 엔진으로 동작합니다. LLM 없이도 임계치 기반 이상감지는 정상 동작합니다.

### Q. 기존 Oracle MES DB에 테이블을 추가해야 하나요?

MES 테이블은 **기존 테이블을 그대로 사용**합니다. `detection_rules`, `anomalies`, `users` 등 감지 시스템 테이블만 추가하면 됩니다 (`db/schema.sql` 참고).

### Q. 규칙을 추가하려면 개발자가 필요한가요?

아닙니다. 대시보드에서 **비개발자도 규칙을 추가**할 수 있습니다. "조건 감시" 탭에서 도구 선택 → 임계치 설정, 또는 "AI 판단" 탭에서 자연어로 조건을 설명하면 됩니다.

### Q. 감지 주기를 변경하려면?

`python main.py --sqlite simulator.db --interval 30` 처럼 `--interval` 옵션으로 초 단위 설정 가능합니다. 기본 300초(5분).

### Q. 다크 모드 / 라이트 모드 전환은?

좌측 사이드바 하단의 "☀️ 라이트 모드" 또는 "🌙 다크 모드" 버튼으로 전환됩니다.

---

## TODO — 추후 확장

| 우선순위 | 기능 | 설명 |
|----------|------|------|
| **P1** | **알림 연동** | 이상 발생 시 이메일/Teams/텔레그램 자동 알림. 심각도별 채널 분리 |
| **P1** | **Oracle 연결** | 실제 MES Oracle DB 연동 테스트. `db/oracle.py` + 환경변수 설정 |
| **P2** | **연쇄 이상감지** | 다건 이상의 시간·공간·인과 관계 분석. 동시 발생 패턴 그룹핑 |
| **P2** | **에스컬레이션** | 미확인 이상 자동 재알림 + SLA 기반 단계별 알림 |
| **P2** | **대시보드 차트 강화** | 히트맵, 설비별 가동률 트렌드, WIP 흐름 Sankey 다이어그램 |
| **P3** | **RAG 전문지식** | 설비 알람코드·과거 사고사례를 벡터 DB에 저장 → LLM 판단 시 참조 |
| **P3** | **감사 로그** | 규칙 변경/사용자 변경/이상 처리 전체 이력 추적 |
| **P3** | **API 인증** | JWT 토큰 기반 API 인증 (현재는 세션 기반 대시보드 인증만) |
