"""
NCRB Criminal Network Analysis System — Configuration.

Design note: this build deliberately runs on an embedded stack (SQLite + FTS5 +
in-process graph engine) so the whole platform boots with one command on any
machine, with no Docker/Neo4j/Elasticsearch dependency. Every storage access
goes through an adapter layer, so a production deployment can point at
PostgreSQL / Neo4j / OpenSearch by changing configuration only.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root
DATA_DIR = BASE_DIR / "data"
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


class Settings:
    """Runtime configuration. Environment variables override every default."""

    # --- Application ---
    APP_NAME: str = "NCRB Criminal Network Analysis System"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = _env("APP_ENV", "development")

    ORGANISATION: str = "National Crime Records Bureau (NCRB)"
    DEPARTMENT: str = "Women Safety Division"
    MINISTRY: str = "Ministry of Home Affairs, Government of India"

    # --- Storage (embedded profile) ---
    STORAGE_PROFILE: str = _env("STORAGE_PROFILE", "embedded")
    SQLITE_PATH: str = _env("SQLITE_PATH", str(RUNTIME_DIR / "ncrb.db"))

    # --- Optional production backends (unused in embedded profile) ---
    POSTGRES_DSN: str | None = os.environ.get("POSTGRES_DSN")
    NEO4J_URI: str | None = os.environ.get("NEO4J_URI")
    OPENSEARCH_URL: str | None = os.environ.get("OPENSEARCH_URL")

    # --- Auth ---
    JWT_SECRET: str = _env("JWT_SECRET", "ncrb-dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_TTL_MINUTES: int = _env_int("JWT_TTL_MINUTES", 480)

    # --- Analytics tuning ---
    # Weights for the composite Kingpin Influence Score (must sum to 1.0).
    KINGPIN_WEIGHTS: dict[str, float] = {
        "betweenness": 0.22,   # brokerage: controls information//money flow
        "eigenvector": 0.16,   # connected to other important actors
        "insulation": 0.24,    # distance from dirty work = command signature
        "flow_control": 0.14,  # share of money/comms routed through actor
        "role_breadth": 0.12,  # spans multiple crime domains
        "resilience": 0.12,    # network damage if actor is removed
    }

    RISK_WEIGHTS: dict[str, float] = {
        "criminal_history": 0.24,
        "network_position": 0.20,
        "financial_anomaly": 0.18,
        "communication_pattern": 0.14,
        "offence_severity": 0.16,
        "recency": 0.08,
    }

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
