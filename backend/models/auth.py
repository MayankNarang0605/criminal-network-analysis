"""
Authentication and Audit Log SQLAlchemy models.
Implements the 4-tier RBAC system: ADMIN, INVESTIGATING_OFFICER, INTELLIGENCE_ANALYST, AUDITOR.
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text
from backend.postgres import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    INVESTIGATING_OFFICER = "INVESTIGATING_OFFICER"
    INTELLIGENCE_ANALYST = "INTELLIGENCE_ANALYST"
    AUDITOR = "AUDITOR"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128), nullable=False)
    badge_number = Column(String(32), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.INVESTIGATING_OFFICER)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(64), nullable=False, index=True)
    action = Column(String(128), nullable=False, index=True)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(128), nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
