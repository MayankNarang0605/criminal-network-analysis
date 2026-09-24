"""
Database session factory via SQLAlchemy 2.0.
Primary engine: PostgreSQL (system-of-record).
Resilient local fallback: SQLite (zero-config, for local testing without Docker).
"""
import os
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from backend.config import settings
from backend.logging_config import logger


def _init_engine():
    """Attempt connecting to Postgres; fallback to SQLite if Postgres is unavailable."""
    db_url = settings.DATABASE_URL
    is_sqlite = db_url.startswith("sqlite")
    
    if not is_sqlite:
        import socket
        from urllib.parse import urlparse
        try:
            parsed = urlparse(db_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            is_open = (sock.connect_ex((host, port)) == 0)
            sock.close()
        except Exception:
            is_open = False

        if is_open:
            try:
                pg_engine = create_engine(
                    db_url,
                    pool_pre_ping=True,
                    pool_size=10,
                    max_overflow=20,
                    echo=False,
                    connect_args={"connect_timeout": 3} if "postgresql" in db_url else {},
                )
                with pg_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("Connected successfully to PostgreSQL database.")
                return pg_engine
            except Exception as exc:
                logger.warning(
                    f"PostgreSQL connection failed ({exc}). "
                    "Engaging resilient local SQLite database fallback."
                )
        else:
            logger.info("PostgreSQL not active locally; using resilient local SQLite database fallback.")

    # SQLite fallback
    sqlite_path = os.path.abspath("E:/criminal-network-analysis/crimenet.db")
    sqlite_url = f"sqlite:///{sqlite_path.replace(os.sep, '/')}"
    sqlite_engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    logger.info(f"Using SQLite database at {sqlite_url}")
    return sqlite_engine


engine = _init_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_postgres_health() -> dict:
    """Return health info for the database connection."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            dialect = engine.dialect.name
        return {"status": "healthy", "dialect": dialect}
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        return {"status": "unhealthy", "error": str(exc)}
