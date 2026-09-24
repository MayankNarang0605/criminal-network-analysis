"""
Cross-Jurisdiction Syndicate Linkage Endpoints (OCND / NATGRID)
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.config import JURISDICTIONS
from backend.app.graph.engine import graph_engine
from backend.app.graph.analytics import GraphAnalytics

analytics = GraphAnalytics(graph_engine)

async def cross_jurisdiction_links_endpoint(request: Request) -> JSONResponse:
    """
    Surfaces suspects, phones, vehicles, or bank accounts that span across
    multiple police stations or states (OCND feature).
    """
    links = analytics.detect_cross_jurisdiction_links()
    
    return JSONResponse({
        "total_cross_jurisdictional_entities": len(links),
        "alerts": links
    })

async def list_jurisdictions_endpoint(request: Request) -> JSONResponse:
    """Returns list of supported Law Enforcement Agencies & Specialized Wings."""
    return JSONResponse({
        "jurisdictions": JURISDICTIONS
    })
