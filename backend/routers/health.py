"""
Health router — checks Neo4j + Postgres status.
Used by Docker healthchecks and the frontend status indicator.
"""
from fastapi import APIRouter
from backend.database import neo4j_db
from backend.postgres import check_postgres_health
from backend.config import settings

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
def health_check():
    neo4j_health = neo4j_db.check_health()
    postgres_health = check_postgres_health()
    overall = (
        "healthy"
        if neo4j_health["status"] == "healthy" and postgres_health["status"] == "healthy"
        else "degraded"
    )
    return {
        "status": overall,
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "env": settings.APP_ENV,
        "services": {
            "neo4j": neo4j_health,
            "postgres": postgres_health,
        },
        "gemini_configured": bool(settings.GEMINI_API_KEY),
    }
