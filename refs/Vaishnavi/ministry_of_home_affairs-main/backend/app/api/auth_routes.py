"""
Authentication & RBAC API Endpoints
"""

import json
from starlette.requests import Request
from starlette.responses import JSONResponse
from backend.app.database.connection import SessionLocal
from backend.app.database.models import User
from backend.app.security.auth import (
    verify_password,
    create_access_token,
    decode_access_token,
    ROLES,
    PERMISSIONS
)
from backend.app.security.audit import AuditLogger

async def login_endpoint(request: Request) -> JSONResponse:
    """Authenticates user and returns JWT token with role claims."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    if not username or not password:
        return JSONResponse({"error": "Username and password required"}, status_code=400)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password_hash):
            return JSONResponse({"error": "Invalid username or badge credentials"}, status_code=401)

        if not user.is_active:
            return JSONResponse({"error": "User account is suspended"}, status_code=403)

        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "badge_number": user.badge_number,
            "jurisdiction_code": user.jurisdiction_code
        }
        token = create_access_token(token_data)

        # Audit log login action
        AuditLogger.log_action(
            db=db,
            username=user.username,
            user_role=user.role,
            action="LOGIN_SUCCESS",
            entity_type="User",
            entity_id=str(user.id),
            details={"badge": user.badge_number, "jurisdiction": user.jurisdiction_code},
            user_id=user.id
        )

        return JSONResponse({
            "access_token": token,
            "token_type": "bearer",
            "user": user.to_dict(),
            "permissions": PERMISSIONS.get(user.role, [])
        })
    finally:
        db.close()

async def current_user_endpoint(request: Request) -> JSONResponse:
    """Returns the authenticated user details from the JWT header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"error": "Missing or invalid authorization token"}, status_code=401)

    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JSONResponse({"error": "Token expired or invalid"}, status_code=401)

    return JSONResponse({
        "user": {
            "id": payload.get("sub"),
            "username": payload.get("username"),
            "full_name": payload.get("full_name"),
            "role": payload.get("role"),
            "badge_number": payload.get("badge_number"),
            "jurisdiction_code": payload.get("jurisdiction_code")
        },
        "permissions": PERMISSIONS.get(payload.get("role"), [])
    })

async def list_demo_users_endpoint(request: Request) -> JSONResponse:
    """Returns demo accounts for rapid role-switching and presentation."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return JSONResponse({
            "users": [u.to_dict() for u in users],
            "available_roles": list(ROLES.values())
        })
    finally:
        db.close()
