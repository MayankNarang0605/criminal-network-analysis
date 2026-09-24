"""
Embedded storage layer.

Replaces the PostgreSQL + Neo4j + Elasticsearch + Redis stack with a single
SQLite file so the platform boots anywhere with zero infrastructure:

  * relational tables  -> SQLite
  * full-text search   -> SQLite FTS5 (BM25 ranked, same ranking family as ES)
  * graph store        -> `entities` / `relationships` tables projected into an
                          in-process NetworkX graph by app.graph.engine
  * cache              -> app.cache (in-process TTL cache)

Every query lives behind functions in this module, so swapping in a server-based
backend is a localised change.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Sequence

from app.config import settings

_LOCAL = threading.local()

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================ Access control ============================
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL,          -- admin | investigator | analyst | viewer
    unit          TEXT,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================ Source records ============================
CREATE TABLE IF NOT EXISTS cases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fir_id      TEXT UNIQUE NOT NULL,
    title       TEXT,
    description TEXT,
    station     TEXT,
    district    TEXT,
    state       TEXT,
    ipc_sections TEXT,                    -- JSON array
    crime_type  TEXT,
    status      TEXT,
    priority    TEXT,
    date_filed  TEXT,
    officer     TEXT,
    raw         TEXT,                     -- JSON of original record
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT,
    version     INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_cases_state ON cases(state);
CREATE INDEX IF NOT EXISTS idx_cases_date  ON cases(date_filed);

-- Version history for CASE_UPDATED audit
CREATE TABLE IF NOT EXISTS cases_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fir_id      TEXT NOT NULL,
    version     INTEGER NOT NULL,
    snapshot    TEXT NOT NULL,            -- JSON snapshot of previous row
    edited_by   TEXT,
    edited_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fir_id, version)
);
CREATE INDEX IF NOT EXISTS idx_cases_versions_fir ON cases_versions(fir_id);

-- ============================ Entities ============================
CREATE TABLE IF NOT EXISTS entities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id     TEXT UNIQUE NOT NULL,   -- stable app-level id, e.g. PER-000123
    type          TEXT NOT NULL,          -- Person|Organization|Phone|Vehicle|BankAccount|Location|Event|CryptoWallet|Email
    name          TEXT NOT NULL,
    normalized    TEXT NOT NULL,          -- canonical form used for matching
    aliases       TEXT DEFAULT '[]',      -- JSON array
    attributes    TEXT DEFAULT '{}',      -- JSON object
    risk_score    REAL DEFAULT 0,
    risk_factors  TEXT DEFAULT '[]',      -- JSON array of factor contributions
    kingpin_score REAL DEFAULT 0,
    source_count  INTEGER DEFAULT 0,
    first_seen    TEXT,
    last_seen     TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_norm ON entities(normalized);
CREATE INDEX IF NOT EXISTS idx_entities_risk ON entities(risk_score DESC);

-- ============================ Relationships ============================
CREATE TABLE IF NOT EXISTS relationships (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    rel_type    TEXT NOT NULL,            -- CO_ACCUSED|CALLED|TRANSFERRED_TO|OWNS|USES|LOCATED_AT|MEMBER_OF ...
    weight      REAL DEFAULT 1.0,
    confidence  REAL DEFAULT 1.0,
    evidence    TEXT DEFAULT '[]',        -- JSON array of evidence objects
    attributes  TEXT DEFAULT '{}',
    first_seen  TEXT,
    last_seen   TEXT,
    observations INTEGER DEFAULT 1,
    UNIQUE(source_id, target_id, rel_type)
);
CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_rel_type   ON relationships(rel_type);

-- ============================ Raw signal tables ============================
CREATE TABLE IF NOT EXISTS cdr (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id     TEXT,
    caller      TEXT NOT NULL,
    callee      TEXT NOT NULL,
    ts          TEXT NOT NULL,            -- ISO 8601
    duration    INTEGER DEFAULT 0,
    call_type   TEXT,
    tower_id    TEXT,
    tower_name  TEXT,
    lat         REAL,
    lon         REAL
);
CREATE INDEX IF NOT EXISTS idx_cdr_caller ON cdr(caller);
CREATE INDEX IF NOT EXISTS idx_cdr_callee ON cdr(callee);
CREATE INDEX IF NOT EXISTS idx_cdr_ts     ON cdr(ts);

CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id       TEXT,
    ts           TEXT NOT NULL,
    from_account TEXT NOT NULL,
    from_bank    TEXT,
    from_name    TEXT,
    to_account   TEXT NOT NULL,
    to_bank      TEXT,
    to_name      TEXT,
    amount       REAL NOT NULL,
    txn_type     TEXT,
    description  TEXT,
    flagged      INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_txn_from ON transactions(from_account);
CREATE INDEX IF NOT EXISTS idx_txn_to   ON transactions(to_account);
CREATE INDEX IF NOT EXISTS idx_txn_ts   ON transactions(ts);

-- ============================ Derived intelligence ============================
CREATE TABLE IF NOT EXISTS entity_cases (
    entity_id TEXT NOT NULL,
    fir_id    TEXT NOT NULL,
    role      TEXT,                       -- accused|complainant|victim|witness|mentioned
    PRIMARY KEY (entity_id, fir_id, role)
);

CREATE TABLE IF NOT EXISTS communities (
    community_id INTEGER NOT NULL,
    entity_id    TEXT NOT NULL,
    label        TEXT,
    cohesion     REAL,
    PRIMARY KEY (community_id, entity_id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type  TEXT NOT NULL,
    severity    TEXT NOT NULL,            -- critical|high|medium|low
    title       TEXT NOT NULL,
    description TEXT,
    entity_id   TEXT,
    evidence    TEXT DEFAULT '{}',
    score       REAL DEFAULT 0,
    status      TEXT DEFAULT 'open',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_alerts_sev ON alerts(severity);

CREATE TABLE IF NOT EXISTS patterns (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,
    typology     TEXT,
    severity     TEXT,
    confidence   REAL,
    summary      TEXT,
    members      TEXT DEFAULT '[]',
    detail       TEXT DEFAULT '{}',
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================ Blockchain audit ledger ============================
CREATE TABLE IF NOT EXISTS audit_chain (
    idx        INTEGER PRIMARY KEY,       -- block height, 0 = genesis
    ts         TEXT NOT NULL,
    actor      TEXT,
    action     TEXT NOT NULL,
    resource   TEXT,
    payload    TEXT DEFAULT '{}',
    prev_hash  TEXT NOT NULL,
    nonce      INTEGER DEFAULT 0,
    hash       TEXT NOT NULL
);

-- ============================ Ground truth (evaluation only) ============================
CREATE TABLE IF NOT EXISTS ground_truth (
    entity_name TEXT NOT NULL,
    phone       TEXT PRIMARY KEY,         -- hard identifier: survives name variants
    true_role   TEXT,                     -- kingpin|lieutenant|operative|mule|courier|peripheral
    network     TEXT
);

-- ============================ Full text search ============================
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    ref_id, ref_type, title, body, meta, tokenize='porter unicode61'
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_conn() -> sqlite3.Connection:
    """One connection per thread (SQLite connections are not thread-safe)."""
    conn = getattr(_LOCAL, "conn", None)
    if conn is None:
        conn = _connect()
        _LOCAL.conn = conn
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Transaction scope: commits on success, rolls back on exception."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    # Lightweight migration for existing DBs created before versioned cases
    for col, coldef in (("updated_at", "TEXT"), ("version", "INTEGER DEFAULT 1")):
        try:
            conn.execute(f"ALTER TABLE cases ADD COLUMN {col} {coldef}")
        except Exception:
            pass
    # Ensure cases_versions exists for old DBs
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cases_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, fir_id TEXT NOT NULL, version INTEGER NOT NULL, snapshot TEXT NOT NULL, edited_by TEXT, edited_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(fir_id, version))"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_versions_fir ON cases_versions(fir_id)")
    conn.commit()


def reset_db() -> None:
    """Drop all analytical content. Used by the ingest pipeline for clean loads."""
    conn = get_conn()
    for table in (
        "entities", "relationships", "cases", "cdr", "transactions",
        "entity_cases", "communities", "alerts", "patterns",
        "search_index", "ground_truth",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


# --------------------------------------------------------------------------
# Query helpers
# --------------------------------------------------------------------------
def query(sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    return get_conn().execute(sql, params).fetchall()


def query_one(sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
    return get_conn().execute(sql, params).fetchone()


def execute(sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
    with tx() as conn:
        return conn.execute(sql, params)


def executemany(sql: str, seq: Iterable[Sequence[Any]]) -> None:
    with tx() as conn:
        conn.executemany(sql, seq)


def scalar(sql: str, params: Sequence[Any] = (), default: Any = 0) -> Any:
    row = query_one(sql, params)
    if row is None:
        return default
    value = row[0]
    return default if value is None else value


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def jload(value: Any, default: Any) -> Any:
    """Tolerant JSON decode for TEXT columns holding JSON."""
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def jdump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
