"""
Neo4j schema initialization — creates constraints and indexes on startup.
Adapted from Thxrun's schema_manager with full node types from the build spec Section 6.3.
"""
from neo4j import Session
from backend.logging_config import logger

_CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Case) REQUIRE c.case_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (ph:Phone) REQUIRE ph.phone_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:SIM) REQUIRE s.sim_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Device) REQUIRE d.device_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Vehicle) REQUIRE v.vehicle_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (b:BankAccount) REQUIRE b.account_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Organization) REQUIRE o.organization_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.location_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Transaction) REQUIRE t.transaction_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Evidence) REQUIRE e.evidence_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FIR) REQUIRE f.fir_id IS UNIQUE",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.full_name)",
    "CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.city)",
    "CREATE INDEX IF NOT EXISTS FOR (c:Case) ON (c.crime_type)",
    "CREATE INDEX IF NOT EXISTS FOR (c:Case) ON (c.difficulty)",
    "CREATE INDEX IF NOT EXISTS FOR (t:Transaction) ON (t.case_id)",
    "CREATE INDEX IF NOT EXISTS FOR (t:Transaction) ON (t.timestamp)",
]


def init_neo4j_schema(session: Session) -> None:
    """Create all constraints and indexes idempotently."""
    for stmt in _CONSTRAINTS:
        try:
            session.run(stmt)
        except Exception as exc:
            logger.warning(f"Constraint creation warning (may already exist): {exc}")
    for stmt in _INDEXES:
        try:
            session.run(stmt)
        except Exception as exc:
            logger.warning(f"Index creation warning (may already exist): {exc}")
    logger.info(f"Neo4j schema: {len(_CONSTRAINTS)} constraints, {len(_INDEXES)} indexes initialized.")
