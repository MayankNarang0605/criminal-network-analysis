"""
Report Export & Entity Merge API Endpoints
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.graph.engine import graph_engine
from backend.app.nlp.entity_resolver import EntityResolver
from backend.app.database.connection import SessionLocal
from backend.app.security.audit import AuditLogger
from backend.app.api.case_routes import get_current_user_info

resolver = EntityResolver(graph_engine)

async def list_merge_candidates_endpoint(request: Request) -> JSONResponse:
    """
    Returns AI-suggested duplicate entity merge candidates for human-in-the-loop review.
    """
    candidates = resolver.find_merge_candidates(min_similarity=0.70)
    return JSONResponse({
        "total_candidates": len(candidates),
        "candidates": candidates
    })

async def execute_merge_endpoint(request: Request) -> JSONResponse:
    """
    Executes a confirmed entity merge, consolidating aliases, edges, and assets.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    primary_id = body.get("primary_id")
    candidate_id = body.get("candidate_id")

    if not primary_id or not candidate_id:
        return JSONResponse({"error": "primary_id and candidate_id are required."}, status_code=400)

    try:
        result = resolver.execute_merge(primary_id, candidate_id)

        # Audit log merge operation
        db = SessionLocal()
        try:
            username, role, uid = get_current_user_info(request)
            AuditLogger.log_action(
                db=db,
                username=username,
                user_role=role,
                action="ENTITY_MERGE_EXECUTED",
                entity_type="Person",
                entity_id=primary_id,
                details={"merged_candidate_id": candidate_id},
                user_id=uid
            )
        finally:
            db.close()

        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def export_dossier_endpoint(request: Request) -> JSONResponse:
    """
    Exports formal structured intelligence report for a suspect or case.
    """
    entity_id = request.path_params.get("entity_id")
    node = graph_engine.get_node(entity_id)
    if not node:
        return JSONResponse({"error": "Entity not found"}, status_code=404)

    neighbors = graph_engine.get_neighbors(entity_id, direction="both")

    # Audit log export operation
    db = SessionLocal()
    try:
        username, role, uid = get_current_user_info(request)
        AuditLogger.log_action(
            db=db,
            username=username,
            user_role=role,
            action="EXPORT_DOSSIER_REPORT",
            entity_type=node.get("label"),
            entity_id=entity_id,
            details={"name": node.get("name"), "exported_format": "JSON_REPORT"},
            user_id=uid
        )
    finally:
        db.close()

    return JSONResponse({
        "report_title": f"MHA Intelligence Dossier — {node.get('name')}",
        "generated_by": username,
        "classification_level": "CONFIDENTIAL // LAW ENFORCEMENT ONLY",
        "entity_profile": node,
        "direct_connections": [
            {
                "relation": nb.get("relation"),
                "direction": nb.get("direction"),
                "connected_entity": nb.get("node")
            } for nb in neighbors
        ]
    })
