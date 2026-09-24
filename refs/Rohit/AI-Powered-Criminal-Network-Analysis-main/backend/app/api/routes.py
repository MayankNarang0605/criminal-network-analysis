"""API routers — the complete REST surface for the investigator dashboard."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app import db
from app.alerts import rules as alert_rules
from app.analytics import evaluate as evaluation
from app.analytics.patterns import run_all_detectors
from app.auth import security
from app.blockchain.ledger import chain, log
from app.config import settings
from app.etl.pipeline import run_pipeline
from app.graph.engine import engine
from app.ml.risk import RiskScorer, risk_band
from app.nlp.extractor import EntityExtractor, summarise
from app.nlp import ipc as ipc_kb
from app.search import engine as search_engine
from app.women_safety import service as women_safety

# ===========================================================================
auth_router = APIRouter()


@auth_router.post("/login", summary="Authenticate and obtain a bearer token")
async def login(payload: dict = Body(..., examples=[{"username": "investigator", "password": "invest123!"}])):
    username = str(payload.get("username", ""))
    password = str(payload.get("password", ""))
    user = security.authenticate(username, password)
    if user is None:
        log(username or "unknown", "LOGIN_FAILED", "auth")
        raise HTTPException(401, "Invalid credentials")
    token = security.create_token({"sub": user["username"], "role": user["role"],
                                   "name": user["full_name"], "unit": user["unit"]})
    log(user["username"], "LOGIN_SUCCESS", "auth", role=user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": 480,
        "user": {**user, "permissions": security.permissions_for(user["role"])},
    }


@auth_router.get("/me", summary="Current caller identity and permissions")
async def me(user: dict = Depends(security.current_user)):
    return {**user, "permissions": security.permissions_for(user.get("role", "viewer"))}


@auth_router.get("/roles", summary="Role hierarchy and permission matrix")
async def roles():
    return {
        "hierarchy": security.ROLE_LEVELS,
        "permissions": security.ROLE_PERMISSIONS,
        "note": ("Privilege levels are ordinal: a higher level satisfies any lower "
                 "requirement. PII is masked for roles lacking 'read:pii'."),
    }


# ===========================================================================
data_router = APIRouter()


@data_router.post("/ingest", summary="Run the full ingestion and enrichment pipeline")
async def ingest(
    use_samples: bool = Query(True, description="Include the bundled sample FIR/CDR/ledger files"),
    synthetic_networks: int = Query(6, ge=0, le=20,
                                    description="Number of labelled synthetic networks to generate"),
    seed: int = Query(20260828, description="Deterministic generator seed"),
    user: dict = Depends(security.require_role("analyst")),
):
    result = run_pipeline(use_samples=use_samples, synthetic_networks=synthetic_networks,
                          seed=seed, reset=True)
    log(user.get("username", "system"), "DATA_INGEST", "corpus",
        networks=synthetic_networks, samples=use_samples)
    return result


@data_router.get("/stats", summary="Corpus statistics")
async def stats():
    return {
        "cases": db.scalar("SELECT COUNT(*) FROM cases"),
        "entities": db.scalar("SELECT COUNT(*) FROM entities"),
        "entities_by_type": {r["type"]: r["c"] for r in db.query(
            "SELECT type, COUNT(*) AS c FROM entities GROUP BY type ORDER BY c DESC")},
        "relationships": db.scalar("SELECT COUNT(*) FROM relationships"),
        "relationships_by_type": {r["rel_type"]: r["c"] for r in db.query(
            "SELECT rel_type, COUNT(*) AS c FROM relationships GROUP BY rel_type "
            "ORDER BY c DESC")},
        "cdr_records": db.scalar("SELECT COUNT(*) FROM cdr"),
        "transactions": db.scalar("SELECT COUNT(*) FROM transactions"),
        "flagged_transactions": db.scalar("SELECT COUNT(*) FROM transactions WHERE flagged=1"),
        "patterns": db.scalar("SELECT COUNT(*) FROM patterns"),
        "alerts": db.scalar("SELECT COUNT(*) FROM alerts"),
        "audit_blocks": db.scalar("SELECT COUNT(*) FROM audit_chain"),
    }


@data_router.get("/cases", summary="List FIRs / case records")
async def cases(
    state: str | None = None,
    crime_type: str | None = None,
    limit: int = Query(100, le=500),
):
    sql = ("SELECT fir_id, title, station, district, state, ipc_sections, crime_type, "
           "status, priority, date_filed, officer FROM cases WHERE 1=1")
    params: list[Any] = []
    if state:
        sql += " AND state = ?"
        params.append(state)
    if crime_type:
        sql += " AND crime_type = ?"
        params.append(crime_type)
    sql += " ORDER BY date_filed DESC LIMIT ?"
    params.append(limit)
    out = []
    for row in db.query(sql, params):
        item = dict(row)
        sections = db.jload(item["ipc_sections"], [])
        item["ipc_sections"] = sections
        item["section_detail"] = ipc_kb.describe(sections)
        item["max_gravity"] = ipc_kb.gravity_of(sections)
        item["women_safety_mandate"] = ipc_kb.is_women_safety(sections)
        out.append(item)
    return {"total": len(out), "cases": out}


@data_router.get("/cases/{fir_id}", summary="Full case record with linked entities")
async def case_detail(fir_id: str, user: dict = Depends(security.current_user)):
    row = db.query_one("SELECT * FROM cases WHERE fir_id = ?", (fir_id,))
    if row is None:
        raise HTTPException(404, f"Case {fir_id} not found")
    log(user.get("username", "anonymous"), "CASE_ACCESS", fir_id)

    item = dict(row)
    sections = db.jload(item["ipc_sections"], [])
    item["ipc_sections"] = sections
    item["section_detail"] = ipc_kb.describe(sections)
    item["raw"] = db.jload(item["raw"], {})
    item["summary"] = summarise(item.get("description") or "", max_sentences=3)

    linked = []
    for e in db.query(
        "SELECT e.entity_id, e.name, e.type, e.risk_score, e.kingpin_score, ec.role "
        "FROM entity_cases ec JOIN entities e ON e.entity_id = ec.entity_id "
        "WHERE ec.fir_id = ? ORDER BY e.risk_score DESC", (fir_id,)
    ):
        entry = dict(e)
        if entry["type"] == "Phone":
            entry["name"] = security.mask_pii(entry["name"], user, "phone")
        elif entry["type"] == "BankAccount":
            entry["name"] = security.mask_pii(entry["name"], user, "account")
        linked.append(entry)
    item["linked_entities"] = linked
    return item


@data_router.get("/cdr", summary="Call detail records")
async def cdr(
    number: str | None = None,
    limit: int = Query(200, le=2000),
    user: dict = Depends(security.current_user),
):
    sql = "SELECT * FROM cdr WHERE 1=1"
    params: list[Any] = []
    if number:
        sql += " AND (caller = ? OR callee = ?)"
        params += [number, number]
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    rows = []
    for row in db.query(sql, params):
        item = dict(row)
        item["caller"] = security.mask_pii(item["caller"], user, "phone")
        item["callee"] = security.mask_pii(item["callee"], user, "phone")
        rows.append(item)
    return {"total": len(rows), "records": rows}


@data_router.post("/case", summary="Add a single FIR — dashboard live-investigation path (no wipe)")
async def add_case(
    fir: dict = Body(..., examples=[{"fir_id": "FIR-2024-PB-TEST01", "station": "Test PS", "district": "Pune", "state": "Maharashtra", "date_filed": "2024-08-01", "ipc_sections": ["420","120B"], "description": "Accused Amit Rao 9876543210 used MH01AB1234...", "accused": [{"name": "Amit Rao", "phone": "9876543210"}], "crime_type": "Economic Offence"}]),
    user: dict = Depends(security.require_role("investigator")),
):
    from app.etl.pipeline import Pipeline

    fir.pop("_comment", None)
    if not fir.get("fir_id"):
        raise HTTPException(400, "fir_id is required")
    if db.query_one("SELECT fir_id FROM cases WHERE fir_id=?", (fir["fir_id"],)):
        raise HTTPException(409, f"Case {fir['fir_id']} already exists")
    # Minimal normalisation: phone/account cleanup is done inside pipeline
    result = Pipeline().add_case(fir, recompute=True)
    return result


@data_router.put("/cases/{fir_id}", summary="Update a registered FIR — admin only, versioned")
async def update_case(
    fir_id: str,
    fir: dict = Body(..., examples=[{"fir_id": "FIR-2024-PB-TEST01", "station": "Test PS", "district": "Pune", "state": "Maharashtra", "date_filed": "2024-08-01", "ipc_sections": ["420","120B"], "description": "Updated narrative...", "accused": [{"name": "Amit Rao", "phone": "9876543210"}], "crime_type": "Economic Offence"}]),
    user: dict = Depends(security.require_role("admin")),
):
    from app.etl.pipeline import Pipeline

    fir.pop("_comment", None)
    if not db.query_one("SELECT fir_id FROM cases WHERE fir_id=?", (fir_id,)):
        raise HTTPException(404, f"Case {fir_id} not found")
    new_fir_id = fir.get("fir_id", fir_id)
    if new_fir_id != fir_id and db.query_one("SELECT fir_id FROM cases WHERE fir_id=?", (new_fir_id,)):
        raise HTTPException(409, f"Case {new_fir_id} already exists")
    result = Pipeline().update_case(fir_id, fir, editor=user.get("username", "admin"), recompute=True)
    log(user.get("username", "admin"), "CASE_UPDATED", new_fir_id, from_fir=fir_id)
    return result


@data_router.get("/cases/{fir_id}/history", summary="Version history for a FIR")
async def case_history(fir_id: str, user: dict = Depends(security.current_user)):
    rows = db.query("SELECT version, snapshot, edited_by, edited_at FROM cases_versions WHERE fir_id=? ORDER BY version", (fir_id,))
    if not rows and not db.query_one("SELECT fir_id FROM cases WHERE fir_id=?", (fir_id,)):
        raise HTTPException(404, f"Case {fir_id} not found")
    out = []
    for r in rows:
        item = dict(r)
        item["snapshot"] = db.jload(item["snapshot"], {})
        out.append(item)
    cur = db.query_one("SELECT version, updated_at FROM cases WHERE fir_id=?", (fir_id,))
    return {"fir_id": fir_id, "current_version": (cur["version"] if cur else 1), "current_updated_at": (cur["updated_at"] if cur else None), "history": out}


@data_router.post("/cdr/batch", summary="Append CDR records — dashboard live-investigation path")
async def add_cdr_batch(
    payload: dict = Body(..., examples=[{"records": [{"caller": "9876543210", "callee": "9123456789", "ts": "2024-06-01 14:30:00", "duration": 120}]}]),
    user: dict = Depends(security.require_role("investigator")),
):
    from app.etl.pipeline import Pipeline

    records = payload.get("records") or payload.get("cdr") or []
    if isinstance(records, dict):
        records = [records]
    if not records:
        raise HTTPException(400, "Provide 'records' as a non-empty list")
    return Pipeline().add_cdr_batch(records, recompute=True)


@data_router.post("/transactions/batch", summary="Append ledger entries — dashboard live-investigation path")
async def add_transactions_batch(
    payload: dict = Body(..., examples=[{"records": [{"from_account": "30142567890", "to_account": "50198765432", "amount": 950000, "from_name": "Amit Rao", "to_name": "Sunita Devi"}]}]),
    user: dict = Depends(security.require_role("investigator")),
):
    from app.etl.pipeline import Pipeline

    records = payload.get("records") or payload.get("transactions") or []
    if isinstance(records, dict):
        records = [records]
    if not records:
        raise HTTPException(400, "Provide 'records' as a non-empty list")
    return Pipeline().add_transactions_batch(records, recompute=True)


@data_router.get("/transactions", summary="Financial ledger")
async def transactions(
    account: str | None = None,
    flagged_only: bool = False,
    limit: int = Query(200, le=2000),
    user: dict = Depends(security.current_user),
):
    sql = "SELECT * FROM transactions WHERE 1=1"
    params: list[Any] = []
    if account:
        sql += " AND (from_account = ? OR to_account = ?)"
        params += [account, account]
    if flagged_only:
        sql += " AND flagged = 1"
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    rows = []
    for row in db.query(sql, params):
        item = dict(row)
        item["from_account"] = security.mask_pii(item["from_account"], user, "account")
        item["to_account"] = security.mask_pii(item["to_account"], user, "account")
        rows.append(item)
    return {"total": len(rows), "records": rows}


# ===========================================================================
nlp_router = APIRouter()


@nlp_router.post("/extract", summary="Extract entities and relationships from free text")
async def extract(payload: dict = Body(..., examples=[{"text": "Accused Vikram Desai (9123456780) transferred Rs 45 lakh."}])):
    text = str(payload.get("text", ""))
    if not text.strip():
        raise HTTPException(400, "Field 'text' is required")

    known = [r["name"] for r in db.query(
        "SELECT name FROM entities WHERE type='Person' LIMIT 5000")]
    locations = [r["name"] for r in db.query(
        "SELECT name FROM entities WHERE type='Location' LIMIT 2000")]
    extractor = EntityExtractor(known_people=known, known_locations=locations)
    result = extractor.extract(text)
    payload_out = result.to_dict()
    payload_out["summary"] = summarise(text)
    payload_out["engine"] = (
        "Hybrid extractor: deterministic Indian identifier patterns (mobile, RTO "
        "plate, bank account, IFSC, PAN, IPC section, crypto wallet) + corpus-seeded "
        "gazetteer + morphological Indian-name recogniser + cue-based relation "
        "extraction. Every mention carries character offsets for evidence highlighting."
    )
    return payload_out


@nlp_router.get("/sections/{section}", summary="Look up a legal section")
async def section_lookup(section: str):
    info = ipc_kb.lookup(section)
    return {"section": section, **info}


@nlp_router.post("/summarise", summary="Extractive summary of a case narrative")
async def summarise_text(payload: dict = Body(...)):
    text = str(payload.get("text", ""))
    sentences = int(payload.get("max_sentences", 3))
    return {"summary": summarise(text, max_sentences=sentences)}


# ===========================================================================
graph_router = APIRouter()


@graph_router.get("/overview", summary="Whole-network graph payload")
async def graph_overview(
    person_only: bool = Query(False),
    limit: int = Query(600, le=3000),
):
    engine.ensure()
    g = engine.person_subgraph() if person_only else engine.G
    if g.number_of_nodes() > limit:
        # Keep the most connected nodes so the visualisation stays legible.
        top = sorted(g.degree(), key=lambda kv: -kv[1])[:limit]
        g = g.subgraph([n for n, _ in top])
    if not engine._communities:
        engine.communities()
    return engine.to_payload(g)


@graph_router.get("/entity/{entity_id}", summary="Entity profile with ego network")
async def entity_profile(
    entity_id: str,
    depth: int = Query(1, ge=1, le=3),
    user: dict = Depends(security.current_user),
):
    row = db.query_one("SELECT * FROM entities WHERE entity_id = ?", (entity_id,))
    if row is None:
        raise HTTPException(404, f"Entity {entity_id} not found")
    log(user.get("username", "anonymous"), "ENTITY_ACCESS", entity_id)
    engine.ensure()

    item = dict(row)
    item["aliases"] = db.jload(item["aliases"], [])
    item["attributes"] = db.jload(item["attributes"], {})
    item["risk_factors"] = db.jload(item["risk_factors"], [])
    item["risk_band"] = risk_band(item.get("risk_score") or 0)

    metrics = engine.centrality(person_only=True).get(entity_id, {})
    kingpin = next((k for k in engine.kingpin_ranking(top_n=0)
                    if k["entity_id"] == entity_id), None)

    relationships = []
    for r in db.query(
        "SELECT r.*, "
        "(SELECT name FROM entities WHERE entity_id = r.source_id) AS source_name, "
        "(SELECT type FROM entities WHERE entity_id = r.source_id) AS source_type, "
        "(SELECT name FROM entities WHERE entity_id = r.target_id) AS target_name, "
        "(SELECT type FROM entities WHERE entity_id = r.target_id) AS target_type "
        "FROM relationships r WHERE r.source_id = ? OR r.target_id = ? "
        "ORDER BY r.confidence DESC, r.observations DESC", (entity_id, entity_id)
    ):
        rel = dict(r)
        rel["evidence"] = db.jload(rel["evidence"], [])
        relationships.append(rel)

    cases = [dict(c) for c in db.query(
        "SELECT c.fir_id, c.title, c.crime_type, c.state, c.district, c.status, "
        "c.priority, c.date_filed, c.ipc_sections, ec.role "
        "FROM entity_cases ec JOIN cases c ON c.fir_id = ec.fir_id "
        "WHERE ec.entity_id = ? ORDER BY c.date_filed DESC", (entity_id,))]
    for c in cases:
        c["ipc_sections"] = db.jload(c["ipc_sections"], [])

    patterns = []
    for p in db.query("SELECT * FROM patterns"):
        if entity_id in db.jload(p["members"], []):
            item_p = dict(p)
            item_p["detail"] = db.jload(item_p["detail"], {})
            item_p["members"] = db.jload(item_p["members"], [])
            patterns.append(item_p)

    community = db.query_one(
        "SELECT community_id, label, cohesion FROM communities WHERE entity_id = ?",
        (entity_id,))

    return {
        "entity": item,
        "graph_metrics": metrics,
        "kingpin_assessment": kingpin,
        "community": dict(community) if community else None,
        "relationships": relationships,
        "relationship_count": len(relationships),
        "cases": cases,
        "patterns": patterns,
        "ego_network": engine.neighbourhood(entity_id, depth=depth),
    }


@graph_router.get("/entities", summary="List / filter entities")
async def entities(
    type: str | None = None,
    min_risk: float = Query(0.0, ge=0, le=100),
    order_by: str = Query("risk_score", pattern="^(risk_score|kingpin_score|name|source_count)$"),
    limit: int = Query(100, le=1000),
):
    sql = ("SELECT entity_id, type, name, aliases, risk_score, kingpin_score, "
           "source_count FROM entities WHERE risk_score >= ?")
    params: list[Any] = [min_risk]
    if type:
        sql += " AND type = ?"
        params.append(type)
    direction = "ASC" if order_by == "name" else "DESC"
    sql += f" ORDER BY {order_by} {direction} LIMIT ?"
    params.append(limit)
    out = []
    for row in db.query(sql, params):
        item = dict(row)
        item["aliases"] = db.jload(item["aliases"], [])
        item["risk_band"] = risk_band(item["risk_score"] or 0)
        out.append(item)
    return {"total": len(out), "entities": out}


@graph_router.get("/kingpins", summary="Ranked command-tier actors with explanations")
async def kingpins(top_n: int = Query(20, ge=1, le=200)):
    engine.ensure()
    if not engine._communities:
        engine.communities()
    ranking = engine.kingpin_ranking(top_n=top_n)
    return {
        "total": len(ranking),
        "weights": settings.KINGPIN_WEIGHTS,
        "methodology": (
            "Composite Kingpin Influence Score over six orthogonal signals: "
            "betweenness (brokerage), eigenvector (elite adjacency), insulation "
            "index (structural distance from operational activity), flow control "
            "(share of network throughput), role breadth (multi-domain span) and "
            "resilience impact (fragmentation on removal). Single-metric ranking is "
            "avoided because it is trivially dominated by high-volume couriers."
        ),
        "ranking": ranking,
    }


@graph_router.get("/communities", summary="Detected criminal cells")
async def communities(resolution: float = Query(1.0, ge=0.2, le=3.0)):
    engine.ensure()
    result = engine.communities(resolution=resolution)
    names = {r["entity_id"]: r["name"] for r in db.query("SELECT entity_id, name FROM entities")}
    for community in result["communities"]:
        community["member_names"] = [names.get(m, m) for m in community["members"]]
    result.pop("assignment", None)
    return result


@graph_router.get("/path", summary="Shortest connection paths between two entities")
async def path(source: str, target: str, k: int = Query(3, ge=1, le=10)):
    engine.ensure()
    paths = engine.shortest_paths(source, target, k=k)
    if not paths:
        return {"found": False, "paths": [],
                "message": "No connecting path exists in the current graph."}
    return {"found": True, "count": len(paths), "paths": paths}


@graph_router.get("/predict-links", summary="Predicted unobserved relationships")
async def predict_links(top_n: int = Query(25, ge=1, le=100)):
    engine.ensure()
    predictions = engine.predict_links(top_n=top_n)
    return {
        "total": len(predictions),
        "method": ("Ensemble of Adamic-Adar, Jaccard coefficient, preferential "
                   "attachment and community co-membership. Each prediction lists the "
                   "shared associates that justify it."),
        "predictions": predictions,
    }


@graph_router.post("/simulate-disruption", summary="Simulate arresting a set of actors")
async def simulate_disruption(
    payload: dict = Body(..., examples=[{"entity_ids": ["PER-00001"]}]),
    user: dict = Depends(security.require_role("investigator")),
):
    targets = payload.get("entity_ids") or []
    if not targets:
        raise HTTPException(400, "Provide 'entity_ids' as a non-empty list")
    engine.ensure()
    log(user.get("username", "anonymous"), "DISRUPTION_SIMULATION", ",".join(targets))
    return engine.simulate_disruption(list(targets))


@graph_router.get("/optimal-disruption", summary="Recommend the highest-impact arrest set")
async def optimal_disruption(
    budget: int = Query(3, ge=1, le=8),
    user: dict = Depends(security.require_role("investigator")),
):
    engine.ensure()
    log(user.get("username", "anonymous"), "OPTIMAL_DISRUPTION", f"budget={budget}")
    return engine.optimal_disruption(budget=budget)


@graph_router.post("/reload", summary="Rebuild the in-memory graph from storage")
async def reload_graph(user: dict = Depends(security.require_role("analyst"))):
    engine.load()
    engine.communities()
    return {"status": "reloaded", "nodes": engine.G.number_of_nodes(),
            "edges": engine.G.number_of_edges()}


# ===========================================================================
ml_router = APIRouter()


@ml_router.get("/risk", summary="Ranked risk scores with factor breakdown")
async def risk(limit: int = Query(50, ge=1, le=500), recompute: bool = False):
    engine.ensure()
    if recompute:
        scorer = RiskScorer(graph_metrics=engine.centrality(person_only=True))
        return {"total": limit, "recomputed": True,
                "scores": scorer.score_all(persist=True)[:limit]}

    out = []
    for row in db.query(
        "SELECT entity_id, name, risk_score, risk_factors FROM entities "
        "WHERE type='Person' ORDER BY risk_score DESC LIMIT ?", (limit,)
    ):
        item = dict(row)
        item["risk_factors"] = db.jload(item["risk_factors"], [])
        item["risk_band"] = risk_band(item["risk_score"] or 0)
        out.append(item)
    return {"total": len(out), "recomputed": False, "scores": out}


@ml_router.get("/risk/{entity_id}", summary="Explainable risk assessment for one entity")
async def risk_detail(entity_id: str):
    row = db.query_one("SELECT entity_id, name FROM entities WHERE entity_id = ?", (entity_id,))
    if row is None:
        raise HTTPException(404, f"Entity {entity_id} not found")
    engine.ensure()
    scorer = RiskScorer(graph_metrics=engine.centrality(person_only=True))
    return scorer.score_entity(entity_id, row["name"])


@ml_router.get("/patterns", summary="Detected suspicious patterns")
async def patterns(
    pattern_type: str | None = None,
    severity: str | None = None,
    recompute: bool = False,
    limit: int = Query(100, le=500),
):
    if recompute:
        return run_all_detectors(persist=True)

    sql = "SELECT * FROM patterns WHERE 1=1"
    params: list[Any] = []
    if pattern_type:
        sql += " AND pattern_type = ?"
        params.append(pattern_type)
    if severity:
        sql += " AND severity = ?"
        params.append(severity)
    sql += " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 " \
           "WHEN 'medium' THEN 2 ELSE 3 END, confidence DESC LIMIT ?"
    params.append(limit)

    names = {r["entity_id"]: r["name"] for r in db.query("SELECT entity_id, name FROM entities")}
    out = []
    for row in db.query(sql, params):
        item = dict(row)
        members = db.jload(item["members"], [])
        item["members"] = members
        item["member_names"] = [names.get(m, m) for m in members]
        item["detail"] = db.jload(item["detail"], {})
        out.append(item)
    return {"total": len(out), "patterns": out}


@ml_router.get("/evaluation", summary="Ground-truth evaluation of kingpin detection")
async def model_evaluation():
    engine.ensure()
    return evaluation.evaluate()


# ===========================================================================
search_router = APIRouter()


@search_router.get("", summary="Global search across entities, cases and patterns")
async def do_search(
    q: str = Query(..., min_length=1),
    ref_type: str | None = Query(None, pattern="^(entity|case|pattern)$"),
    limit: int = Query(25, ge=1, le=100),
    user: dict = Depends(security.current_user),
):
    log(user.get("username", "anonymous"), "SEARCH", q)
    return search_engine.search(q, ref_type=ref_type, limit=limit)


@search_router.get("/suggest", summary="Type-ahead suggestions")
async def suggest(q: str = Query(..., min_length=2), limit: int = Query(10, le=25)):
    return {"suggestions": search_engine.suggest(q, limit=limit)}


# ===========================================================================
alerts_router = APIRouter()


@alerts_router.get("", summary="Prioritised alert worklist")
async def list_alerts(severity: str | None = None, limit: int = Query(100, le=500)):
    items = alert_rules.list_alerts(severity=severity, limit=limit)
    return {
        "total": len(items),
        "by_severity": {r["severity"]: r["c"] for r in db.query(
            "SELECT severity, COUNT(*) AS c FROM alerts GROUP BY severity")},
        "alerts": items,
    }


@alerts_router.post("/regenerate", summary="Recompute alerts from current analytics")
async def regenerate(user: dict = Depends(security.require_role("analyst"))):
    result = alert_rules.generate_alerts()
    log(user.get("username", "anonymous"), "ALERTS_REGENERATED", "alerts", **result)
    return result


# ===========================================================================
audit_router = APIRouter()


@audit_router.get("/chain", summary="Audit ledger entries")
async def audit_entries(limit: int = Query(50, le=500), actor: str | None = None,
                        action: str | None = None):
    return {"entries": chain.entries(limit=limit, actor=actor, action=action)}


@audit_router.get("/verify", summary="Verify ledger integrity end to end")
async def audit_verify():
    return chain.verify()


@audit_router.get("/stats", summary="Ledger statistics")
async def audit_stats():
    return chain.stats()


@audit_router.get("/proof/{idx}", summary="Merkle inclusion proof for one audit entry")
async def audit_proof(idx: int):
    result = chain.inclusion_proof(idx)
    if not result.get("found"):
        raise HTTPException(404, f"No audit block at height {idx}")
    return result


@audit_router.post("/tamper-demo", summary="Demonstrate tamper detection (admin only)")
async def tamper_demo(
    payload: dict = Body(default={}, examples=[{"idx": 1, "new_action": "MODIFIED"}]),
    user: dict = Depends(security.require_role("admin")),
):
    """
    Deliberately mutates one audit block so that `verify` reports exactly where
    the chain broke. Restores the original content afterwards, so the ledger is
    left intact. This exists to make the integrity guarantee demonstrable rather
    than asserted.
    """
    idx = int(payload.get("idx", 1))
    row = db.query_one("SELECT * FROM audit_chain WHERE idx = ?", (idx,))
    if row is None:
        raise HTTPException(404, f"No audit block at height {idx}")

    original_action = row["action"]
    before = chain.verify()
    db.execute("UPDATE audit_chain SET action = ? WHERE idx = ?",
               (payload.get("new_action", "TAMPERED_ENTRY"), idx))
    during = chain.verify()
    db.execute("UPDATE audit_chain SET action = ? WHERE idx = ?", (original_action, idx))
    after = chain.verify()

    return {
        "demonstration": "Audit block content was modified, verified, then restored.",
        "before_tampering": before,
        "after_tampering": during,
        "after_restoration": after,
        "conclusion": (
            f"Modifying block {idx} was detected immediately at height "
            f"{during.get('failed_at')} because the recorded SHA-256 digest no "
            f"longer reproduces from the block contents. Restoring the original "
            f"value returns the chain to a valid state, proving detection is exact "
            f"rather than probabilistic."
        ),
    }


# ===========================================================================
women_router = APIRouter()


@women_router.get("/dashboard", summary="Women Safety Division dashboard")
async def ws_dashboard():
    return women_safety.dashboard()


@women_router.get("/overview", summary="Cases within the Women Safety mandate")
async def ws_overview():
    return women_safety.overview()


@women_router.get("/repeat-offenders", summary="Repeat and cross-jurisdictional offenders")
async def ws_repeat(min_cases: int = Query(2, ge=2, le=10)):
    items = women_safety.repeat_offenders(min_cases=min_cases)
    return {"total": len(items), "offenders": items}


@women_router.get("/escalation-watchlist", summary="Offence-escalation risk assessment")
async def ws_escalation():
    items = women_safety.escalation_risk()
    return {
        "total": len(items),
        "high_risk": len([i for i in items if i["escalation_band"] == "high_escalation_risk"]),
        "watchlist": items,
        "rationale": (
            "Offences are placed on an escalation ladder from insulting modesty "
            "through stalking and assault to grave offences. Multiple precursor "
            "offences without a grave offence yet is the window where preventive "
            "action changes the outcome."
        ),
    }


@women_router.get("/trafficking-corridors", summary="Inferred trafficking corridors")
async def ws_corridors(min_shared: int = Query(2, ge=1, le=10)):
    items = women_safety.trafficking_corridors(min_shared=min_shared)
    return {"total": len(items), "corridors": items}


@women_router.get("/hotspots", summary="District-level hotspot index")
async def ws_hotspots():
    items = women_safety.hotspots()
    return {"total": len(items), "hotspots": items}


# ===========================================================================
dashboard_router = APIRouter()


@dashboard_router.get("/summary", summary="Single-call dashboard payload")
async def dashboard_summary():
    engine.ensure()
    if not engine._communities:
        engine.communities()

    kingpins = engine.kingpin_ranking(top_n=6)
    top_risk = []
    for row in db.query(
        "SELECT entity_id, name, risk_score, kingpin_score FROM entities "
        "WHERE type='Person' ORDER BY risk_score DESC LIMIT 8"
    ):
        item = dict(row)
        item["risk_band"] = risk_band(item["risk_score"] or 0)
        top_risk.append(item)

    crime_distribution = {r["crime_type"]: r["c"] for r in db.query(
        "SELECT crime_type, COUNT(*) AS c FROM cases GROUP BY crime_type ORDER BY c DESC")}
    state_distribution = {r["state"]: r["c"] for r in db.query(
        "SELECT state, COUNT(*) AS c FROM cases GROUP BY state ORDER BY c DESC")}
    timeline = [dict(r) for r in db.query(
        "SELECT substr(date_filed,1,7) AS month, COUNT(*) AS cases "
        "FROM cases WHERE date_filed <> '' GROUP BY month ORDER BY month")]

    money = db.query_one(
        "SELECT COUNT(*) AS c, COALESCE(SUM(amount),0) AS total, "
        "COALESCE(SUM(CASE WHEN flagged=1 THEN amount ELSE 0 END),0) AS flagged "
        "FROM transactions")

    return {
        "system": {
            "organisation": "National Crime Records Bureau (NCRB)",
            "department": "Women Safety Division",
            "ministry": "Ministry of Home Affairs, Government of India",
        },
        "counts": {
            "cases": db.scalar("SELECT COUNT(*) FROM cases"),
            "entities": db.scalar("SELECT COUNT(*) FROM entities"),
            "persons": db.scalar("SELECT COUNT(*) FROM entities WHERE type='Person'"),
            "relationships": db.scalar("SELECT COUNT(*) FROM relationships"),
            "cdr_records": db.scalar("SELECT COUNT(*) FROM cdr"),
            "transactions": money["c"],
            "networks_detected": db.scalar("SELECT COUNT(DISTINCT community_id) FROM communities"),
            "patterns": db.scalar("SELECT COUNT(*) FROM patterns"),
            "alerts": db.scalar("SELECT COUNT(*) FROM alerts"),
            "audit_blocks": db.scalar("SELECT COUNT(*) FROM audit_chain"),
        },
        "financial": {
            "total_traced_inr": float(money["total"] or 0),
            "flagged_inr": float(money["flagged"] or 0),
            "flagged_share_pct": round(float(money["flagged"] or 0) /
                                       float(money["total"] or 1) * 100, 2),
        },
        "graph": {
            "nodes": engine.G.number_of_nodes(),
            "edges": engine.G.number_of_edges(),
            "person_nodes": len([n for n, d in engine.G.nodes(data=True)
                                 if d.get("type") == "Person"]),
        },
        "top_kingpins": kingpins,
        "top_risk": top_risk,
        "alerts": alert_rules.list_alerts(limit=8),
        "pattern_summary": {r["pattern_type"]: r["c"] for r in db.query(
            "SELECT pattern_type, COUNT(*) AS c FROM patterns GROUP BY pattern_type "
            "ORDER BY c DESC")},
        "severity_summary": {r["severity"]: r["c"] for r in db.query(
            "SELECT severity, COUNT(*) AS c FROM patterns GROUP BY severity")},
        "crime_distribution": crime_distribution,
        "state_distribution": state_distribution,
        "timeline": timeline,
        "women_safety": women_safety.overview(),
        "audit": chain.verify(),
    }


@dashboard_router.get("/geo", summary="Geographic intelligence points")
async def geo():
    towers = [dict(r) for r in db.query(
        "SELECT tower_id, tower_name, lat, lon, COUNT(*) AS activity "
        "FROM cdr WHERE lat IS NOT NULL GROUP BY tower_id "
        "ORDER BY activity DESC LIMIT 300")]
    cases = [dict(r) for r in db.query(
        "SELECT state, district, COUNT(*) AS cases, "
        "SUM(CASE WHEN priority IN ('Critical','High') THEN 1 ELSE 0 END) AS high_priority "
        "FROM cases GROUP BY state, district ORDER BY cases DESC")]
    return {"towers": towers, "case_density": cases,
            "hotspots": women_safety.hotspots()[:10]}
