"""
Tamper-Evident Hash-Chained Audit Trail Module
Cryptographically chains every investigator query, view, export, and edit
using SHA-256 to ensure complete evidentiary integrity and compliance.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from backend.app.database.models import AuditLog

GENESIS_HASH = "0" * 64

class AuditLogger:
    """
    Manages immutable, tamper-evident audit logs using cryptographic hash chaining.
    """

    @staticmethod
    def _compute_hash(
        prev_hash: str,
        sequence_id: int,
        timestamp_str: str,
        username: str,
        action: str,
        entity_id: Optional[str],
        details_json: str
    ) -> str:
        """Calculates SHA-256 digest over log entry fields."""
        payload = f"{prev_hash}|{sequence_id}|{timestamp_str}|{username}|{action}|{entity_id or ''}|{details_json}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def log_action(
        cls,
        db: Session,
        username: str,
        user_role: str,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        ip_address: str = "127.0.0.1"
    ) -> AuditLog:
        """
        Appends a new audit record cryptographically linked to the previous log entry.
        """
        # Fetch the latest log to obtain sequence_id and previous hash
        last_log = db.query(AuditLog).order_by(AuditLog.sequence_id.desc()).first()

        sequence_id = (last_log.sequence_id + 1) if last_log else 1
        prev_hash = last_log.current_hash if last_log else GENESIS_HASH
        
        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
        details_json = json.dumps(details or {}, sort_keys=True)

        current_hash = cls._compute_hash(
            prev_hash=prev_hash,
            sequence_id=sequence_id,
            timestamp_str=timestamp_str,
            username=username,
            action=action,
            entity_id=entity_id,
            details_json=details_json
        )

        entry = AuditLog(
            sequence_id=sequence_id,
            timestamp=now,
            user_id=user_id,
            username=username,
            user_role=user_role,
            ip_address=ip_address,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            details_json=details_json,
            prev_hash=prev_hash,
            current_hash=current_hash
        )

        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @classmethod
    def verify_integrity(cls, db: Session) -> Dict[str, Any]:
        """
        Walks the entire audit log chain from sequence 1 to the end,
        re-computing every SHA-256 hash to prove zero tampering.
        """
        logs = db.query(AuditLog).order_by(AuditLog.sequence_id.asc()).all()

        if not logs:
            return {
                "valid": True,
                "total_records": 0,
                "message": "Audit chain is empty. Genesis state intact."
            }

        expected_prev_hash = GENESIS_HASH
        for idx, entry in enumerate(logs):
            # Check previous hash pointer
            if entry.prev_hash != expected_prev_hash:
                return {
                    "valid": False,
                    "failed_at_sequence": entry.sequence_id,
                    "reason": f"Broken chain link at log sequence #{entry.sequence_id}. Expected prev_hash {expected_prev_hash[:12]}..., found {entry.prev_hash[:12]}...",
                    "tampered_log_id": entry.id
                }

            # Recompute current hash
            if isinstance(entry.timestamp, datetime):
                timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                timestamp_str = str(entry.timestamp)[:19]

            computed_hash = cls._compute_hash(
                prev_hash=entry.prev_hash,
                sequence_id=entry.sequence_id,
                timestamp_str=timestamp_str,
                username=entry.username,
                action=entry.action,
                entity_id=entry.entity_id,
                details_json=entry.details_json
            )

            if computed_hash != entry.current_hash:
                return {
                    "valid": False,
                    "failed_at_sequence": entry.sequence_id,
                    "reason": f"Cryptographic signature mismatch at log sequence #{entry.sequence_id}. Record data was modified post-logging!",
                    "tampered_log_id": entry.id
                }

            expected_prev_hash = entry.current_hash

        return {
            "valid": True,
            "total_records": len(logs),
            "latest_sequence": logs[-1].sequence_id,
            "latest_block_hash": logs[-1].current_hash,
            "message": f"Cryptographic integrity verified across all {len(logs)} audit entries. Hash-chain is unbroken and tamper-free."
        }
