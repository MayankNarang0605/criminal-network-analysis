"""
Main Application Entry Point (Starlette / ASGI)
Sets up routes, CORS middleware, static files, and application startup lifecycle.
"""

import os
from pathlib import Path
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.responses import HTMLResponse, JSONResponse
from starlette.templating import Jinja2Templates

from backend.app.config import BASE_DIR
from backend.app.database.connection import init_db
from backend.app.security.auth import seed_default_users
from backend.app.synthetic.generator import SyntheticDataGenerator
from backend.app.graph.engine import graph_engine

# Import Route Handlers
from backend.app.api.auth_routes import (
    login_endpoint,
    current_user_endpoint,
    list_demo_users_endpoint
)
from backend.app.api.case_routes import (
    preview_entities_endpoint,
    intake_case_endpoint,
    list_cases_endpoint,
    get_case_detail_endpoint,
    seed_synthetic_data_endpoint
)
from backend.app.api.graph_routes import (
    get_full_graph_endpoint,
    get_ego_graph_endpoint,
    search_graph_nodes_endpoint,
    get_node_profile_endpoint
)
from backend.app.api.analytics_routes import (
    key_players_ranking_endpoint,
    community_detection_endpoint,
    shortest_path_endpoint,
    link_predictions_endpoint
)
from backend.app.api.jurisdiction_routes import (
    cross_jurisdiction_links_endpoint,
    list_jurisdictions_endpoint
)
from backend.app.api.audit_routes import (
    list_audit_logs_endpoint,
    verify_audit_chain_endpoint
)
from backend.app.api.export_routes import (
    list_merge_candidates_endpoint,
    execute_merge_endpoint,
    export_dossier_endpoint
)

# Paths
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

# Ensure directories exist
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

async def homepage(request):
    """Serves the main Command Dashboard Single Page Application."""
    return templates.TemplateResponse(request, "index.html")

async def health_check(request):
    """API health status endpoint."""
    return JSONResponse({
        "status": "healthy",
        "system": "AI-Powered Criminal Network Analysis System",
        "theme": "Ministry of Home Affairs (MHA) Specification",
        "total_nodes": len(graph_engine.nodes_data),
        "total_edges": len(graph_engine.edges_data)
    })

# API Routes
routes = [
    # Frontend & Health
    Route("/", endpoint=homepage, methods=["GET"]),
    Route("/api/health", endpoint=health_check, methods=["GET"]),

    # Auth & RBAC
    Route("/api/auth/login", endpoint=login_endpoint, methods=["POST"]),
    Route("/api/auth/me", endpoint=current_user_endpoint, methods=["GET"]),
    Route("/api/auth/demo-users", endpoint=list_demo_users_endpoint, methods=["GET"]),

    # Case Management & NLP
    Route("/api/cases/preview", endpoint=preview_entities_endpoint, methods=["POST"]),
    Route("/api/cases/intake", endpoint=intake_case_endpoint, methods=["POST"]),
    Route("/api/cases", endpoint=list_cases_endpoint, methods=["GET"]),
    Route("/api/cases/{case_id}", endpoint=get_case_detail_endpoint, methods=["GET"]),
    Route("/api/cases/synthetic/reset", endpoint=seed_synthetic_data_endpoint, methods=["POST"]),

    # Graph Operations
    Route("/api/graph", endpoint=get_full_graph_endpoint, methods=["GET"]),
    Route("/api/graph/search", endpoint=search_graph_nodes_endpoint, methods=["GET"]),
    Route("/api/graph/ego/{node_id}", endpoint=get_ego_graph_endpoint, methods=["GET"]),
    Route("/api/graph/profile/{node_id}", endpoint=get_node_profile_endpoint, methods=["GET"]),

    # Analytics & Graph ML
    Route("/api/analytics/key-players", endpoint=key_players_ranking_endpoint, methods=["GET"]),
    Route("/api/analytics/communities", endpoint=community_detection_endpoint, methods=["GET"]),
    Route("/api/analytics/shortest-path", endpoint=shortest_path_endpoint, methods=["GET"]),
    Route("/api/analytics/link-predictions", endpoint=link_predictions_endpoint, methods=["GET"]),

    # Jurisdictions (OCND)
    Route("/api/jurisdictions/cross-links", endpoint=cross_jurisdiction_links_endpoint, methods=["GET"]),
    Route("/api/jurisdictions", endpoint=list_jurisdictions_endpoint, methods=["GET"]),

    # Audit Trail & Integrity
    Route("/api/audit/logs", endpoint=list_audit_logs_endpoint, methods=["GET"]),
    Route("/api/audit/verify-chain", endpoint=verify_audit_chain_endpoint, methods=["GET"]),

    # Entity Resolution & Export
    Route("/api/entities/merge-candidates", endpoint=list_merge_candidates_endpoint, methods=["GET"]),
    Route("/api/entities/merge", endpoint=execute_merge_endpoint, methods=["POST"]),
    Route("/api/export/dossier/{entity_id}", endpoint=export_dossier_endpoint, methods=["GET"]),

    # Static Assets
    Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"]
    )
]

def startup_tasks():
    """Initializes DB, seeds users, and loads initial synthetic data if empty."""
    init_db()
    seed_default_users()
    if len(graph_engine.nodes_data) == 0:
        generator = SyntheticDataGenerator(graph_engine)
        generator.generate_all_scenarios(reset_first=False)

startup_tasks()

app = Starlette(debug=True, routes=routes, middleware=middleware)
