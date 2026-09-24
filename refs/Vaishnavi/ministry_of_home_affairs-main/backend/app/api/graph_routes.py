"""
Graph Visualization & Exploration API Endpoints
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.graph.engine import graph_engine
from backend.app.graph.analytics import GraphAnalytics
from backend.app.database.connection import SessionLocal
from backend.app.security.audit import AuditLogger
from backend.app.api.case_routes import get_current_user_info

analytics = GraphAnalytics(graph_engine)

async def get_full_graph_endpoint(request: Request) -> JSONResponse:
    """
    Returns the complete node-edge property graph with community assignments,
    risk tiers, and centrality measures for interactive visual rendering.
    """
    # Ensure communities and centralities are up-to-date
    analytics.detect_communities()
    analytics.compute_composite_risk_score()

    label_filter = request.query_params.get("label")
    category_filter = request.query_params.get("category")
    jurisdiction_filter = request.query_params.get("jurisdiction")

    nodes = graph_engine.get_all_nodes(label_filter=label_filter)
    edges = graph_engine.get_all_edges()

    # Apply category / jurisdiction filter if specified
    if category_filter or jurisdiction_filter:
        valid_node_ids = set()
        for n in nodes:
            # Check direct match or case link
            if category_filter and n.get("crime_category") == category_filter:
                valid_node_ids.add(n["id"])
            if jurisdiction_filter and n.get("jurisdiction_code") == jurisdiction_filter:
                valid_node_ids.add(n["id"])

        # Also include 1-hop connected nodes to those matching cases
        for e in edges:
            if e["source"] in valid_node_ids or e["target"] in valid_node_ids:
                valid_node_ids.add(e["source"])
                valid_node_ids.add(e["target"])

        nodes = [n for n in nodes if n["id"] in valid_node_ids]
        edges = [e for e in edges if e["source"] in valid_node_ids and e["target"] in valid_node_ids]

    stats = graph_engine.get_stats()

    return JSONResponse({
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "graph_stats": stats
    })

async def get_ego_graph_endpoint(request: Request) -> JSONResponse:
    """
    Returns k-hop ego network around a specific node.
    """
    node_id = request.path_params.get("node_id")
    radius = int(request.query_params.get("radius", 1))
    
    subgraph = graph_engine.get_ego_graph(node_id, radius=radius)
    
    return JSONResponse(subgraph)

async def search_graph_nodes_endpoint(request: Request) -> JSONResponse:
    """
    Searches graph entities by query string, alias, phone, vehicle plate, or case number.
    """
    q = request.query_params.get("q", "")
    label = request.query_params.get("label")
    
    results = graph_engine.search_nodes(query=q, label_filter=label, limit=30)
    
    # Audit log search query for compliance
    if q and len(q) >= 3:
        db = SessionLocal()
        try:
            username, role, uid = get_current_user_info(request)
            AuditLogger.log_action(
                db=db,
                username=username,
                user_role=role,
                action="SEARCH_ENTITIES",
                entity_type="SearchQuery",
                entity_id=q,
                details={"query": q, "label_filter": label, "results_count": len(results)},
                user_id=uid
            )
        finally:
            db.close()

    return JSONResponse({
        "query": q,
        "total_matches": len(results),
        "results": results
    })

async def get_node_profile_endpoint(request: Request) -> JSONResponse:
    """
    Generates a 360° deep-dive intelligence dossier for a suspect or entity.
    Includes associates tree, timeline of incidents, cases linked, asset links, and XAI breakdown.
    """
    node_id = request.path_params.get("node_id")
    node = graph_engine.get_node(node_id)
    if not node:
        return JSONResponse({"error": "Entity not found"}, status_code=404)

    # 1. Fetch direct neighbors
    neighbors = graph_engine.get_neighbors(node_id, direction="both")
    
    associates = []
    cases_linked = []
    assets = []
    communication_history = []
    locations = []

    for nb in neighbors:
        nb_node = nb["node"]
        lbl = nb_node.get("label")
        rel = nb.get("relation")

        if lbl == "Person":
            associates.append({
                "id": nb_node["id"],
                "name": nb_node.get("name"),
                "relation": rel,
                "role": nb_node.get("operational_role", "Associate"),
                "risk_score": nb_node.get("risk_score", 0.0),
                "status": nb_node.get("status", "Active")
            })
        elif lbl == "Case":
            cases_linked.append(nb_node)
        elif lbl in ("Vehicle", "FinancialAccount"):
            assets.append({
                "type": lbl,
                "name": nb_node.get("name"),
                "details": nb_node
            })
        elif lbl == "CommunicationRecord":
            communication_history.append(nb_node)
        elif lbl == "Location":
            locations.append(nb_node)

    # 2. Build Chronological Timeline
    timeline_events = []
    for c in cases_linked:
        timeline_events.append({
            "date": c.get("filed_date", "2026-01-01"),
            "event_type": "FIR Registration",
            "title": f"Booked in FIR No. {c.get('fir_number')}",
            "description": f"Filed at {c.get('station')} ({c.get('state')}) for {c.get('crime_category')}.",
            "severity": "HIGH"
        })

    timeline_events.sort(key=lambda x: x["date"], reverse=True)

    # 3. Audit log dossier inspection
    db = SessionLocal()
    try:
        username, role, uid = get_current_user_info(request)
        AuditLogger.log_action(
            db=db,
            username=username,
            user_role=role,
            action="VIEW_SUSPECT_DOSSIER",
            entity_type=node.get("label"),
            entity_id=node_id,
            details={"name": node.get("name"), "risk_score": node.get("risk_score")},
            user_id=uid
        )
    finally:
        db.close()

    return JSONResponse({
        "entity": node,
        "associates": associates,
        "connected_cases": cases_linked,
        "assets": assets,
        "communication_history": communication_history,
        "locations": locations,
        "timeline": timeline_events,
        "neighbor_count": len(neighbors)
    })
