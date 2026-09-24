from backend.routers.health import router as health_router
from backend.routers.auth import router as auth_router
from backend.routers.cases import router as cases_router
from backend.routers.persons import router as persons_router
from backend.routers.graph import router as graph_router
from backend.routers.ingest import router as ingest_router
from backend.routers.analytics import router as analytics_router
from backend.routers.copilot import router as copilot_router
from backend.routers.evidence import router as evidence_router
from backend.routers.geospatial import router as geospatial_router
from backend.routers.reports import router as reports_router
from backend.routers.nlp import router as nlp_router

__all__ = [
    "health_router",
    "auth_router",
    "cases_router",
    "persons_router",
    "graph_router",
    "ingest_router",
    "analytics_router",
    "copilot_router",
    "evidence_router",
    "geospatial_router",
    "reports_router",
    "nlp_router",
]
