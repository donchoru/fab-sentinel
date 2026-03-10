"""FAB 이상감지 시스템 환경 설정."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class OracleConfig:
    user: str = field(default_factory=lambda: os.getenv("ORACLE_USER", "fab"))
    password: str = field(default_factory=lambda: os.getenv("ORACLE_PASSWORD", ""))
    dsn: str = field(default_factory=lambda: os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1"))
    min_pool: int = 2
    max_pool: int = 10


@dataclass
class LLMConfig:
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-2.0-flash"))
    timeout: float = 60.0
    max_tokens: int = 2048
    temperature: float = 0.1


@dataclass
class SchedulerConfig:
    detection_interval_sec: int = field(
        default_factory=lambda: int(os.getenv("DETECTION_INTERVAL_SEC", "300"))
    )


@dataclass
class RAGConfig:
    enabled: bool = field(default_factory=lambda: os.getenv("RAG_ENABLED", "true").lower() == "true")
    milvus_uri: str = field(default_factory=lambda: os.getenv("MILVUS_URI", "http://localhost:19530"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "bge-m3"))
    embedding_dim: int = field(default_factory=lambda: int(os.getenv("EMBEDDING_DIM", "1024")))
    top_k: int = 5
    min_score: float = 0.3


@dataclass
class Settings:
    oracle: OracleConfig = field(default_factory=OracleConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    host: str = "0.0.0.0"
    port: int = 8600
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")


settings = Settings()
