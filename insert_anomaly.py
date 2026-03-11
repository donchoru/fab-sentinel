"""이상 데이터 수동 삽입 스크립트.

사용법:
  # 기본 (감지됨 상태)
  python insert_anomaly.py --title "EQ-010 온도 이상" --category equipment --severity critical

  # 해결 완료 상태
  python insert_anomaly.py --title "AGV-005 통신 끊김" --category logistics --severity warning --status resolved --resolved-by "박엔지니어"

  # RCA 포함
  python insert_anomaly.py --title "WIP 200% 적체" --category wip --severity critical \
    --root-cause "설비 3대 동시 정지로 인한 적체" \
    --cause-category process \
    --factors "설비 EQ-003 정지" "설비 EQ-007 정지" "투입 중단 미실시" \
    --recommendations "설비 즉시 복구" "투입 일시 중단" \
    --confidence 0.85

  # 전체 옵션
  python insert_anomaly.py \
    --title "LINE02 컨베이어 과부하" \
    --description "LINE02-ZONE-B 부하율 95%" \
    --category logistics \
    --severity critical \
    --measured 95.0 \
    --threshold 90.0 \
    --entity "LINE02-ZONE-B" \
    --status resolved \
    --resolved-by "김매니저" \
    --analysis "AI가 분석한 내용" \
    --suggestion "조치1" "조치2" \
    --root-cause "하류 설비 정지" \
    --cause-category equipment \
    --factors "EQ-008 정지" "캐리어 회수 지연" \
    --evidence "conveyor_status: 95/100" "equipment: EQ-008 DOWN" \
    --recommendations "설비 복구" "우회 경로 활성화" \
    --confidence 0.88
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="이상 데이터 수동 삽입",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 필수
    parser.add_argument("--title", required=True, help="이상 제목")
    parser.add_argument("--category", required=True, choices=["logistics", "wip", "equipment"], help="카테고리")
    parser.add_argument("--severity", required=True, choices=["critical", "warning"], help="심각도")

    # 이상 상세 (선택)
    parser.add_argument("--db", default="simulator.db", help="SQLite DB 파일 (기본: simulator.db)")
    parser.add_argument("--description", default="", help="상세 설명")
    parser.add_argument("--measured", type=float, default=None, help="측정값")
    parser.add_argument("--threshold", type=float, default=None, help="임계치")
    parser.add_argument("--entity", default="", help="영향 대상 (예: EQ-005, LINE03-ZONE-A)")
    parser.add_argument("--status", default="detected", choices=["detected", "in_progress", "resolved"], help="상태")
    parser.add_argument("--resolved-by", default=None, help="해결자 (resolved 상태일 때)")
    parser.add_argument("--analysis", default=None, help="AI 분석 내용")
    parser.add_argument("--suggestion", nargs="*", default=None, help="AI 제안 (여러 항목)")

    # RCA (선택)
    parser.add_argument("--root-cause", default=None, help="근본 원인")
    parser.add_argument("--cause-category", default=None, choices=["equipment", "process", "material", "human", "environment", "logistics"], help="원인 분류")
    parser.add_argument("--factors", nargs="*", default=None, help="기여 요인 (여러 항목)")
    parser.add_argument("--evidence", nargs="*", default=None, help="분석 근거 (여러 항목)")
    parser.add_argument("--recommendations", nargs="*", default=None, help="권장 조치 (여러 항목)")
    parser.add_argument("--confidence", type=float, default=None, help="신뢰도 (0.0~1.0)")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"DB 파일 없음: {args.db}")
        print(f"먼저 실행: python init_db.py --db {args.db}")
        sys.exit(1)

    from simulator.sqlite_backend import init_sqlite, get_conn
    init_sqlite(args.db)
    conn = get_conn()

    # rca_analyses 테이블 보장
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rca_analyses (
            rca_id INTEGER PRIMARY KEY AUTOINCREMENT,
            anomaly_id INTEGER NOT NULL REFERENCES anomalies(anomaly_id),
            status TEXT DEFAULT 'pending',
            root_cause TEXT,
            cause_category TEXT,
            contributing_factors TEXT,
            evidence TEXT,
            recommendations TEXT,
            confidence REAL,
            analyzed_at TEXT,
            analysis_duration_ms INTEGER,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # 이상 삽입
    suggestion_json = json.dumps(args.suggestion, ensure_ascii=False) if args.suggestion else None
    resolved_at_sql = 'datetime("now", "localtime")' if args.status == "resolved" else "NULL"

    cursor = conn.execute(
        f"""INSERT INTO anomalies (category, severity, title, description,
           measured_value, threshold_value, affected_entity, status,
           llm_analysis, llm_suggestion, detected_at, resolved_at, resolved_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'),
           {resolved_at_sql}, ?)""",
        (
            args.category, args.severity, args.title, args.description,
            args.measured, args.threshold, args.entity, args.status,
            args.analysis, suggestion_json, args.resolved_by,
        ),
    )
    anomaly_id = cursor.lastrowid
    print(f"이상 삽입 완료 (anomaly_id: {anomaly_id})")

    # RCA 삽입 (root-cause가 있을 때만)
    if args.root_cause:
        factors_json = json.dumps(args.factors, ensure_ascii=False) if args.factors else None
        evidence_json = json.dumps(args.evidence, ensure_ascii=False) if args.evidence else None
        recs_json = json.dumps(args.recommendations, ensure_ascii=False) if args.recommendations else None

        conn.execute(
            """INSERT INTO rca_analyses (anomaly_id, status, root_cause, cause_category,
               contributing_factors, evidence, recommendations, confidence,
               analyzed_at, analysis_duration_ms)
               VALUES (?, 'done', ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), 0)""",
            (
                anomaly_id, args.root_cause, args.cause_category,
                factors_json, evidence_json, recs_json, args.confidence,
            ),
        )
        print(f"RCA 삽입 완료 (anomaly_id: {anomaly_id})")

    conn.commit()
    print()
    print(f"  제목: {args.title}")
    print(f"  상태: {args.status}")
    if args.root_cause:
        print(f"  근본원인: {args.root_cause}")
    print()
    print("대시보드에서 확인: http://localhost:3009/anomalies")


if __name__ == "__main__":
    main()
