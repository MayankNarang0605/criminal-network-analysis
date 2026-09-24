"""
Unit Tests for Tamper-Evident SHA-256 Hash Chained Audit Trail
"""

from backend.app.database.connection import SessionLocal, init_db
from backend.app.database.models import AuditLog
from backend.app.security.audit import AuditLogger

def test_audit_hash_chain():
    init_db()
    db = SessionLocal()
    try:
        # Clear audit logs for clean test
        db.query(AuditLog).delete()
        db.commit()

        # Log 3 actions
        log1 = AuditLogger.log_action(db, "officer_1", "Investigating Officer", "SEARCH", "Person", "P_1", {"query": "Raju"})
        log2 = AuditLogger.log_action(db, "officer_2", "Intelligence Analyst", "VIEW_DOSSIER", "Person", "P_1", {"source": "Graph"})
        log3 = AuditLogger.log_action(db, "admin", "Admin", "EXPORT_REPORT", "Case", "CASE_101", {"format": "PDF"})

        # Verify chain integrity
        res = AuditLogger.verify_integrity(db)
        assert res["valid"] is True
        assert res["total_records"] == 3
        print("✓ Cryptographic Audit Log verification test passed!")

        # Simulate tampering
        log2.details_json = '{"tampered": true}'
        db.commit()

        tampered_res = AuditLogger.verify_integrity(db)
        assert tampered_res["valid"] is False
        assert tampered_res["failed_at_sequence"] == 2
        print("✓ Tamper detection successfully flagged modified record!")

        # Restore
        db.query(AuditLog).delete()
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    test_audit_hash_chain()
