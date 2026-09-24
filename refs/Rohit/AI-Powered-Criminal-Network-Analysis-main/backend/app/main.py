"""
NCRB Criminal Network Analysis System — application entry point.

Zero-infrastructure deployment: the entire platform (relational store, full-text
index, graph engine, ML scoring, blockchain audit ledger) runs in this process
against a single SQLite file. `uvicorn app.main:app` is the only command needed.
On first boot it seeds users and, if the database is empty, runs the full
ingestion pipeline so the API is immediately useful.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.api.routes import (
    alerts_router, audit_router, auth_router, dashboard_router, data_router,
    graph_router, ml_router, nlp_router, search_router, women_router,
)
from app.auth.security import seed_users
from app.blockchain.ledger import chain
from app.config import BASE_DIR, settings
from app.graph.engine import engine

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
logger = logging.getLogger("ncrb")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (%s profile)", settings.APP_NAME, settings.STORAGE_PROFILE)
    db.init_db()
    seed_users()
    chain.ensure_genesis()

    case_count = db.scalar("SELECT COUNT(*) FROM cases")
    if case_count == 0:
        logger.info("Empty database detected — running initial ingestion pipeline")
        from app.etl.pipeline import run_pipeline
        result = run_pipeline(use_samples=True, synthetic_networks=6)
        logger.info("Ingestion complete: %s entities, %s relationships in %sms",
                    result["ingest"]["entities_total"],
                    result["ingest"]["relationships_total"],
                    result["ingest"]["timings_ms"].get("total"))
    else:
        logger.info("Loading existing corpus: %s cases", case_count)
        engine.load()
        engine.communities()

    logger.info("Graph ready: %s nodes, %s edges",
                engine.G.number_of_nodes(), engine.G.number_of_edges())
    yield
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-powered criminal network analysis for the National Crime Records Bureau, "
        "Women Safety Division, Ministry of Home Affairs.\n\n"
        "**Capabilities**\n"
        "- Multi-source ingestion (FIR narratives, CDRs, financial ledgers)\n"
        "- Hybrid NLP entity and relationship extraction tuned for Indian records\n"
        "- Entity resolution across fragmented sources\n"
        "- Graph analytics: centrality, community detection, path finding, link prediction\n"
        "- Composite Kingpin Influence Score with insulation-index modelling\n"
        "- Network disruption simulation and optimal arrest-set recommendation\n"
        "- FATF/FIU-IND money-laundering typology detection\n"
        "- Explainable risk scoring with full factor attribution\n"
        "- Tamper-evident blockchain audit ledger with Merkle inclusion proofs\n"
        "- Women Safety Division module: repeat offenders, escalation risk, corridors\n"
        "- Ground-truth evaluation against naive baselines\n"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"] if settings.APP_ENV != "production"
    else settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc),
                 "path": request.url.path},
    )


API = "/api/v1"
app.include_router(auth_router, prefix=f"{API}/auth", tags=["Authentication & RBAC"])
app.include_router(data_router, prefix=f"{API}/data", tags=["Data Ingestion"])
app.include_router(nlp_router, prefix=f"{API}/nlp", tags=["NLP Extraction"])
app.include_router(graph_router, prefix=f"{API}/graph", tags=["Graph Intelligence"])
app.include_router(ml_router, prefix=f"{API}/ml", tags=["Risk & Patterns"])
app.include_router(search_router, prefix=f"{API}/search", tags=["Search"])
app.include_router(alerts_router, prefix=f"{API}/alerts", tags=["Alerts"])
app.include_router(audit_router, prefix=f"{API}/audit", tags=["Blockchain Audit"])
app.include_router(women_router, prefix=f"{API}/women-safety", tags=["Women Safety Division"])
app.include_router(dashboard_router, prefix=f"{API}/dashboard", tags=["Dashboard"])


@app.get("/", tags=["Health"], summary="System identity")
async def root():
    return {
        "system": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "organisation": settings.ORGANISATION,
        "department": settings.DEPARTMENT,
        "ministry": settings.MINISTRY,
        "storage_profile": settings.STORAGE_PROFILE,
        "dashboard": "/app",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"], summary="Subsystem health")
async def health():
    integrity = chain.verify()
    return {
        "status": "healthy",
        "subsystems": {
            "database": "up",
            "graph_engine": "loaded" if engine.loaded else "empty",
            "search_index": "up" if db.scalar("SELECT COUNT(*) FROM search_index") else "empty",
            "audit_ledger": "valid" if integrity["valid"] else "COMPROMISED",
        },
        "graph": {"nodes": engine.G.number_of_nodes(), "edges": engine.G.number_of_edges()},
        "audit_blocks": integrity.get("blocks", 0),
    }


# ---------------------------------------------------------------------------
# Serve the built dashboard from the same origin when it exists, so a single
# `uvicorn app.main:app` command runs the entire platform with no CORS setup.
# Mounted last so it never shadows an API route.
# ---------------------------------------------------------------------------
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/app", include_in_schema=False)
    @app.get("/app/{path:path}", include_in_schema=False)
    async def serve_dashboard(path: str = ""):
        """Single-page app entry point. Client-side routing handles the rest."""
        return FileResponse(FRONTEND_DIST / "index.html")

    logger.info("Dashboard served at /app from %s", FRONTEND_DIST)
else:
    @app.get("/app", include_in_schema=False)
    async def dashboard_missing():
        return JSONResponse(
            status_code=503,
            content={
                "error": "dashboard_not_built",
                "detail": "Run `npm install && npm run build` in the frontend directory, "
                          "or use `npm run dev` for the development server on port 5173.",
            },
        )
