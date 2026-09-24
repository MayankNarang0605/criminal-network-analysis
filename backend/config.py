"""
Application settings — loaded from environment variables / .env file.
Adapted from Thxrun's config.py, extended with Postgres + JWT + dataset path.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "CrimeNet — Criminal Network Analysis System"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True

    # ── PostgreSQL ──────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql://crimenet:crimenet_secret@localhost:5432/crimenet"
    )

    # ── Neo4j ───────────────────────────────────────────────────────────────
    NEO4J_URI: str = Field(default="bolt://localhost:7687")
    NEO4J_USERNAME: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="crimenet_neo4j")
    NEO4J_DATABASE: str = Field(default="neo4j")
    NEO4J_MAX_CONNECTION_POOL_SIZE: int = 50

    # ── Algorithm defaults ──────────────────────────────────────────────────
    DEFAULT_MAX_PATH_DEPTH: int = 5
    ENABLE_GDS: bool = False   # flip True if Neo4j GDS plugin installed

    # ── Auth / Security ─────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default="change-me-to-a-random-32-char-secret")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480   # 8 hours
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ── AI Copilot ──────────────────────────────────────────────────────────
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ── Dataset (read-only mount) ────────────────────────────────────────────
    # CRITICAL: ground_truth/ is NEVER accessed by the application.
    # Only evaluation/harness.py reads it.
    DATASET_PATH: str = Field(default="./dataset")

    @property
    def evidence_path(self) -> str:
        return os.path.join(self.DATASET_PATH, "evidence")

    @property
    def neo4j_import_path(self) -> str:
        return os.path.join(self.DATASET_PATH, "neo4j")


settings = Settings()
