"""데이터 주입기 — 이상 시나리오를 시간차로 DB에 주입.

실행: python data_injector.py [--db simulator.db] [--speed 2]

시나리오 (60초 간격, --speed로 조절):
  1. 컨베이어 과부하  (LINE03-ZONE-A 부하율 96%)
  2. 설비 비계획정지  (EQ-005 DOWN + 알람)
  3. WIP 적체         (TFT 공정 170%)
  4. 에이징 LOT       (5개 LOT 24시간+ 체류)
  5. AGV 장애         (3대 ERROR)

--loop: 주입 후 상황 점진적 악화 반복
--reset: 이전 주입 데이터 초기화 후 재주입
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time


def _reset_injected_data(logger) -> None:
    """이전 주입 데이터를 정리하고 정상 상태로 복원."""
    from simulator.sqlite_backend import get_conn

    conn = get_conn()

    # 큐 데이터 (시나리오가 INSERT한 것) 삭제
    conn.execute("DELETE FROM mes_carrier_queue WHERE carrier_id LIKE 'CR-05%'")

    # 설비 정상 복원
    conn.execute("UPDATE mes_equipment_status SET status = 'RUN', last_status_change = NULL WHERE equipment_id = 'EQ-005'")

    # 비계획정지 + 알람 (시나리오가 INSERT한 것) 삭제
    conn.execute("DELETE FROM mes_down_history WHERE equipment_id = 'EQ-005' AND down_code = 'A-501'")
    conn.execute("DELETE FROM mes_equipment_alarms WHERE equipment_id = 'EQ-005'")
    conn.execute("DELETE FROM mes_equipment_alarms WHERE equipment_id LIKE 'AGV-%' AND alarm_code = 'V-101'")

    # WIP 정상 복원
    conn.execute("UPDATE mes_wip_summary SET current_wip = CAST(target_wip * 0.9 AS INTEGER) WHERE step_id IN ('TFT-03', 'TFT-04')")
    conn.execute("UPDATE mes_queue_status SET queue_count = 10, avg_wait_min = 20, max_wait_min = 45 WHERE step_id = 'TFT-03'")

    # 시나리오 WIP flow/snapshot 삭제
    conn.execute("DELETE FROM mes_wip_flow WHERE process = 'TFT' AND step_id = 'TFT-03' AND qty > 14")
    conn.execute("DELETE FROM mes_wip_snapshot WHERE process = 'TFT' AND wip_count > 500")

    # 에이징 LOT 삭제
    conn.execute("DELETE FROM mes_lot_status WHERE lot_id LIKE 'LOT-99%'")

    # AGV 정상 복원
    conn.execute("UPDATE mes_vehicle_status SET status = 'RUN' WHERE vehicle_id IN ('AGV-003', 'AGV-007', 'AGV-011')")

    # 감지된 이상 초기화
    conn.execute("DELETE FROM anomalies")
    conn.execute("DELETE FROM detection_cycles")

    conn.commit()
    logger.info("이전 주입 데이터 초기화 완료")


def main():
    parser = argparse.ArgumentParser(description="이상 데이터 주입기")
    parser.add_argument("--db", default="simulator.db", help="SQLite DB 파일 (기본: simulator.db)")
    parser.add_argument("--speed", type=float, default=2.0, help="속도 배율 (기본: 2x)")
    parser.add_argument("--loop", action="store_true", help="주입 후 상황 악화 반복 (Ctrl+C로 중지)")
    parser.add_argument("--reset", action="store_true", help="이전 주입 데이터 초기화 후 재주입")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("injector")

    if not os.path.exists(args.db):
        logger.error("DB 파일 없음: %s", args.db)
        logger.error("먼저 실행: python init_db.py --db %s", args.db)
        sys.exit(1)

    # SQLite 연결
    from simulator.sqlite_backend import init_sqlite
    init_sqlite(args.db)

    # 이전 데이터 초기화
    if args.reset:
        _reset_injected_data(logger)

    from simulator.scenarios import (
        scenario_conveyor_overload,
        scenario_equipment_down,
        scenario_wip_surge,
        scenario_aging_lots,
        scenario_agv_failure,
        worsen_situation,
    )

    scenarios = [
        ("컨베이어 과부하", scenario_conveyor_overload),
        ("설비 비계획정지", scenario_equipment_down),
        ("WIP 적체", scenario_wip_surge),
        ("에이징 LOT", scenario_aging_lots),
        ("AGV 장애", scenario_agv_failure),
    ]

    interval = 60 / args.speed

    logger.info("=" * 50)
    logger.info("이상 데이터 주입 시작 (속도: %.1fx, 간격: %.0f초)", args.speed, interval)
    logger.info("=" * 50)

    for i, (name, fn) in enumerate(scenarios):
        if i > 0:
            logger.info("'%s' → %.0f초 후...", name, interval)
            time.sleep(interval)
        fn()
        logger.warning("=== 주입 완료: %s ===", name)

    logger.info("모든 시나리오 주입 완료!")

    if args.loop:
        logger.info("상황 악화 모드 (%.0f초마다, Ctrl+C로 중지)", interval)
        try:
            while True:
                time.sleep(interval)
                worsen_situation()
                logger.info("상황 악화 주입")
        except KeyboardInterrupt:
            logger.info("주입 중지")


if __name__ == "__main__":
    main()
