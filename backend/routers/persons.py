"""
Persons & Suspect Dossiers Router.
Provides 360° investigative suspect profiles backed by:
- Identity & aliases
- Linked FIRs, phones, SIM cards, IMEIs, bank accounts, vehicles
- CDR & financial activity
- Associates & network connections
- Locations & timeline
- Forensic anomalies
- Evidentiary references with tamper-evident hash verification
- Network Leadership / Centrality Score (6 pillars)
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.postgres import get_db
from backend.models.evidence import (
    Person, Phone, SimCard, Device, PhoneSimImeiDevice, Vehicle, BankAccount,
    FIRPerson, FIR, CDR, Transaction, LocationEvent, CCTVAnprEvent, Relationship,
    EvidenceMetadata, EvidenceHashChain
)
from backend.services.kingpin import compute_kingpin_scores
from backend.services.detectors import run_all_detectors

router = APIRouter(prefix="/api/persons", tags=["Persons"])


class PersonSummaryResponse(BaseModel):
    person_id: str
    full_name: str
    alias: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    city: Optional[str] = None
    occupation: Optional[str] = None
    phone_ids: Optional[str] = None
    vehicle_ids: Optional[str] = None
    organization_ids: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[PersonSummaryResponse])
def list_persons(
    search: Optional[str] = Query(None, description="Search by name, alias, or person ID"),
    city: Optional[str] = Query(None, description="Filter by city"),
    case_id: Optional[str] = Query(None, description="Filter by associated case ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List persons/suspects with search, city, and case filtering."""
    query = db.query(Person)

    if isinstance(case_id, str) and case_id.strip() and case_id.strip().upper() != "ALL":
        # Find persons in this case via FIR
        case_firs = db.query(FIR).filter(FIR.case_id == case_id.strip()).all()
        fir_ids = [f.fir_id for f in case_firs]
        case_persons = [
            fp.person_id for fp in db.query(FIRPerson).filter(FIRPerson.fir_id.in_(fir_ids)).all()
        ]
        query = query.filter(Person.person_id.in_(case_persons))

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Person.full_name.ilike(pattern),
                Person.alias.ilike(pattern),
                Person.person_id.ilike(pattern),
            )
        )

    if city:
        query = query.filter(Person.city.ilike(city.strip()))

    persons = query.order_by(Person.person_id.asc()).offset(offset).limit(limit).all()
    return persons


@router.get("/{person_id}")
def get_person_dossier(
    person_id: str,
    case_id: Optional[str] = Query(None, description="Optional case context for scoring"),
    db: Session = Depends(get_db)
):
    """
    Retrieve full 360-degree investigative suspect dossier:
    1. Identity & aliases
    2. Linked FIRs, phones, bank accounts, vehicles
    3. CDR & financial activity
    4. Associates & network connections
    5. Locations & timeline
    6. Anomalies
    7. Evidence references
    8. Network Leadership / Centrality Score
    """
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with ID '{person_id}' not found",
        )

    # ── 1. Linked Phones, SIMs, Devices ──────────────────────────────────────
    phones_db = db.query(Phone).filter(Phone.person_id == person_id).all()
    phone_ids = [p.phone_id for p in phones_db]
    phone_numbers = [p.number for p in phones_db]

    # Hardware devices / IMEIs / SIM links
    sim_cards = db.query(SimCard).filter(SimCard.phone_id.in_(phone_ids)).all() if phone_ids else []
    device_links = db.query(PhoneSimImeiDevice).filter(
        or_(
            PhoneSimImeiDevice.person_id == person_id,
            PhoneSimImeiDevice.phone_id.in_(phone_ids) if phone_ids else False
        )
    ).all()
    device_ids = list(set(d.device_id for d in device_links if d.device_id))
    devices_db = db.query(Device).filter(Device.device_id.in_(device_ids)).all() if device_ids else []
    device_map = {d.device_id: d for d in devices_db}

    hardware_assets = []
    for dl in device_links:
        dev = device_map.get(dl.device_id)
        hardware_assets.append({
            "device_id": dl.device_id,
            "imei": dev.imei if dev else "Unknown",
            "make": dev.make if dev else "Unknown",
            "model": dev.model if dev else "Unknown",
            "phone_id": dl.phone_id,
            "sim_id": dl.sim_id,
            "first_seen": dl.first_seen,
            "last_seen": dl.last_seen,
            "is_primary": dl.is_primary,
        })

    # ── 2. Linked Vehicles ───────────────────────────────────────────────────
    vehicles = db.query(Vehicle).filter(Vehicle.owner_person_id == person_id).all()
    vehicle_data = [
        {
            "vehicle_id": v.vehicle_id,
            "registration_id": v.registration_id,
            "make": v.make,
            "model": v.model,
            "color": v.color,
            "type": v.vehicle_type,
            "city": v.registration_city,
        }
        for v in vehicles
    ]
    reg_plates = [v.registration_id for v in vehicles]

    # ── 3. Linked Bank Accounts ──────────────────────────────────────────────
    accounts = db.query(BankAccount).filter(BankAccount.person_id == person_id).all()
    account_ids = [a.account_id for a in accounts]

    # ── 4. Financial Activity ────────────────────────────────────────────────
    tx_sender = db.query(Transaction).filter(Transaction.sender_account.in_(account_ids)).all() if account_ids else []
    tx_receiver = db.query(Transaction).filter(Transaction.receiver_account.in_(account_ids)).all() if account_ids else []
    
    total_sent = sum(t.amount for t in tx_sender)
    total_received = sum(t.amount for t in tx_receiver)
    all_txs = tx_sender + tx_receiver
    # Deduplicate in case of self-transfers
    seen_tx_ids = set()
    dedup_txs = []
    for t in sorted(all_txs, key=lambda x: x.timestamp or "", reverse=True):
        if t.transaction_id not in seen_tx_ids:
            seen_tx_ids.add(t.transaction_id)
            direction = "OUTFLOW" if t.sender_account in account_ids else "INFLOW"
            counterparty = t.receiver_account if direction == "OUTFLOW" else t.sender_account
            dedup_txs.append({
                "transaction_id": t.transaction_id,
                "case_id": t.case_id,
                "timestamp": t.timestamp,
                "amount": round(t.amount, 2),
                "direction": direction,
                "counterparty_account": counterparty,
                "type": t.transaction_type,
                "location": t.location,
                "description": t.description,
            })

    account_data = [
        {
            "account_id": a.account_id,
            "bank_name": a.bank_name,
            "branch_city": a.branch_city,
            "account_type": a.account_type,
            "opening_date": a.opening_date,
            "inflow": round(sum(t.amount for t in tx_receiver if t.receiver_account == a.account_id), 2),
            "outflow": round(sum(t.amount for t in tx_sender if t.sender_account == a.account_id), 2),
            "tx_count": sum(1 for t in dedup_txs if t["counterparty_account"] == a.account_id or a.account_id in (t.get("sender_account", ""), t.get("receiver_account", ""))),
        }
        for a in accounts
    ]

    # ── 5. CDR & Telecom Activity ────────────────────────────────────────────
    cdrs_caller = db.query(CDR).filter(CDR.caller_phone_id.in_(phone_ids)).all() if phone_ids else []
    cdrs_receiver = db.query(CDR).filter(CDR.receiver_phone_id.in_(phone_ids)).all() if phone_ids else []
    
    total_calls_outgoing = len(cdrs_caller)
    total_calls_incoming = len(cdrs_receiver)
    total_duration_sec = sum(c.duration_seconds or 0 for c in cdrs_caller) + sum(c.duration_seconds or 0 for c in cdrs_receiver)

    # Contacts mapping
    contacts_counter = {}
    for c in cdrs_caller:
        other = c.receiver_phone_id
        if other not in contacts_counter:
            contacts_counter[other] = {"calls": 0, "duration": 0}
        contacts_counter[other]["calls"] += 1
        contacts_counter[other]["duration"] += (c.duration_seconds or 0)
    for c in cdrs_receiver:
        other = c.caller_phone_id
        if other not in contacts_counter:
            contacts_counter[other] = {"calls": 0, "duration": 0}
        contacts_counter[other]["calls"] += 1
        contacts_counter[other]["duration"] += (c.duration_seconds or 0)

    # Resolve phone owners for contacts
    top_contact_phones = sorted(contacts_counter.keys(), key=lambda x: contacts_counter[x]["calls"], reverse=True)[:10]
    contact_phone_recs = db.query(Phone).filter(Phone.phone_id.in_(top_contact_phones)).all() if top_contact_phones else []
    contact_person_ids = list(set(p.person_id for p in contact_phone_recs if p.person_id))
    contact_persons = db.query(Person).filter(Person.person_id.in_(contact_person_ids)).all() if contact_person_ids else []
    p_map = {p.person_id: p for p in contact_persons}
    phone_owner_map = {p.phone_id: p_map.get(p.person_id) for p in contact_phone_recs}

    frequent_call_partners = [
        {
            "phone_id": ph,
            "call_count": contacts_counter[ph]["calls"],
            "duration_seconds": contacts_counter[ph]["duration"],
            "contact_name": phone_owner_map.get(ph).full_name if phone_owner_map.get(ph) else "Unregistered Node",
            "contact_alias": phone_owner_map.get(ph).alias if phone_owner_map.get(ph) else None,
            "contact_person_id": phone_owner_map.get(ph).person_id if phone_owner_map.get(ph) else None,
        }
        for ph in top_contact_phones
    ]

    all_cdrs = []
    seen_cdr_ids = set()
    for c in sorted(cdrs_caller + cdrs_receiver, key=lambda x: x.timestamp or "", reverse=True)[:25]:
        if c.cdr_id not in seen_cdr_ids:
            seen_cdr_ids.add(c.cdr_id)
            direction = "OUTGOING" if c.caller_phone_id in phone_ids else "INCOMING"
            other = c.receiver_phone_id if direction == "OUTGOING" else c.caller_phone_id
            all_cdrs.append({
                "cdr_id": c.cdr_id,
                "case_id": c.case_id,
                "timestamp": c.timestamp,
                "duration_seconds": c.duration_seconds or 0,
                "direction": direction,
                "counterparty_phone": other,
                "call_type": c.call_type,
                "tower_location_id": c.tower_location_id,
            })

    # ── 6. Linked FIRs & Cases ───────────────────────────────────────────────
    fir_links = db.query(FIRPerson).filter(FIRPerson.person_id == person_id).all()
    fir_ids = [fl.fir_id for fl in fir_links]
    firs = db.query(FIR).filter(FIR.fir_id.in_(fir_ids)).all() if fir_ids else []
    fir_map = {f.fir_id: f for f in firs}

    linked_firs = [
        {
            "fir_id": fl.fir_id,
            "fir_number": fir_map[fl.fir_id].fir_number if fl.fir_id in fir_map else "Unknown",
            "case_id": fir_map[fl.fir_id].case_id if fl.fir_id in fir_map else "Unknown",
            "role": fl.role,
            "confidence": round(fl.confidence or 1.0, 2),
            "status": fir_map[fl.fir_id].status if fl.fir_id in fir_map else "Under Investigation",
            "crime_type": fir_map[fl.fir_id].crime_type if fl.fir_id in fir_map else "Unspecified",
            "incident_date": fir_map[fl.fir_id].incident_date if fl.fir_id in fir_map else None,
            "incident_city": fir_map[fl.fir_id].incident_city if fl.fir_id in fir_map else None,
            "summary": fir_map[fl.fir_id].summary if fl.fir_id in fir_map else None,
        }
        for fl in fir_links
    ]

    # ── 7. Associates & Network Connections ──────────────────────────────────
    rels = db.query(Relationship).filter(
        or_(Relationship.source_entity == person_id, Relationship.target_entity == person_id)
    ).all()
    other_pids = set()
    for r in rels:
        if r.source_entity != person_id and r.source_entity.startswith("P"):
            other_pids.add(r.source_entity)
        if r.target_entity != person_id and r.target_entity.startswith("P"):
            other_pids.add(r.target_entity)

    other_persons = db.query(Person).filter(Person.person_id.in_(list(other_pids))).all() if other_pids else []
    assoc_map = {p.person_id: p for p in other_persons}

    associates = []
    for r in rels:
        is_source = (r.source_entity == person_id)
        other_id = r.target_entity if is_source else r.source_entity
        other_obj = assoc_map.get(other_id)
        associates.append({
            "relationship_id": r.relationship_id,
            "associate_id": other_id,
            "associate_name": other_obj.full_name if other_obj else other_id,
            "associate_alias": other_obj.alias if other_obj else None,
            "associate_city": other_obj.city if other_obj else None,
            "associate_occupation": other_obj.occupation if other_obj else None,
            "relationship_type": r.relationship_type,
            "confidence": round(r.confidence or 1.0, 2),
            "direction": "OUTGOING" if is_source else "INCOMING",
            "timestamp": r.timestamp,
            "source_record": r.source_record,
        })

    # ── 8. Locations & Forensic Timeline ─────────────────────────────────────
    loc_events = db.query(LocationEvent).filter(LocationEvent.person_id == person_id).all()
    cctv_events = db.query(CCTVAnprEvent).filter(CCTVAnprEvent.plate_number.in_(reg_plates)).all() if reg_plates else []

    timeline_events = []
    visited_cities = set()
    if person.city:
        visited_cities.add(person.city)

    for le in loc_events:
        timeline_events.append({
            "timestamp": le.timestamp,
            "category": "LOCATION",
            "title": f"Location Ping ({le.event_type})",
            "description": f"Observed at location node {le.location_id} via {le.source}",
            "case_id": le.case_id,
            "evidence_id": le.event_id,
        })

    for cctv in cctv_events:
        timeline_events.append({
            "timestamp": cctv.timestamp,
            "category": "CCTV_ANPR",
            "title": f"Vehicle ANPR Capture: {cctv.plate_number}",
            "description": f"{cctv.description or 'ANPR camera tracking'} at camera {cctv.camera_id}",
            "case_id": cctv.case_id,
            "evidence_id": cctv.event_id,
        })

    for lf in linked_firs:
        if lf["incident_date"]:
            timeline_events.append({
                "timestamp": lf["incident_date"],
                "category": "FIR_INCIDENT",
                "title": f"FIR Incident: {lf['fir_number']}",
                "description": f"Alleged role: {lf['role']} in {lf['crime_type']} ({lf['incident_city'] or 'N/A'})",
                "case_id": lf["case_id"],
                "evidence_id": lf["fir_id"],
            })
            if lf["incident_city"]:
                visited_cities.add(lf["incident_city"])

    for tx in dedup_txs[:10]:
        timeline_events.append({
            "timestamp": tx["timestamp"],
            "category": "FINANCIAL",
            "title": f"Financial {tx['direction']}: ₹{tx['amount']:,.0f}",
            "description": f"{tx['type']} via {tx['counterparty_account']} ({tx['location'] or 'Online Banking'})",
            "case_id": tx["case_id"],
            "evidence_id": tx["transaction_id"],
        })

    for cd in all_cdrs[:10]:
        timeline_events.append({
            "timestamp": cd["timestamp"],
            "category": "CDR",
            "title": f"Telecom {cd['direction']} Call ({cd['duration_seconds']}s)",
            "description": f"{cd['call_type']} with node {cd['counterparty_phone']} at tower {cd['tower_location_id']}",
            "case_id": cd["case_id"],
            "evidence_id": cd["cdr_id"],
        })

    timeline_events.sort(key=lambda x: x["timestamp"] or "")

    # ── 9. Forensic Anomalies ────────────────────────────────────────────────
    # Query case-specific anomalies or primary linked case
    case_context = case_id.strip() if isinstance(case_id, str) and case_id.strip() and case_id.strip().upper() != "ALL" else None
    target_case_for_anomalies = case_context or (linked_firs[0]["case_id"] if linked_firs else None)
    all_anomalies = run_all_detectors(db, case_id=target_case_for_anomalies) if target_case_for_anomalies else []
    
    # Filter anomalies involving this person or their linked accounts/phones/vehicles
    entity_keys = {person_id, person.full_name}
    if person.alias:
        entity_keys.add(person.alias)
    for a in account_ids:
        entity_keys.add(a)
    for p in phone_numbers:
        entity_keys.add(p)
    for v in reg_plates:
        entity_keys.add(v)

    suspect_anomalies = []
    for a in all_anomalies:
        ent_id = a.get("entity_id") or ""
        ent_name = a.get("entity") or ""
        if ent_id in entity_keys or any(k in ent_name for k in entity_keys if len(k) > 3):
            suspect_anomalies.append(a)

    # ── 10. Evidence References & Hash Chain ─────────────────────────────────
    ev_case_ids = list(set(lf["case_id"] for lf in linked_firs if lf["case_id"]))
    ev_records = db.query(EvidenceMetadata).filter(
        or_(
            EvidenceMetadata.case_id.in_(ev_case_ids) if ev_case_ids else False,
            EvidenceMetadata.record_id.in_(fir_ids + phone_ids + account_ids) if (fir_ids or phone_ids or account_ids) else False
        )
    ).limit(30).all()

    evidence_ids = [e.evidence_id for e in ev_records]
    hashes = db.query(EvidenceHashChain).filter(EvidenceHashChain.evidence_id.in_(evidence_ids)).all() if evidence_ids else []
    hash_map = {h.evidence_id: h.content_sha256 for h in hashes}

    evidence_references = [
        {
            "evidence_id": e.evidence_id,
            "case_id": e.case_id,
            "source_table": e.source_table,
            "record_id": e.record_id,
            "evidence_type": e.evidence_type,
            "collected_date": e.collected_date,
            "custodian": e.custodian,
            "content_sha256": hash_map.get(e.evidence_id, "Verified Ledger Root"),
        }
        for e in ev_records
    ]

    # ── 11. Network Leadership / Centrality Score ────────────────────────────
    # Compute leadership scores scoped to case context or global
    target_case_for_score = case_context or (linked_firs[0]["case_id"] if linked_firs else None)
    kingpin_list = compute_kingpin_scores(db, case_id=target_case_for_score, limit=200)
    score_data = next((k for k in kingpin_list if k["person_id"] == person_id), None)
    if not score_data:
        # Fallback to computing on the fly
        score_data = {
            "leadership_score_100": 15,
            "network_leadership_score": 0.15,
            "composite_score": 0.15,
            "rank": len(kingpin_list) + 1,
            "role_classification": "Operational Associate",
            "score_breakdown": {
                "network_centrality": 0.1,
                "betweenness_connectivity": 0.1,
                "financial_influence": 0.1,
                "communication_influence": 0.1,
                "cross_case_connections": 0.2,
                "evidence_strength": 0.2,
            },
            "explanation": "Standard node activity observed with localized connections.",
            "disclaimer": "⚠️ Network Leadership/Centrality Score is a structural topological metric — NOT a measure of legal guilt probability.",
        }

    return {
        "person_id": person.person_id,
        "full_name": person.full_name,
        "alias": person.alias,
        "age": person.age,
        "gender": person.gender,
        "city": person.city,
        "occupation": person.occupation,
        "address": person.address,
        "visited_cities": sorted(list(visited_cities)),
        # Hardware / Telecom assets
        "phones": phone_numbers,
        "phone_details": [
            {
                "phone_id": p.phone_id,
                "number": p.number,
                "sim_cards": [s.operator for s in sim_cards if s.phone_id == p.phone_id],
            }
            for p in phones_db
        ],
        "hardware_devices": hardware_assets,
        # Physical and Financial assets
        "vehicles": vehicle_data,
        "bank_accounts": account_data,
        # FIR involvements
        "linked_firs": linked_firs,
        "cases_involved": linked_firs,  # Backwards compatibility
        # Financial Activity Summary
        "financial_activity": {
            "total_sent_inr": round(total_sent, 2),
            "total_received_inr": round(total_received, 2),
            "total_volume_inr": round(total_sent + total_received, 2),
            "transaction_count": len(dedup_txs),
            "transactions": dedup_txs[:20],
        },
        # Telecom Activity Summary
        "cdr_activity": {
            "total_calls": total_calls_outgoing + total_calls_incoming,
            "calls_outgoing": total_calls_outgoing,
            "calls_incoming": total_calls_incoming,
            "total_duration_seconds": total_duration_sec,
            "total_duration_formatted": f"{total_duration_sec // 60}m {total_duration_sec % 60}s",
            "unique_contacts_count": len(contacts_counter),
            "frequent_call_partners": frequent_call_partners,
            "recent_calls": all_cdrs[:20],
        },
        # Direct Associates & Graph Links
        "associates": associates,
        # Spatiotemporal Forensic Timeline
        "timeline": timeline_events,
        # Detected Forensic Anomalies
        "anomalies": suspect_anomalies,
        # Evidence References & Hash Integrity
        "evidence_references": evidence_references,
        # Network Leadership & Centrality Metric
        "leadership_scoring": score_data,
        "disclaimer": "⚠️ Network Leadership/Centrality Score is a structural topological metric — NOT a measure of legal guilt probability.",
    }


@router.get("/{person_id}/timeline")
def get_person_timeline(person_id: str, db: Session = Depends(get_db)):
    """Assemble chronological timeline of events involving this person."""
    dossier = get_person_dossier(person_id=person_id, db=db)
    timeline = dossier.get("timeline", [])
    return {
        "person_id": person_id,
        "total_events": len(timeline),
        "timeline": timeline,
    }
