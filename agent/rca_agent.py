"""원인분석(RCA) 에이전트 — DB 폴링으로 pending 이상 분석.

rca_status='pending' → 'processing' → 'done'/'failed' 전이.
분석 완료 시 알림을 alert.router.send_alert()로 직접 발송.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agent.agent_loop import run_agent_loop
from agent.prompts import RCA_SYSTEM
from config import settings
from db import queries

logger = logging.getLogger(__name__)


async def poll_and_analyze() -> int:
    """DB에서 rca_status='pending' 조회 → 하나씩 분석.

    Returns: 처리된 이상 수.
    """
    pending = await queries.get_pending_rca(limit=5)
    if not pending:
        return 0

    count = 0
    for anomaly in pending:
        anomaly_id = anomaly["anomaly_id"]

        # processing으로 갱신 (중복 처리 방지)
        await queries.update_rca_status(anomaly_id, "processing")

        try:
            result = await _run_rca(anomaly)

            # DB에 분석 결과 저장
            await queries.update_anomaly_rca(
                anomaly_id=anomaly_id,
                analysis=result.get("root_cause", "분석 실패"),
                suggestion=json.dumps(
                    result.get("suggested_actions", []),
                    ensure_ascii=False,
                ),
            )
            await queries.update_rca_status(anomaly_id, "done")

            logger.info(
                "RCA completed: anomaly_id=%d root_cause=%s confidence=%.2f",
                anomaly_id,
                result.get("root_cause", "?")[:80],
                result.get("confidence", 0),
            )

            # 알림 발송 (DB 기록)
            from alert.router import send_alert
            await send_alert(anomaly, result)

            count += 1

        except Exception:
            logger.exception("RCA failed for anomaly_id=%d", anomaly_id)
            await queries.update_rca_status(anomaly_id, "failed")
            await queries.update_anomaly_rca(
                anomaly_id=anomaly_id,
                analysis="RCA 분석 중 오류 발생",
                suggestion="수동 분석 필요",
            )

    if count:
        logger.info("RCA poll completed: %d/%d analyzed", count, len(pending))
    return count


async def _run_rca(anomaly: dict[str, Any]) -> dict[str, Any]:
    """ReAct 루프로 근본원인 분석."""
    user_msg = await _build_rca_message(anomaly)
    return await run_agent_loop(
        system_prompt=RCA_SYSTEM,
        user_message=user_msg,
        max_rounds=3,
    )


async def _build_rca_message(anomaly: dict[str, Any]) -> str:
    # RAG 전문지식 검색 (lazy import — pymilvus 없어도 동작)
    rag_context = ""
    if settings.rag.enabled:
        try:
            from rag.retriever import retrieve_context, build_search_query
            search_query = build_search_query(
                {
                    "rule_name": anomaly.get("title", ""),
                    "category": anomaly.get("category", ""),
                    "subcategory": "",
                },
                anomaly.get("description", ""),
            )
            rag_context = await retrieve_context(
                query=search_query,
                category=anomaly.get("category"),
                top_k=settings.rag.top_k,
                min_score=settings.rag.min_score,
            )
        except Exception:
            logger.warning("RAG retrieval failed for anomaly_id=%d, proceeding without", anomaly.get("anomaly_id", 0))

    return f"""## 이상 감지 — 근본원인 분석 요청

**이상 ID**: {anomaly['anomaly_id']}
**감지 시각**: {anomaly.get('detected_at', '')}
**제목**: {anomaly.get('title', '')}
**심각도**: {anomaly.get('severity', 'warning')}
**카테고리**: {anomaly.get('category', '')}
**영향 엔티티**: {anomaly.get('affected_entity', '')}

### 감지 정보
- 측정값: {anomaly.get('measured_value', '')}
- 임계치: {anomaly.get('threshold_value', '')}
- 설명: {anomaly.get('description', '')}

{rag_context}

위 이상의 근본 원인을 분석하세요.
전문지식이 있다면 유사 사례와 알려진 원인 패턴을 참고하세요.
제공된 도구로 관련 설비/공정/물류 데이터를 추가 조회하여
원인을 좁혀가세요.
"""
