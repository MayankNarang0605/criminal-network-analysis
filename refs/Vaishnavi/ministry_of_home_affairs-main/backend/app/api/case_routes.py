"""
Case Intake & Management API Endpoints
"""

import json
from datetime import datetime, timezone
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.database.connection import SessionLocal
from backend.app.database.models import CaseRecord
from backend.app.graph.engine import graph_engine
from backend.app.nlp.entity_extractor import EntityExtractor
from backend.app.nlp.crime_classifier import CrimeClassifier
from backend.app.security.audit import AuditLogger
from backend.app.security.auth import decode_access_token
from backend.app.synthetic.generator import SyntheticDataGenerator

extractor = EntityExtractor()
classifier = CrimeClassifier()

def get_current_user_info(request: Request) -> tuple:
    """Extract user info from request Authorization header or fallback to default."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = decode_access_token(auth_header.split(" ")[1])
        if payload:
            return payload.get("username", "anonymous_officer"), payload.get("role", "Investigating Officer"), int(payload.get("sub", 0))
    return "anonymous_officer", "Investigating Officer", 0

async def preview_entities_endpoint(request: Request) -> JSONResponse:
    """
    Real-Time NLP preview endpoint for the Case Intake Workbench.
    Extracts entities and classifies crime category on keystroke / paste.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    text = body.get("narrative_text", "").strip()
    if not text:
        return JSONResponse({"entities": {}, "classification": {}})

    extracted = extractor.extract(text)
    classification = classifier.classify(text)

    return JSONResponse({
        "extracted_entities": extracted,
        "classification": classification,
        "summary": {
            "total_persons": len(extracted["persons"]),
            "total_phones": len(extracted["phones"]),
            "total_vehicles": len(extracted["vehicles"]),
            "total_accounts": len(extracted["financial_accounts"]),
            "total_locations": len(extracted["locations"]),
            "total_orgs": len(extracted["organizations"])
        }
    })

async def intake_case_endpoint(request: Request) -> JSONResponse:
    """
    Full Case Intake:
    1. Validates and stores structured FIR record in SQL DB.
    2. Runs NLP extraction to resolve entities.
    3. Ingests Case, Suspects, Assets, and Relationships into the Graph.
    4. Logs tamper-evident audit record.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    fir_number = body.get("fir_number", "").strip()
    station = body.get("station", "").strip()
    state = body.get("state", "Delhi").strip()
    jurisdiction_code = body.get("jurisdiction_code", "DL-POLICE-SPL").strip()
    crime_category = body.get("crime_category", "").strip()
    investigating_officer = body.get("investigating_officer", "").strip()
    narrative_text = body.get("narrative_text", "").strip()
    filed_date = body.get("filed_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    if not fir_number or not station or not narrative_text:
        return JSONResponse({"error": "FIR Number, Police Station, and Narrative text are required."}, status_code=400)

    # 1. NLP Processing
    extracted = extractor.extract(narrative_text)
    if not crime_category:
        classification = classifier.classify(narrative_text)
        crime_category = classification["predicted_category"]

    case_id = f"CASE_{fir_number.replace('/', '_').replace(' ', '_').upper()}_{len(graph_engine.nodes_data) + 1}"

    db = SessionLocal()
    try:
        # Check duplicate FIR
        existing_case = db.query(CaseRecord).filter(CaseRecord.fir_number == fir_number).first()
        if existing_case:
            return JSONResponse({"error": f"FIR Number '{fir_number}' is already registered in the system."}, status_code=409)

        # 2. Store in Relational DB
        new_case = CaseRecord(
            case_id=case_id,
            fir_number=fir_number,
            station=station,
            jurisdiction_code=jurisdiction_code,
            state=state,
            crime_category=crime_category,
            filed_date=filed_date,
            investigating_officer=investigating_officer or "Insp. In-Charge",
            narrative_text=narrative_text,
            extracted_entities_json=json.dumps(extracted)
        )
        db.add(new_case)
        db.commit()
        db.refresh(new_case)

        # 3. Ingest into Graph Engine
        # Add Case Node
        graph_engine.add_node(case_id, "Case", f"FIR No. {fir_number} ({station})", {
            "case_id": case_id,
            "fir_number": fir_number,
            "station": station,
            "jurisdiction_code": jurisdiction_code,
            "state": state,
            "crime_category": crime_category,
            "filed_date": filed_date,
            "investigating_officer": investigating_officer,
            "narrative_text": narrative_text
        })

        # Add Extracted Person Nodes & Edges
        created_node_ids = [case_id]
        for p in extracted["persons"]:
            p_name = p["name"]
            # Check if matching phone or name already exists
            p_id = f"P_{p_name.replace(' ', '_').upper()}_{len(graph_engine.nodes_data) + 1}"
            p_node = graph_engine.add_node(p_id, "Person", p_name, {
                "aliases": p.get("aliases", []),
                "gender": "Unknown",
                "status": "Accused / Named in FIR"
            })
            graph_engine.add_edge(p_id, case_id, "ACCUSED_IN", {"role": "Accused", "weight": 2.5})
            created_node_ids.append(p_id)

        # Add Phone Nodes & Edges
        for phone in extracted["phones"]:
            phone_id = f"TEL_{phone['normalized']}"
            graph_engine.add_node(phone_id, "CommunicationRecord", f"Phone {phone['masked']}", {
                "phone": phone["normalized"],
                "phone_hash": phone["phone_hash"],
                "type": "Cellular SIM"
            })
            graph_engine.add_edge(phone_id, case_id, "ACCUSED_IN", {"weight": 1.5})
            created_node_ids.append(phone_id)

        # Add Vehicle Nodes & Edges
        for veh in extracted["vehicles"]:
            veh_id = f"VEH_{veh['registration_number'].replace(' ', '_')}"
            graph_engine.add_node(veh_id, "Vehicle", f"Vehicle ({veh['registration_number']})", {
                "registration_number": veh["registration_number"],
                "vehicle_hash": veh["vehicle_hash"]
            })
            graph_engine.add_edge(veh_id, case_id, "ACCUSED_IN", {"weight": 1.5})
            created_node_ids.append(veh_id)

        # Add Financial Accounts
        for acc in extracted["financial_accounts"]:
            acc_id = f"ACC_{acc['account_hash'][:10]}"
            graph_engine.add_node(acc_id, "FinancialAccount", f"{acc['type']} ({acc['masked']})", {
                "account_type": acc["type"],
                "account_hash": acc["account_hash"],
                "masked": acc["masked"]
            })
            graph_engine.add_edge(acc_id, case_id, "ACCUSED_IN", {"weight": 1.5})
            created_node_ids.append(acc_id)

        # Add Organizations
        for org in extracted["organizations"]:
            org_id = f"ORG_{org['name'].replace(' ', '_').upper()}"
            graph_engine.add_node(org_id, "Organization", org["name"], {
                "type": org.get("type", "Syndicate Module")
            })
            graph_engine.add_edge(org_id, case_id, "ACCUSED_IN", {"weight": 2.0})
            created_node_ids.append(org_id)

        # Persist graph updates
        graph_engine.save_to_disk()

        # 4. Audit Log Action
        username, role, uid = get_current_user_info(request)
        AuditLogger.log_action(
            db=db,
            username=username,
            user_role=role,
            action="CASE_INTAKE",
            entity_type="Case",
            entity_id=case_id,
            details={
                "fir_number": fir_number,
                "station": station,
                "crime_category": crime_category,
                "extracted_entities_count": len(created_node_ids)
            },
            user_id=uid
        )

        return JSONResponse({
            "success": True,
            "message": f"Successfully registered FIR No. '{fir_number}' and ingested {len(created_node_ids)} nodes into the Criminal Graph.",
            "case": new_case.to_dict(),
            "graph_summary": {
                "created_node_ids": created_node_ids,
                "total_nodes": len(graph_engine.nodes_data),
                "total_edges": len(graph_engine.edges_data)
            }
        }, status_code=201)
    finally:
        db.close()

async def list_cases_endpoint(request: Request) -> JSONResponse:
    """Returns list of registered case records with query filtering."""
    q = request.query_params.get("q", "").strip().lower()
    category = request.query_params.get("category", "")
    jurisdiction = request.query_params.get("jurisdiction", "")

    db = SessionLocal()
    try:
        cases_query = db.query(CaseRecord).order_by(CaseRecord.created_at.desc())
        if category:
            cases_query = cases_query.filter(CaseRecord.crime_category == category)
        if jurisdiction:
            cases_query = cases_query.filter(CaseRecord.jurisdiction_code == jurisdiction)

        all_cases = cases_query.all()
        results = []
        for c in all_cases:
            if not q or (q in c.fir_number.lower() or q in c.station.lower() or q in c.narrative_text.lower() or q in c.investigating_officer.lower()):
                results.append(c.to_dict())

        return JSONResponse({
            "total": len(results),
            "cases": results
        })
    finally:
        db.close()

async def get_case_detail_endpoint(request: Request) -> JSONResponse:
    """Returns full details of a specific case, including 1-hop connected graph entities."""
    case_id = request.path_params.get("case_id")
    db = SessionLocal()
    try:
        case = db.query(CaseRecord).filter(
            (CaseRecord.case_id == case_id) | (CaseRecord.fir_number == case_id)
        ).first()

        if not case:
            return JSONResponse({"error": "Case not found"}, status_code=404)

        # Get connected graph entities
        connected_entities = graph_engine.get_neighbors(case.case_id, direction="both")

        # Audit log view
        username, role, uid = get_current_user_info(request)
        AuditLogger.log_action(
            db=db,
            username=username,
            user_role=role,
            action="VIEW_CASE_DOSSIER",
            entity_type="Case",
            entity_id=case.case_id,
            details={"fir_number": case.fir_number, "station": case.station},
            user_id=uid
        )

        return JSONResponse({
            "case": case.to_dict(),
            "connected_entities": connected_entities
        })
    finally:
        db.close()

async def seed_synthetic_data_endpoint(request: Request) -> JSONResponse:
    """Re-initializes the synthetic crime networks across all 3 syndicates."""
    generator = SyntheticDataGenerator(graph_engine)
    result = generator.generate_all_scenarios(reset_first=True)

    db = SessionLocal()
    try:
        username, role, uid = get_current_user_info(request)
        AuditLogger.log_action(
            db=db,
            username=username,
            user_role=role,
            action="RESET_SYNTHETIC_DATASET",
            entity_type="System",
            entity_id="GLOBAL_GRAPH",
            details=result,
            user_id=uid
        )
    finally:
        db.close()

    return JSONResponse(result)
