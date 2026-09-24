"""
Authentication & RBAC Router.
Implements login, current-user introspection, demo user seeding, and audit trail inspection.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.postgres import get_db
from backend.models.auth import User, UserRole, AuditLog
from backend.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_roles,
    log_audit_event,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    badge_number: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AuditEntryResponse(BaseModel):
    id: int
    username: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    details: Optional[str]
    timestamp: str

    class Config:
        from_attributes = True


DEMO_USERS = [
    {
        "username": "admin",
        "password": "Admin@123",
        "full_name": "Chief Administrator",
        "badge_number": "HQ-ADMIN-01",
        "role": UserRole.ADMIN,
    },
    {
        "username": "officer",
        "password": "Officer@123",
        "full_name": "Senior Investigating Officer Rajesh Kumar",
        "badge_number": "DL-INV-4412",
        "role": UserRole.INVESTIGATING_OFFICER,
    },
    {
        "username": "analyst",
        "password": "Analyst@123",
        "full_name": "Intelligence Analyst Neha Sharma",
        "badge_number": "INT-ANL-882",
        "role": UserRole.INTELLIGENCE_ANALYST,
    },
    {
        "username": "auditor",
        "password": "Auditor@123",
        "full_name": "Independent Oversight Auditor Verma",
        "badge_number": "AUD-V-109",
        "role": UserRole.AUDITOR,
    },
]


def seed_default_users(db: Session):
    """Ensure standard demo users exist for testing."""
    for u in DEMO_USERS:
        existing = db.query(User).filter(User.username == u["username"]).first()
        if not existing:
            new_user = User(
                username=u["username"],
                hashed_password=hash_password(u["password"]),
                full_name=u["full_name"],
                badge_number=u["badge_number"],
                role=u["role"],
                is_active=True,
            )
            db.add(new_user)
    db.commit()


@router.post("/seed")
def seed_users_endpoint(db: Session = Depends(get_db)):
    """Seed default demo accounts."""
    seed_default_users(db)
    return {"message": "Demo users seeded successfully", "users": [u["username"] for u in DEMO_USERS]}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user with username and password, issue JWT token."""
    user = db.query(User).filter(User.username == req.username).first()
    
    # Auto-seed if database is empty on first boot
    if not user and db.query(User).count() == 0:
        seed_default_users(db)
        user = db.query(User).filter(User.username == req.username).first()

    if not user or not verify_password(req.password, user.hashed_password):
        log_audit_event(
            db=db,
            username=req.username,
            action="LOGIN_FAILED",
            ip_address=request.client.host if request.client else None,
            details="Invalid credentials attempt",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or inactive",
        )

    access_token = create_access_token(data={"sub": user.username, "role": user.role.value})
    
    log_audit_event(
        db=db,
        username=user.username,
        user_id=user.id,
        action="LOGIN_SUCCESS",
        ip_address=request.client.host if request.client else None,
        details=f"User {user.username} authenticated with role {user.role.value}",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return profile and permissions for currently authenticated user."""
    return UserResponse.model_validate(current_user)


@router.get("/audit", dependencies=[Depends(require_roles([UserRole.ADMIN, UserRole.AUDITOR]))])
def list_audit_trail(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Retrieve immutable audit trail (restricted to ADMIN and AUDITOR)."""
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": l.id,
            "username": l.username,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "ip_address": l.ip_address,
            "details": l.details,
            "timestamp": l.timestamp.isoformat(),
        }
        for l in logs
    ]
