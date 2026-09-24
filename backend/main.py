"""
FastAPI application entry point.
Architecture: Thxrun's lifespan pattern + ATLAS router structure,
extended with Postgres + JWT auth + full dataset-backed modules.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import settings
from backend.database import neo4j_db
from backend.logging_config import logger
from backend.routers import (
    health_router,
    cases_router,
    graph_router,
    ingest_router,
    auth_router,
    persons_router,
    analytics_router,
    copilot_router,
    evidence_router,
    geospatial_router,
    reports_router,
    nlp_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init Neo4j schema constraints if online. Shutdown: close connections."""
    logger.info(f"Starting {settings.APP_NAME} [{settings.APP_ENV}]")
    if neo4j_db.is_healthy():
        try:
            from backend.services.schema_manager import init_neo4j_schema
            with neo4j_db.get_session() as session:
                init_neo4j_schema(session)
        except Exception as exc:
            logger.warning(f"Neo4j schema init skipped: {exc}")
    else:
        logger.info("Neo4j not currently reachable — starting in resilient database-backed mode.")
    try:
        yield
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        try:
            neo4j_db.close()
        except Exception:
            pass
        logger.info("Application shutdown complete")


app = FastAPI(
    title="CrimeNet — AI-Powered Criminal Network Analysis System",
    description=(
        "Graph-centric criminal investigation platform: entity resolution, "
        "Neo4j knowledge graph, 10+ detection engines, kingpin scoring, "
        "geospatial intelligence, AI Copilot with deterministic fallback, "
        "evidence-integrity ledger, and evaluation harness."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global error handlers ────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "UnprocessableEntityError",
            "message": "Request payload validation failed.",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error at {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected server error occurred.",
            "detail": str(exc) if settings.DEBUG else None,
        },
    )


@app.get("/health", tags=["Health"])
def root_health():
    from backend.routers.health import health_check
    return health_check()


# ── Routers (specific before parameterized) ──────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(persons_router)
app.include_router(graph_router)
app.include_router(ingest_router)
app.include_router(analytics_router)
app.include_router(copilot_router)
app.include_router(evidence_router)
app.include_router(geospatial_router)
app.include_router(reports_router)
app.include_router(nlp_router)


from fastapi.staticfiles import StaticFiles

# ── Static Files & Root: serve frontend dist if built ───────────────────────
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
assets_dir = frontend_dist / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.get("/favicon.svg", include_in_schema=False)
def serve_favicon():
    fav = frontend_dist / "favicon.svg"
    if fav.exists():
        return Response(content=fav.read_bytes(), media_type="image/svg+xml")
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#38bdf8" d="M12 2L3 7v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z"/></svg>'
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse, tags=["UI"], include_in_schema=False)
def serve_dashboard():
    dist = frontend_dist / "index.html"
    if dist.exists():
        return dist.read_text(encoding="utf-8")
    return HTMLResponse("<h1>CrimeNet API running. Frontend not built yet.</h1>", status_code=200)


@app.head("/", include_in_schema=False)
def serve_dashboard_head():
    return Response(status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

