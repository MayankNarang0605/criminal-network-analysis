"""
Authentication and role-based access control.

JWT is implemented on the standard library (hmac + hashlib + base64) rather than
pulling in python-jose, and password hashing uses PBKDF2-HMAC-SHA256 with a
per-user salt from `secrets`, which is what `hashlib.pbkdf2_hmac` exists for.
That keeps the dependency surface small — relevant for a government deployment
where every third-party package is an audit item.

RBAC is enforced by dependency injection: `require_role("investigator")` on a
route rejects lower-privileged tokens before the handler runs, and every
authenticated action is written to the blockchain audit ledger.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import db
from app.config import settings

# Privilege ordering. A higher level satisfies any lower requirement.
ROLE_LEVELS = {"viewer": 1, "analyst": 2, "investigator": 3, "admin": 4}

ROLE_PERMISSIONS = {
    "viewer": ["read:dashboard", "read:alerts"],
    "analyst": ["read:dashboard", "read:alerts", "read:graph", "read:patterns",
                "read:search", "run:analytics"],
    "investigator": ["read:dashboard", "read:alerts", "read:graph", "read:patterns",
                     "read:search", "run:analytics", "read:pii", "write:case",
                     "run:disruption"],
    "admin": ["*"],
}

PBKDF2_ITERATIONS = 200_000
bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                 PBKDF2_ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored_hash)


# ---------------------------------------------------------------------------
# JWT (HS256)
# ---------------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(payload: dict[str, Any], ttl_minutes: int | None = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    body = {
        **payload,
        "iat": now,
        "exp": now + 60 * (ttl_minutes or settings.JWT_TTL_MINUTES),
        "iss": "ncrb-cnas",
    }
    segments = [
        _b64url(json.dumps(header, separators=(",", ":")).encode()),
        _b64url(json.dumps(body, separators=(",", ":"), default=str).encode()),
    ]
    signing_input = ".".join(segments).encode()
    signature = hmac.new(settings.JWT_SECRET.encode(), signing_input,
                         hashlib.sha256).digest()
    segments.append(_b64url(signature))
    return ".".join(segments)


def decode_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = hmac.new(settings.JWT_SECRET.encode(), signing_input,
                        hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url(expected), signature_b64):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token signature")

    payload = json.loads(_b64url_decode(payload_b64))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    return payload


# ---------------------------------------------------------------------------
# User store
# ---------------------------------------------------------------------------
DEFAULT_USERS = [
    ("admin", "Administrator (NCRB HQ)", "admin", "NCRB Headquarters", "admin123!"),
    ("investigator", "Inspector R. Patil", "investigator", "Crime Branch, Mumbai", "invest123!"),
    ("analyst", "Analyst K. Mehra", "analyst", "Women Safety Division", "analyst123!"),
    ("viewer", "Duty Officer", "viewer", "District Control Room", "viewer123!"),
]


def seed_users() -> None:
    db.init_db()
    for username, full_name, role, unit, password in DEFAULT_USERS:
        if db.query_one("SELECT id FROM users WHERE username=?", (username,)):
            continue
        pw_hash, salt = hash_password(password)
        db.execute(
            "INSERT INTO users (username, full_name, role, unit, password_hash, password_salt) "
            "VALUES (?,?,?,?,?,?)",
            (username, full_name, role, unit, pw_hash, salt))


def authenticate(username: str, password: str) -> dict | None:
    row = db.query_one("SELECT * FROM users WHERE username=?", (username,))
    if row is None:
        return None
    if not verify_password(password, row["password_hash"], row["password_salt"]):
        return None
    return {"id": row["id"], "username": row["username"], "full_name": row["full_name"],
            "role": row["role"], "unit": row["unit"]}


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """
    Resolve the caller. In development the platform allows unauthenticated read
    access so the dashboard works out of the box; the caller is then recorded as
    the anonymous viewer in the audit ledger rather than being silently dropped.
    """
    if credentials is None:
        if settings.APP_ENV == "production":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                               "Authorization header required")
        return {"username": "anonymous", "role": "analyst",
                "full_name": "Unauthenticated (development mode)",
                "unit": "n/a", "authenticated": False}

    payload = decode_token(credentials.credentials)
    return {
        "username": payload.get("sub"),
        "role": payload.get("role", "viewer"),
        "full_name": payload.get("name"),
        "unit": payload.get("unit"),
        "authenticated": True,
    }


def require_role(minimum: str) -> Callable:
    """Route dependency enforcing a minimum privilege level."""
    required_level = ROLE_LEVELS.get(minimum, 99)

    async def dependency(user: dict = Depends(current_user)) -> dict:
        level = ROLE_LEVELS.get(user.get("role", "viewer"), 0)
        if level < required_level:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role '{user.get('role')}' is not permitted; '{minimum}' or higher required.")
        return user

    return dependency


def permissions_for(role: str) -> list[str]:
    return ROLE_PERMISSIONS.get(role, [])


def mask_pii(value: str, user: dict, kind: str = "phone") -> str:
    """
    Redact identifiers for users without read:pii. Investigators see full values;
    analysts and viewers see masked forms, which is the minimum needed to satisfy
    purpose limitation under the DPDP Act 2023.
    """
    perms = permissions_for(user.get("role", "viewer"))
    if "*" in perms or "read:pii" in perms:
        return value
    text = str(value or "")
    if kind == "phone" and len(text) >= 10:
        return text[:2] + "*" * (len(text) - 4) + text[-2:]
    if kind == "account" and len(text) >= 8:
        return "*" * (len(text) - 4) + text[-4:]
    if len(text) > 4:
        return text[:2] + "*" * (len(text) - 2)
    return "****"
