"""
Security and authentication utilities:
- Password hashing (bcrypt / pbkdf2 fallback)
- JWT access token generation & verification
- RBAC role enforcement dependencies
- Audit trail recorder
"""
import os
import time
import hashlib
import hmac
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.config import settings
from backend.logging_config import logger
from backend.postgres import get_db
from backend.models.auth import User, UserRole, AuditLog

# Try importing passlib / jose; provide zero-crash fallbacks if run outside full container
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    pwd_context = None

try:
    from jose import JWTError, jwt
except ImportError:
    JWTError = Exception
    jwt = None


def hash_password(password: str) -> str:
    """Hash plain password using bcrypt or PBKDF2-SHA256 fallback."""
    if pwd_context:
        try:
            return pwd_context.hash(password)
        except Exception:
            pass
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"pbkdf2_sha256${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    if pwd_context and not hashed_password.startswith("pbkdf2_sha256$"):
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            pass
    if hashed_password.startswith("pbkdf2_sha256$"):
        parts = hashed_password.split("$")
        if len(parts) == 3:
            salt = bytes.fromhex(parts[1])
            expected_key = bytes.fromhex(parts[2])
            check_key = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, 100000)
            return hmac.compare_digest(expected_key, check_key)
    return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT token."""
    to_encode = data.copy()
    expire_minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", getattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 480))
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=expire_minutes))
    to_encode.update({"exp": expire})

    if jwt:
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    # Secure fallback HMAC-SHA256 JWT
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_dict = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in to_encode.items()}
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")
    signing_input = f"{header}.{payload}".encode()
    signature = base64.urlsafe_b64encode(
        hmac.new(settings.JWT_SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    if jwt:
        try:
            return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # Fallback HMAC-SHA256 decoder
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token")
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(settings.JWT_SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
        ).decode().rstrip("=")
        if not hmac.compare_digest(signature_b64, expected_sig):
            raise ValueError("Signature mismatch")
        padding = "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode())
        return payload
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


http_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: Extract and verify current user from Bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    username: str = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return user


def require_roles(allowed_roles: List[UserRole]):
    """Role-based authorization dependency guard."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {[r.value for r in allowed_roles]}",
            )
        return current_user
    return role_checker


def log_audit_event(
    db: Session,
    username: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None,
    user_id: Optional[int] = None,
):
    """Record an immutable action in the audit log table."""
    try:
        log_entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details,
            timestamp=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()
    except Exception as exc:
        logger.error(f"Failed to record audit log: {exc}")
        db.rollback()
