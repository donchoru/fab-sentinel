#!/bin/bash
# ============================================================
# FLOPI 초기 설정 스크립트
# FAB 이상감지 시스템 — SQLite 시뮬레이터 모드
#
# 사용법:
#   chmod +x setup.sh
#   ./setup.sh              # 기본 설정 (정상 데이터만)
#   ./setup.sh --with-demo  # 데모 데이터 포함 (이상 + RCA)
#   ./setup.sh --reset      # 기존 DB 삭제 후 재설정
# ============================================================

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

print_step() { echo -e "\n${BLUE}[$1/5]${NC} ${BOLD}$2${NC}"; }
print_ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}!${NC} $1"; }
print_err()  { echo -e "  ${RED}✗${NC} $1"; }

# ── 옵션 파싱 ──
WITH_DEMO=false
RESET=false
for arg in "$@"; do
    case $arg in
        --with-demo) WITH_DEMO=true ;;
        --reset)     RESET=true ;;
        --help|-h)
            echo "FLOPI 초기 설정"
            echo ""
            echo "사용법: ./setup.sh [옵션]"
            echo ""
            echo "옵션:"
            echo "  --with-demo  데모 데이터 포함 (이상 시나리오 + RCA 분석)"
            echo "  --reset      기존 DB 삭제 후 처음부터 재설정"
            echo "  --help       이 도움말 표시"
            exit 0
            ;;
    esac
done

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     FLOPI — FAB 이상감지 시스템 설정     ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"

# ── Step 1: Python 확인 ──
print_step 1 "Python 환경 확인"

PYTHON=""
for cmd in python3.11 python3.12 python3.13 python3; do
    if command -v $cmd &>/dev/null; then
        ver=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo $ver | cut -d. -f1)
        minor=$(echo $ver | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    print_err "Python 3.11 이상이 필요합니다."
    echo "  설치: https://www.python.org/downloads/"
    exit 1
fi
print_ok "Python: $($PYTHON --version)"

# ── Step 2: 가상환경 ──
print_step 2 "가상환경 설정"

if [ -d ".venv" ]; then
    print_ok "기존 가상환경 사용: .venv/"
else
    $PYTHON -m venv .venv
    print_ok "가상환경 생성: .venv/"
fi

# OS별 활성화
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
fi
print_ok "가상환경 활성화 완료"

# ── Step 3: 패키지 설치 ──
print_step 3 "패키지 설치"

pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
print_ok "$(pip list 2>/dev/null | wc -l | tr -d ' ')개 패키지 설치 완료"

# ── Step 4: DB 초기화 ──
print_step 4 "데이터베이스 초기화"

DB_FILE="simulator.db"
INIT_ARGS="--db $DB_FILE"

if [ "$RESET" = true ]; then
    INIT_ARGS="$INIT_ARGS --reset"
    print_warn "기존 DB 삭제 후 재생성합니다."
fi

if [ -f "$DB_FILE" ] && [ "$RESET" = false ]; then
    print_ok "기존 DB 사용: $DB_FILE (재설정: ./setup.sh --reset)"
else
    python init_db.py $INIT_ARGS
    print_ok "DB 초기화 완료: $DB_FILE"
    echo ""
    echo -e "  ${GREEN}생성된 테이블:${NC}"
    echo "    MES 테이블 14개 (컨베이어, 설비, WIP, LOT 등)"
    echo "    감지 테이블 5개 (규칙, 이상, 상관, 사이클, RCA)"
    echo "    사용자 테이블 1개"
    echo ""
    echo -e "  ${GREEN}초기 데이터:${NC}"
    echo "    정상 FAB 데이터 (컨베이어 40~70%, 설비 대부분 RUN)"
    echo "    감지 규칙 7개 (rules.yaml 동기화)"
    echo "    기본 관리자 계정 (admin / fab-admin)"
fi

# ── Step 5: 데모 데이터 ──
print_step 5 "데모 데이터"

if [ "$WITH_DEMO" = true ]; then
    python data_injector.py --db $DB_FILE --speed 100 --reset
    print_ok "데모 데이터 주입 완료"
    echo ""
    echo -e "  ${GREEN}주입된 시나리오:${NC}"
    echo "    1. 컨베이어 과부하 (LINE03-ZONE-A 부하율 96%)"
    echo "    2. 설비 비계획정지 (EQ-005 DOWN + 알람)"
    echo "    3. WIP 적체 (TFT 공정 170%)"
    echo "    4. 에이징 LOT (5건 24시간+ 체류)"
    echo "    5. AGV 장애 (3대 ERROR)"
    echo "    + AI 분석 결과 및 RCA 원인분석 데이터"
else
    print_warn "데모 데이터 없이 설정 완료 (추가하려면: ./setup.sh --with-demo)"
fi

# ── 완료 ──
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║            설정 완료!                    ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}실행 방법:${NC}"
echo ""
echo -e "  ${YELLOW}# macOS / Linux${NC}"
echo "  .venv/bin/python main.py --sqlite simulator.db --interval 60   # API"
echo "  .venv/bin/python -m nicegui_app.main                            # 대시보드"
echo ""
echo -e "  ${YELLOW}# Windows (PowerShell)${NC}"
echo '  .venv\Scripts\python.exe main.py --sqlite simulator.db --interval 60'
echo '  .venv\Scripts\python.exe -m nicegui_app.main'
echo ""
echo -e "${BOLD}접속:${NC}"
echo -e "  대시보드  →  ${GREEN}http://localhost:3009${NC}"
echo -e "  API 문서  →  ${GREEN}http://localhost:8600/docs${NC}"
echo ""
echo -e "${BOLD}로그인:${NC}"
echo -e "  관리자 계정  →  아이디: ${GREEN}admin${NC}  비밀번호: ${GREEN}fab-admin${NC}"
echo ""
echo -e "${BOLD}데모 데이터 주입 (나중에):${NC}"
echo "  python data_injector.py --speed 100 --reset"
echo ""
