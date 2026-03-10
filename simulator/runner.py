"""시뮬레이터 러너 — SQLite + 더미 데이터 + 시나리오 + 전체 파이프라인.

실행: python -m simulator.runner [--speed 2] [--port 8600]

1. SQLite로 Oracle 대체
2. MES 더미 테이블 생성 + 정상 데이터 시딩
3. 감지 규칙 등록
4. 시나리오 시작 (시간차로 이상 주입)
5. FastAPI 서버 + 감지 스케줄러 + RCA 폴러 시작
6. Streamlit 대시보드에서 확인 가능
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="FAB-SENTINEL Simulator")
    parser.add_argument("--speed", type=float, default=2.0, help="시나리오 속도 배율 (기본 2x)")
    parser.add_argument("--port", type=int, default=8600, help="API 포트 (기본 8600)")
    parser.add_argument("--db", type=str, default="simulator.db", help="SQLite DB 파일")
    parser.add_argument("--interval", type=int, default=30, help="감지 주기(초, 기본 30)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("simulator")

    # 1. SQLite 백엔드 초기화 (Oracle monkey-patch)
    from simulator.sqlite_backend import init_sqlite, get_conn
    if os.path.exists(args.db):
        os.remove(args.db)
        logger.info("Removed existing %s", args.db)
    init_sqlite(args.db)

    # 2. MES 테이블 생성
    schema_path = os.path.join(os.path.dirname(__file__), "mes_schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    conn = get_conn()
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    logger.info("MES + Sentinel tables created")

    # 3. 정상 데이터 시딩
    from simulator.seeder import seed_all
    seed_all()

    # 4. config 설정 변경
    from config import settings
    settings.scheduler.detection_interval_sec = args.interval
    settings.port = args.port

    # 5. 시나리오 + FastAPI 서버 시작
    import asyncio
    from contextlib import asynccontextmanager
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from agent.rca_agent import poll_and_analyze
    from detection.scheduler import run_detection_cycle
    from correlation.engine import analyze_correlations
    from alert.escalation import check_escalations
    from simulator.scenarios import ScenarioRunner

    # 도구 임포트 (데코레이터 등록)
    import agent.tools.logistics  # noqa: F401
    import agent.tools.wip  # noqa: F401
    import agent.tools.equipment  # noqa: F401

    scenario_runner = ScenarioRunner(speed=args.speed)
    scheduler = AsyncIOScheduler()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # RAG 지식베이스 초기화 (Milvus 없으면 자동 비활성화)
        if settings.rag.enabled:
            try:
                from rag.store import init_store
                from rag.loader import load_knowledge
                init_store(uri=settings.rag.milvus_uri, dim=settings.rag.embedding_dim)
                rag_count = await load_knowledge(
                    milvus_uri=settings.rag.milvus_uri,
                    dim=settings.rag.embedding_dim,
                )
                logger.info("RAG knowledge loaded: %d chunks", rag_count)
            except Exception:
                logger.warning("RAG init failed (Milvus not available?), continuing without RAG")
                settings.rag.enabled = False

        scheduler.add_job(run_detection_cycle, "interval", seconds=args.interval, id="detection")
        scheduler.add_job(poll_and_analyze, "interval", seconds=30, id="rca_poll")
        scheduler.add_job(analyze_correlations, "interval", seconds=args.interval, id="correlation")
        scheduler.add_job(check_escalations, "interval", seconds=60, id="escalation")
        scheduler.start()

        await scenario_runner.start()

        logger.info("=" * 60)
        logger.info("FAB-SENTINEL Simulator running")
        logger.info("  API: http://localhost:%d", args.port)
        logger.info("  Streamlit: streamlit run streamlit_app/app.py (포트 3009)")
        logger.info("  Detection interval: %d초", args.interval)
        logger.info("  RCA poll: 30초")
        logger.info("  Scenario speed: %.1fx", args.speed)
        logger.info("  Scenarios: 1분 컨베이어, 2분 설비, 3분 WIP, 4분 에이징, 5분 AGV")
        logger.info("=" * 60)

        yield

        await scenario_runner.stop()
        scheduler.shutdown(wait=False)

    app = FastAPI(title="FAB-SENTINEL (Simulator)", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.rules import router as rules_router
    from api.anomalies import router as anomalies_router
    from api.correlations import router as correlations_router
    from api.alerts import router as alerts_router
    from api.dashboard import router as dashboard_router
    from api.system import router as system_router

    app.include_router(rules_router)
    app.include_router(anomalies_router)
    app.include_router(correlations_router)
    app.include_router(alerts_router)
    app.include_router(dashboard_router)
    app.include_router(system_router)

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
