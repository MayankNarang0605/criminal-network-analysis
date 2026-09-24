"""
Authentication & Role-Based Access Control (RBAC) Module
JWT token issuance, role validation, and password hashing
"""

import os
import hmac
import hashlib
import json
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import jwt

from backend.app.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ROLES,
    PERMISSIONS
)
from backend.app.database.connection import SessionLocal
from backend.app.database.models import User

# Secure Password Hashing using PBKDF2-HMAC-SHA256 with Salt
def hash_password(password: str) -> str:
    """Hash password with a random 16-byte salt using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return base64.b64encode(salt + dk).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored salt + PBKDF2 hash."""
    try:
        raw = base64.b64decode(hashed_password.encode("utf-8"))
        salt = raw[:16]
        stored_dk = raw[16:]
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(stored_dk, dk)
    except Exception:
        return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT token payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None

def check_permission(user_role: str, required_permission: str) -> bool:
    """Check if the user's role has the requested capability."""
    allowed = PERMISSIONS.get(user_role, [])
    return required_permission in allowed

def seed_default_users():
    """Initializes standard demonstration accounts for MHA RBAC roles."""
    db = SessionLocal()
    try:
        demo_users = [
            {
                "username": "admin",
                "password": "adminpassword",
                "full_name": "Dr. V. K. Sharma (MHA Admin)",
                "role": ROLES["ADMIN"],
                "badge_number": "MHA-DIR-001",
                "jurisdiction_code": "NCRB-HQ"
            },
            {
                "username": "io_rajesh",
                "password": "iopassword",
                "full_name": "Insp. Rajesh Kumar (Special Cell)",
                "role": ROLES["INVESTIGATOR"],
                "badge_number": "DL-POL-8492",
                "jurisdiction_code": "DL-POLICE-SPL"
            },
            {
                "username": "analyst_priya",
                "password": "analystpassword",
                "full_name": "Priya Nair (Senior Intelligence Analyst)",
                "role": ROLES["ANALYST"],
                "badge_number": "I4C-CYB-204",
                "jurisdiction_code": "I4C-CYBER"
            },
            {
                "username": "auditor_verma",
                "password": "auditorpassword",
                "full_name": "Sunil Verma (Compliance Auditor)",
                "role": ROLES["AUDITOR"],
                "badge_number": "MHA-AUD-077",
                "jurisdiction_code": "NCRB-HQ"
            }
        ]

        for u in demo_users:
            existing = db.query(User).filter(User.username == u["username"]).first()
            if not existing:
                new_user = User(
                    username=u["username"],
                    password_hash=hash_password(u["password"]),
                    full_name=u["full_name"],
                    role=u["role"],
                    badge_number=u["badge_number"],
                    jurisdiction_code=u["jurisdiction_code"],
                    is_active=True
                )
                db.add(new_user)
        db.commit()
    finally:
        db.close()
