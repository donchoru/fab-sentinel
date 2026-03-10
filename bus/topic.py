"""In-process pub/sub topic bus using asyncio — with metrics."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# Well-known topics
TOPIC_ANOMALY_DETECTED = "anomaly.detected"
TOPIC_RCA_COMPLETED = "rca.completed"
TOPIC_ALERT_REQUEST = "alert.request"


@dataclass
class Message:
    topic: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""


@dataclass
class TopicMetrics:
    """토픽별 메트릭."""
    published: int = 0
    delivered: int = 0
    failed: int = 0
    last_published_at: datetime | None = None
    last_delivered_at: datetime | None = None
    total_processing_ms: float = 0
    min_processing_ms: float = float("inf")
    max_processing_ms: float = 0

    @property
    def avg_processing_ms(self) -> float:
        return self.total_processing_ms / self.delivered if self.delivered else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "published": self.published,
            "delivered": self.delivered,
            "failed": self.failed,
            "pending": self.published - self.delivered - self.failed,
            "last_published_at": self.last_published_at.isoformat() if self.last_published_at else None,
            "last_delivered_at": self.last_delivered_at.isoformat() if self.last_delivered_at else None,
            "avg_processing_ms": round(self.avg_processing_ms, 1),
            "min_processing_ms": round(self.min_processing_ms, 1) if self.min_processing_ms != float("inf") else None,
            "max_processing_ms": round(self.max_processing_ms, 1) if self.max_processing_ms else None,
        }


Subscriber = Callable[[Message], Coroutine[Any, Any, None]]


class TopicBus:
    """Simple in-process pub/sub bus with built-in metrics.

    Detection agent publishes anomalies → RCA agent subscribes and analyzes.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None
        self._metrics: dict[str, TopicMetrics] = defaultdict(TopicMetrics)
        self._started_at: datetime | None = None
        self._recent_messages: list[dict[str, Any]] = []  # 최근 메시지 (최대 100)
        self._max_recent = 100

    def subscribe(self, topic: str, handler: Subscriber) -> None:
        self._subscribers[topic].append(handler)
        logger.info("Subscribed to topic=%s handler=%s", topic, handler.__qualname__)

    def unsubscribe(self, topic: str, handler: Subscriber) -> None:
        if handler in self._subscribers[topic]:
            self._subscribers[topic].remove(handler)

    async def publish(self, topic: str, payload: dict[str, Any], source: str = "") -> None:
        msg = Message(topic=topic, payload=payload, source=source)
        await self._queue.put(msg)

        m = self._metrics[topic]
        m.published += 1
        m.last_published_at = msg.timestamp

        logger.debug("Published topic=%s source=%s", topic, source)

    async def start(self) -> None:
        self._running = True
        self._started_at = datetime.now()
        self._task = asyncio.create_task(self._dispatch_loop())
        logger.info("TopicBus started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TopicBus stopped")

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            handlers = self._subscribers.get(msg.topic, [])
            m = self._metrics[msg.topic]
            start = time.monotonic()

            all_ok = True
            for handler in handlers:
                try:
                    await handler(msg)
                except Exception:
                    logger.exception(
                        "Handler %s failed for topic=%s", handler.__qualname__, msg.topic
                    )
                    all_ok = False

            elapsed_ms = (time.monotonic() - start) * 1000

            if all_ok:
                m.delivered += 1
                m.last_delivered_at = datetime.now()
            else:
                m.failed += 1

            m.total_processing_ms += elapsed_ms
            m.min_processing_ms = min(m.min_processing_ms, elapsed_ms)
            m.max_processing_ms = max(m.max_processing_ms, elapsed_ms)

            # 최근 메시지 기록
            self._recent_messages.append({
                "topic": msg.topic,
                "source": msg.source,
                "timestamp": msg.timestamp.isoformat(),
                "status": "delivered" if all_ok else "failed",
                "processing_ms": round(elapsed_ms, 1),
                "anomaly_id": msg.payload.get("anomaly_id"),
                "severity": msg.payload.get("severity"),
                "title": msg.payload.get("title", "")[:80],
            })
            if len(self._recent_messages) > self._max_recent:
                self._recent_messages = self._recent_messages[-self._max_recent:]

    def get_metrics(self) -> dict[str, Any]:
        """전체 메트릭 스냅샷."""
        total_published = sum(m.published for m in self._metrics.values())
        total_delivered = sum(m.delivered for m in self._metrics.values())
        total_failed = sum(m.failed for m in self._metrics.values())

        return {
            "bus": {
                "running": self._running,
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "queue_depth": self._queue.qsize(),
                "subscriber_count": sum(len(h) for h in self._subscribers.values()),
            },
            "totals": {
                "published": total_published,
                "delivered": total_delivered,
                "failed": total_failed,
                "pending": total_published - total_delivered - total_failed,
            },
            "topics": {
                topic: m.to_dict() for topic, m in self._metrics.items()
            },
            "subscribers": {
                topic: [h.__qualname__ for h in handlers]
                for topic, handlers in self._subscribers.items()
            },
        }

    def get_recent_messages(self, limit: int = 50) -> list[dict[str, Any]]:
        """최근 처리된 메시지 목록."""
        return list(reversed(self._recent_messages[-limit:]))


# Singleton
bus = TopicBus()
