"""
Alert generation.

Turns analytical output into a prioritised worklist. Alerts are deduplicated and
each carries the evidence that produced it, because an alert an investigator
cannot verify is an alert they will learn to ignore.
"""
from __future__ import annotations

from app import db
from app.nlp import ipc
from app.nlp import normalize as nz


def generate_alerts() -> dict:
    db.execute("DELETE FROM alerts")
    rows: list[tuple] = []

    # 1. High-tier command actors.
    for row in db.query(
        "SELECT entity_id, name, kingpin_score, risk_score FROM entities "
        "WHERE type='Person' AND kingpin_score >= 40 ORDER BY kingpin_score DESC"
    ):
        severity = "critical" if row["kingpin_score"] >= 60 else "high"
        rows.append((
            "command_actor", severity,
            f"Probable command-tier actor: {row['name']}",
            (f"{row['name']} scores {row['kingpin_score']:.1f}/100 on the composite "
             f"Kingpin Influence Score, indicating a controlling rather than "
             f"operational role. Recommend prioritised surveillance and financial tracing."),
            row["entity_id"],
            db.jdump({"kingpin_score": row["kingpin_score"], "risk_score": row["risk_score"]}),
            row["kingpin_score"],
        ))

    # 2. Critical-risk individuals.
    for row in db.query(
        "SELECT entity_id, name, risk_score FROM entities "
        "WHERE type='Person' AND risk_score >= 70 ORDER BY risk_score DESC LIMIT 30"
    ):
        rows.append((
            "high_risk_individual", "high",
            f"High-risk individual: {row['name']}",
            (f"Composite risk score {row['risk_score']:.1f}/100 driven by criminal "
             f"history, network position and financial or communication anomalies."),
            row["entity_id"],
            db.jdump({"risk_score": row["risk_score"]}),
            row["risk_score"],
        ))

    # 3. Critical pattern findings.
    for row in db.query(
        "SELECT id, pattern_type, typology, severity, confidence, summary, members "
        "FROM patterns WHERE severity IN ('critical','high') ORDER BY confidence DESC LIMIT 60"
    ):
        members = db.jload(row["members"], [])
        # Resolve raw account/phone strings (e.g. "30142567890") to canonical entity_ids (ACC-..., PHN-...) for navigability
        resolved_members = []
        for m in members:
            eid = None
            for typ, fn in (("BankAccount", nz.normalize_account), ("Phone", nz.normalize_phone), ("Vehicle", nz.normalize_vehicle)):
                try:
                    norm = fn(m) if fn else m
                except Exception:
                    norm = m
                if not norm:
                    continue
                r = db.query_one("SELECT entity_id FROM entities WHERE type=? AND normalized=?", (typ, norm))
                if r:
                    eid = r["entity_id"]
                    break
            if not eid:
                try:
                    norm = nz.normalize_name(m) if m else m
                    r = db.query_one("SELECT entity_id FROM entities WHERE type='Person' AND normalized=?", (norm,))
                    if r:
                        eid = r["entity_id"]
                except Exception:
                    pass
            if not eid:
                r = db.query_one("SELECT entity_id FROM entities WHERE normalized=?", (str(m).strip().upper(),))
                eid = r["entity_id"] if r else m
            resolved_members.append(eid)
        # Use resolved first member for navigation, keep original members in evidence for audit trail
        nav_id = resolved_members[0] if resolved_members else None
        rows.append((
            f"pattern:{row['pattern_type']}", row["severity"],
            f"{row['typology']}",
            row["summary"],
            nav_id,
            db.jdump({"pattern_id": row["id"], "members": resolved_members, "raw_members": members,
                      "confidence": row["confidence"]}),
            (row["confidence"] or 0) * 100,
        ))

    # 4. Women Safety Division escalations.
    for row in db.query(
        "SELECT fir_id, title, ipc_sections, state, district, priority, status FROM cases"
    ):
        sections = db.jload(row["ipc_sections"], [])
        if not ipc.is_women_safety(sections):
            continue
        gravity = ipc.gravity_of(sections)
        severity = "critical" if gravity >= 9 else "high"
        rows.append((
            "women_safety_case", severity,
            f"Women Safety Division case requiring review: {row['fir_id']}",
            (f"{row['fir_id']} in {row['district']}, {row['state']} invokes "
             f"section(s) {', '.join(sections)} within the Women Safety mandate "
             f"(max gravity {gravity}/10). Current status: {row['status']}."),
            None,
            db.jdump({"fir_id": row["fir_id"], "sections": ipc.describe(sections),
                      "gravity": gravity}),
            gravity * 10,
        ))

    # 5. Cross-jurisdictional networks: a cell operating in 3+ states needs
    #    coordination that a single state police unit cannot provide alone.
    for row in db.query(
        "SELECT c.community_id, COUNT(DISTINCT ca.state) AS states, "
        "GROUP_CONCAT(DISTINCT ca.state) AS state_list, COUNT(DISTINCT c.entity_id) AS members "
        "FROM communities c "
        "JOIN entity_cases ec ON ec.entity_id = c.entity_id "
        "JOIN cases ca ON ca.fir_id = ec.fir_id "
        "GROUP BY c.community_id HAVING states >= 3"
    ):
        rows.append((
            "cross_jurisdiction", "high",
            f"Cross-jurisdictional network: Cell-{row['community_id']:02d}",
            (f"Detected cell {row['community_id']} spans {row['states']} states "
             f"({row['state_list']}) across {row['members']} actors. "
             f"Recommend inter-state coordination via NCRB CCTNS."),
            None,
            db.jdump({"community_id": row["community_id"], "states": row["state_list"],
                      "member_count": row["members"]}),
            row["states"] * 20,
        ))

    db.executemany(
        "INSERT INTO alerts (alert_type, severity, title, description, entity_id, "
        "evidence, score) VALUES (?,?,?,?,?,?,?)", rows)

    by_sev = {r["severity"]: r["c"] for r in db.query(
        "SELECT severity, COUNT(*) AS c FROM alerts GROUP BY severity")}
    by_type = {r["alert_type"]: r["c"] for r in db.query(
        "SELECT alert_type, COUNT(*) AS c FROM alerts GROUP BY alert_type")}
    return {"total": len(rows), "by_severity": by_sev, "by_type": by_type}


def list_alerts(severity: str | None = None, limit: int = 100) -> list[dict]:
    sql = ("SELECT a.*, e.name AS entity_name FROM alerts a "
           "LEFT JOIN entities e ON e.entity_id = a.entity_id WHERE 1=1")
    params: list = []
    if severity:
        sql += " AND a.severity = ?"
        params.append(severity)
    sql += " ORDER BY CASE a.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 " \
           "WHEN 'medium' THEN 2 ELSE 3 END, a.score DESC LIMIT ?"
    params.append(limit)
    out = []
    for row in db.query(sql, params):
        item = dict(row)
        item["evidence"] = db.jload(item["evidence"], {})
        out.append(item)
    return out
