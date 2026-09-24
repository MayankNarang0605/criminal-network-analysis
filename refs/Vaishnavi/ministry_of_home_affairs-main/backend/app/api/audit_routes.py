"""
Audit Trail & Evidentiary Integrity API Endpoints
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.database.connection import SessionLocal
from backend.app.database.models import AuditLog
from backend.app.security.audit import AuditLogger

async def list_audit_logs_endpoint(request: Request) -> JSONResponse:
    """
    Returns chronological immutable audit records with SHA-256 signatures.
    """
    limit = int(request.query_params.get("limit", 50))
    action_filter = request.query_params.get("action")
    username_filter = request.query_params.get("username")

    db = SessionLocal()
    try:
        query = db.query(AuditLog).order_by(AuditLog.sequence_id.desc())
        if action_filter:
            query = query.filter(AuditLog.action == action_filter)
        if username_filter:
            query = query.filter(AuditLog.username == username_filter)

        logs = query.limit(limit).all()
        return JSONResponse({
            "total_fetched": len(logs),
            "logs": [l.to_dict() for l in logs]
        })
    finally:
        db.close()

async def verify_audit_chain_endpoint(request: Request) -> JSONResponse:
    """
    Performs live cryptographic SHA-256 hash-chain verification from Genesis block.
    """
    db = SessionLocal()
    try:
        result = AuditLogger.verify_integrity(db)
        return JSONResponse(result)
    finally:
        db.close()
