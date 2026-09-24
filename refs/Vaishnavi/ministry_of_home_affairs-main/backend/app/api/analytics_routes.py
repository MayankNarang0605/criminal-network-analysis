"""
Network Science, Key Players, Community Detection & Link Prediction Endpoints
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.graph.engine import graph_engine
from backend.app.graph.analytics import GraphAnalytics
from backend.app.graph.link_prediction import LinkPredictor
from backend.app.database.connection import SessionLocal
from backend.app.security.audit import AuditLogger
from backend.app.api.case_routes import get_current_user_info

analytics = GraphAnalytics(graph_engine)
link_predictor = LinkPredictor(graph_engine)

async def key_players_ranking_endpoint(request: Request) -> JSONResponse:
    """
    Returns ranked suspects based on composite risk scoring and network centrality measures
    with full Explainable AI (XAI) breakdown.
    """
    ranked_persons = analytics.compute_composite_risk_score()
    
    return JSONResponse({
        "total_suspects": len(ranked_persons),
        "rankings": ranked_persons
    })

async def community_detection_endpoint(request: Request) -> JSONResponse:
    """
    Executes Louvain Community Detection algorithm to discover operational crime cells / gangs.
    Returns modularity score and member groupings.
    """
    communities_data = analytics.detect_communities()
    
    return JSONResponse(communities_data)

async def shortest_path_endpoint(request: Request) -> JSONResponse:
    """
    Solves the shortest relational path between two entities and returns step-by-step chain explanations.
    """
    source_id = request.query_params.get("source_id", "").strip()
    target_id = request.query_params.get("target_id", "").strip()

    if not source_id or not target_id:
        return JSONResponse({"error": "Both source_id and target_id parameters are required."}, status_code=400)

    result = analytics.find_shortest_path(source_id, target_id)

    # Audit log path-finding query
    db = SessionLocal()
    try:
        username, role, uid = get_current_user_info(request)
        AuditLogger.log_action(
            db=db,
            username=username,
            user_role=role,
            action="SHORTEST_PATH_QUERY",
            entity_type="GraphPath",
            entity_id=f"{source_id}->{target_id}",
            details={"source": source_id, "target": target_id, "found": result.get("found", False)},
            user_id=uid
        )
    finally:
        db.close()

    return JSONResponse(result)

async def link_predictions_endpoint(request: Request) -> JSONResponse:
    """
    Returns AI/Graph-ML missing link predictions for hidden or unrecorded associate relationships.
    """
    node_id = request.query_params.get("node_id")
    top_k = int(request.query_params.get("top_k", 15))
    min_score = float(request.query_params.get("min_score", 0.2))

    predictions = link_predictor.predict_missing_links(node_id=node_id, top_k=top_k, min_score=min_score)

    return JSONResponse({
        "total_predictions": len(predictions),
        "predictions": predictions
    })
