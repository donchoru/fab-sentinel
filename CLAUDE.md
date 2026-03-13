# FAB 이상감지 — 반도체 공정 AI 이상감지 시스템

## 개요
- **목적**: 반도체 FAB 폐쇄망에서 물류/WIP/설비 이상을 AI가 감지
- **포트**: API 8600, NiceGUI 대시보드 3009
- **DB**: Oracle (운영) / SQLite (시뮬레이터)
- **LLM**: OpenAI 호환 API (사내 LLM 또는 Ollama)

## 아키텍처 (v3.0 — 이상감지 집중)
```
Detection Scheduler (매 5분)
  → 규칙 SQL 실행 → 임계치 비교
  → 위반 시 LLM 에이전트가 실제 이상 판단
  → DB INSERT (anomalies 테이블)
  → NiceGUI 대시보드에서 조회
```

### 추후 확장
- **알림**: 이상 발생 시 이메일/메신저 자동 알림
- **연쇄 이상감지**: 다건 이상의 시간/공간/인과 관계 분석
- **에스컬레이션**: 미확인 이상 자동 재알림 + SLA 관리

## 규칙 관리 — YAML 기반
- **`rules.yaml`이 규칙의 원본** (source of truth)
- 서버 시작 시: `rules.yaml` → DB 자동 동기화 (`rules/loader.py`)
- UI에서 규칙 추가/수정/삭제 → DB 변경 → `rules.yaml` 자동 갱신
- 시뮬레이터도 `rules.yaml`에서 규칙 로드

## 핵심 파일
| 파일 | 역할 |
|------|------|
| `rules.yaml` | **규칙 원본** — 이상감지 규칙 정의 |
| `rules/loader.py` | YAML ↔ DB 동기화 |
| `main.py` | FastAPI + APScheduler 진입점 |
| `agent/detection_agent.py` | 이상감지 (ReAct) → DB INSERT |
| `detection/evaluator.py` | 규칙 평가 → 에이전트 호출 |
| `detection/scheduler.py` | 감지 사이클 오케스트레이션 |
| `rules/engine.py` | threshold/delta/absence/llm 평가 |
| `api/rules.py` | 규칙 CRUD + AI 자연어 생성 + YAML 동기화 |
| `db/queries.py` | 모든 DB 쿼리 |
| `nicegui_app/main.py` | NiceGUI 5페이지 대시보드 |
| `api/users.py` | 사용자 CRUD + 로그인/회원가입 |

## DB 테이블 (sentinel_ 접두사 없음)
- `detection_rules` — 감지 규칙
- `anomalies` — 감지된 이상
- `users` — 사용자 계정
- `detection_cycles` — 감지 사이클 로그

## 실행

### 초기 설정
```bash
./setup.sh              # 자동 설정 (venv + pip + DB)
./setup.sh --with-demo  # 데모 시나리오 포함
./setup.sh --reset      # DB 재생성
```

### 서버 시작
```bash
# macOS / Linux
.venv/bin/python main.py --sqlite simulator.db       # API (:8600)
.venv/bin/python -m nicegui_app.main                  # 대시보드 (:3009)

# Windows (PowerShell)
.venv\Scripts\python.exe main.py --sqlite simulator.db   # API (:8600)
.venv\Scripts\python.exe -m nicegui_app.main              # 대시보드 (:3009)

# Windows (CMD)
.venv\Scripts\python.exe main.py --sqlite simulator.db
.venv\Scripts\python.exe -m nicegui_app.main
```

## 주의사항
- SQLite 시뮬레이터는 Oracle SQL을 `simulator/sql_compat.py`로 자동 변환
- Python 3.14에서 SQLite WAL + executescript 충돌 → 개별 execute 사용
- FETCH NEXT → LIMIT 변환 시 리터럴 숫자 + 바인드 변수 모두 처리 필요
