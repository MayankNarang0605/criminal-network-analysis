"""
Ingestion Router.
Triggers loading of all 21 dataset evidence tables into Postgres and returns ingestion statistics.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from backend.services.ingestion import run_full_ingestion
from backend.logging_config import logger

router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])


@router.post("/run")
def trigger_ingestion():
    """Synchronously execute full dataset ingestion across all 21 evidence tables."""
    try:
        result = run_full_ingestion()
        return result
    except Exception as exc:
        logger.error(f"Ingestion failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
