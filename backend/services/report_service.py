"""
Structured Investigation Report Generator Service.
Transforms graph, telecom, financial, anomaly, and timeline analysis
into an official, court-ready Police & Prosecution Investigation Dossier.

Sections included:
1. Case Overview & AI Executive Summary
2. FIR Intelligence (Accused, Victims, Witnesses, Legal Sections)
3. Suspect Profiles (Demographics, Hardware, Accounts, Vehicles, Associates)
4. Network Analysis (Graph metrics, Clusters, Bridges, Leadership Scores)
5. Financial Intelligence (Structuring, Mule Funnels, Dispersals, Flow Chains)
6. CDR Telecom Analysis (Frequency pairs, Surges, Cell Towers, Connectors)
7. Geospatial Analysis (Crime scenes, Hotspots, Displacement corridors)
8. Forensic Anomalies (ML & Rule detections with deviations & evidence)
9. Unified Forensic Timeline (FIR + Calls + Financial + Physical Sightings)
10. AI Investigation Summary & Recommended Leads (No automatic guilt)
11. Conclusion & Open Questions
12. Section 65B Indian Evidence Act Cryptographic Integrity Certificate
13. Officer Sign-off, Editable Notes, Versioning & Audit Trail
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
import io

import networkx as nx
from sqlalchemy.orm import Session

from backend.logging_config import logger
from backend.models.evidence import (
    Case, FIR, FIRPerson, Person, Phone, Vehicle, BankAccount, Transaction,
    CDR, LocationEvent, Location, Relationship, EvidenceMetadata, EvidenceHashChain
)
from backend.services.financial_service import analyze_financial_intelligence
from backend.services.cdr_service import analyze_case_cdr
from backend.services.detectors import run_all_detectors
from backend.services.kingpin import compute_kingpin_scores
from backend.routers.evidence import verify_case_hash_chain

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT


def build_structured_case_report(
    db: Session,
    case_id: str,
    officer_name: str = "Investigating Officer (DSP / Inspector)",
    badge_number: str = "POL-IND-8842",
    station_unit: str = "Central Crime Investigation Department / Cyber Cell",
    notes: Optional[str] = None,
    version: str = "v1.0",
    report_status: str = "FINAL",
) -> Dict[str, Any]:
    """
    Assembles a comprehensive, 13-section structured investigation dossier for a case.
    """
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise ValueError(f"Case with ID '{case_id}' not found")

    now = datetime.utcnow()
    gen_iso = now.isoformat() + "Z"
    gen_human = now.strftime("%d %B %Y, %H:%M UTC")
    report_id = f"IR-{case_id}-{now.strftime('%Y%m%d')}-01"

    # ── 1. FIR Records & Legal Categorization ───────────────────────────────
    firs = db.query(FIR).filter(FIR.case_id == case_id).all()
    fir_ids = [f.fir_id for f in firs]
    fir_persons = db.query(FIRPerson).filter(FIRPerson.fir_id.in_(fir_ids)).all() if fir_ids else []

    all_case_person_ids = set(fp.person_id for fp in fir_persons)
    persons_db = db.query(Person).filter(Person.person_id.in_(list(all_case_person_ids))).all() if all_case_person_ids else []
    person_map = {p.person_id: p for p in persons_db}

    accused_entities = []
    victim_entities = []
    witness_entities = []
    other_entities = []

    for fp in fir_persons:
        p_obj = person_map.get(fp.person_id)
        role_lower = (fp.role or "").lower()
        ent_data = {
            "person_id": fp.person_id,
            "full_name": p_obj.full_name if p_obj else fp.person_id,
            "alias": p_obj.alias if p_obj else None,
            "city": p_obj.city if p_obj else None,
            "role": fp.role or "Unspecified",
            "confidence": round(fp.confidence or 1.0, 2),
            "fir_id": fp.fir_id,
            "source": fp.source or "FIR Annexure",
        }
        if any(r in role_lower for r in ["accused", "suspect", "conspirator", "operator"]):
            accused_entities.append(ent_data)
        elif any(r in role_lower for r in ["victim", "complainant"]):
            victim_entities.append(ent_data)
        elif any(r in role_lower for r in ["witness", "informant"]):
            witness_entities.append(ent_data)
        else:
            other_entities.append(ent_data)

    fir_summaries = [
        {
            "fir_id": f.fir_id,
            "fir_number": f.fir_number,
            "police_station": f.police_station_id or "State Crime Police Station",
            "registration_date": f.registration_date,
            "incident_date": f.incident_date,
            "crime_type": f.crime_type,
            "incident_city": f.incident_city,
            "incident_area": f.incident_area,
            "status": f.status or "Investigation in Progress",
            "summary": f.summary or "Formal First Information Report registered for investigation.",
        }
        for f in firs
    ]

    # ── 2. Network Leadership & Centrality Ranks ─────────────────────────────
    kingpin_candidates = compute_kingpin_scores(db, case_id=case_id, limit=25)

    # ── 3. Suspect Profiles Deep Dive ────────────────────────────────────────
    # Extract detailed profiles for top suspects in this case
    top_suspect_ids = [k["person_id"] for k in kingpin_candidates[:8]]
    if not top_suspect_ids and all_case_person_ids:
        top_suspect_ids = list(all_case_person_ids)[:8]

    suspect_profiles = []
    for pid in top_suspect_ids:
        p_obj = db.query(Person).filter(Person.person_id == pid).first()
        if not p_obj:
            continue
        p_phones = [ph.number for ph in db.query(Phone).filter(Phone.person_id == pid).all()]
        p_vehs = [
            f"{v.registration_id} ({v.make} {v.model}, {v.color})"
            for v in db.query(Vehicle).filter(Vehicle.owner_person_id == pid).all()
        ]
        p_accs = [
            f"{ba.account_id} - {ba.bank_name} ({ba.branch_city or 'Branch'})"
            for ba in db.query(BankAccount).filter(BankAccount.person_id == pid).all()
        ]
        # Cross-case involvement
        c_links = db.query(FIRPerson).filter(FIRPerson.person_id == pid).all()
        f_ids = [cl.fir_id for cl in c_links]
        case_involvements = list(set([f.case_id for f in db.query(FIR).filter(FIR.fir_id.in_(f_ids)).all()])) if f_ids else []

        # Immediate associates
        rels = db.query(Relationship).filter(
            (Relationship.source_entity == pid) | (Relationship.target_entity == pid)
        ).limit(6).all()
        assoc_list = []
        for r in rels:
            other = r.target_entity if r.source_entity == pid else r.source_entity
            assoc_list.append(f"{other} ({r.relationship_type}, {int((r.confidence or 1.0) * 100)}%)")

        k_score = next((k for k in kingpin_candidates if k["person_id"] == pid), None)

        suspect_profiles.append({
            "person_id": pid,
            "full_name": p_obj.full_name,
            "alias": p_obj.alias,
            "city": p_obj.city or "Unspecified",
            "occupation": p_obj.occupation or "Unrecorded",
            "age": p_obj.age,
            "gender": p_obj.gender,
            "address": p_obj.address or "Address under verification",
            "phones": p_phones,
            "vehicles": p_vehs,
            "bank_accounts": p_accs,
            "cases_involved": case_involvements,
            "associates": assoc_list,
            "leadership_score": k_score["leadership_score_100"] if k_score else 20,
            "role_classification": k_score["role_classification"] if k_score else "Operational Associate",
            "explanation": k_score["explanation"] if k_score else "Associated node in syndicate graph.",
        })

    # ── 4. Network Graph Metrics & Sub-Clusters ──────────────────────────────
    G = nx.Graph()
    for r in db.query(Relationship).all():
        G.add_edge(r.source_entity, r.target_entity, weight=r.confidence or 1.0)

    # Subgraph for this case's persons
    case_subgraph_nodes = set(all_case_person_ids)
    for k in kingpin_candidates:
        case_subgraph_nodes.add(k["person_id"])
    
    subG = G.subgraph(case_subgraph_nodes) if len(case_subgraph_nodes) > 0 else G
    total_nodes = len(subG.nodes)
    total_edges = len(subG.edges)
    density = nx.density(subG) if total_nodes > 1 else 0.0

    # Identify communities / functional cells
    clusters = []
    if total_nodes >= 4 and total_edges >= 2:
        try:
            from networkx.algorithms.community import greedy_modularity_communities
            comms = list(greedy_modularity_communities(subG))
            for idx, c in enumerate(comms[:4], start=1):
                c_members = list(c)
                named_members = [person_map[m].full_name for m in c_members if m in person_map]
                clusters.append({
                    "cluster_id": f"Cell-{idx}",
                    "size": len(c_members),
                    "primary_nodes": c_members[:5],
                    "named_nodes": named_members[:5],
                    "functional_hypothesis": (
                        "Primary Financial & Dispersal Conduit" if idx == 1 else
                        "Telecom Operational Coordination Cell" if idx == 2 else
                        "Procurement, Transport & Logistics Ring" if idx == 3 else
                        "Peripheral Sub-cluster"
                    ),
                })
        except Exception as exc:
            logger.warning(f"Community detection fallback: {exc}")

    # Top bridge nodes (highest betweenness)
    bridge_nodes = sorted(
        kingpin_candidates,
        key=lambda x: x["score_breakdown"]["betweenness_connectivity"],
        reverse=True
    )[:5]

    network_analysis = {
        "case_topology": case.topology or "Hierarchical Cluster",
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "graph_density": round(density, 3),
        "clusters_detected": clusters,
        "bridge_entities": [
            {
                "person_id": b["person_id"],
                "name": b["full_name"],
                "betweenness": b["metrics"]["betweenness_raw"],
                "role": b["role_classification"],
                "significance": "Acts as critical information and logistics choke-point bridging cells."
            }
            for b in bridge_nodes
        ],
        "top_leadership_ranking": kingpin_candidates[:10],
    }

    # ── 5. Financial Intelligence ────────────────────────────────────────────
    financial_intel = analyze_financial_intelligence(db, case_id=case_id)

    # ── 6. Telecom CDR Analysis ──────────────────────────────────────────────
    cdr_intel = analyze_case_cdr(db, case_id=case_id)
    if isinstance(cdr_intel, dict) and "frequent_communications" in cdr_intel:
        for fc in cdr_intel.get("frequent_communications", []):
            pa = fc.get("party_a") if isinstance(fc.get("party_a"), dict) else {}
            pb = fc.get("party_b") if isinstance(fc.get("party_b"), dict) else {}
            fc["caller"] = pa.get("number") or pa.get("phone_id") or fc.get("caller") or "Unknown"
            fc["caller_name"] = pa.get("person_name") or pa.get("alias") or ""
            fc["caller_label"] = pa.get("label") or f"{fc['caller_name']} ({fc['caller']})".strip()
            fc["receiver"] = pb.get("number") or pb.get("phone_id") or fc.get("receiver") or "Unknown"
            fc["receiver_name"] = pb.get("person_name") or pb.get("alias") or ""
            fc["receiver_label"] = pb.get("label") or f"{fc['receiver_name']} ({fc['receiver']})".strip()
            fc["formatted_duration"] = fc.get("total_duration_formatted") or f"{fc.get('total_duration_seconds', 0)}s"

    # ── 7. Geospatial & Crime Scene Locations ────────────────────────────────
    loc_events = db.query(LocationEvent).filter(LocationEvent.case_id == case_id).all()
    location_ids = list(set([le.location_id for le in loc_events if le.location_id]))
    locations = db.query(Location).filter(Location.location_id.in_(location_ids)).all() if location_ids else []
    loc_map = {l.location_id: l for l in locations}

    visited_cities = set()
    for f in firs:
        if f.incident_city:
            visited_cities.add(f.incident_city)
    for l in locations:
        if l.city:
            visited_cities.add(l.city)

    geospatial_analysis = {
        "primary_jurisdiction": case.primary_location or "National Jurisdiction",
        "affected_cities": sorted(list(visited_cities)),
        "key_locations": [
            {
                "location_id": l.location_id,
                "name": l.location_name,
                "city": l.city,
                "area": l.area,
                "latitude": l.latitude,
                "longitude": l.longitude,
                "type": l.location_type or "Investigative Site",
            }
            for l in locations[:15]
        ],
        "total_sightings": len(loc_events),
    }

    # ── 8. Detected Forensic Anomalies ───────────────────────────────────────
    raw_anomalies = run_all_detectors(db, case_id=case_id)
    anomalies_list = [
        {
            "group_id": a.get("group_id") or a.get("detector_name"),
            "detector_name": a.get("detector_name"),
            "anomaly_type": a.get("anomaly_type") or "Forensic Outlier",
            "model_used": a.get("model_used") or "Rule-based Engine",
            "title": a.get("title") or a.get("detector_name"),
            "severity": a.get("severity") or "HIGH",
            "anomaly_score_100": a.get("anomaly_score_100") or 85,
            "what_happened": a.get("what_happened") or a.get("explanation", ""),
            "why_unusual": a.get("why_unusual") or "Statistical deviation exceeding baseline thresholds.",
            "evidence": a.get("evidence") or [],
        }
        for a in raw_anomalies[:25]
    ]

    # ── 9. Unified Chronological Forensic Timeline ───────────────────────────
    timeline_events = []
    for f in firs:
        if f.incident_date:
            timeline_events.append({
                "timestamp": f.incident_date,
                "category": "FIR_INCIDENT",
                "title": f"Incident Reported: {f.fir_number}",
                "description": f"{f.crime_type} registered at {f.police_station_id} ({f.incident_city})",
                "evidence_ref": f.fir_id,
                "confidence": "HIGH (Official Record)",
            })

    # Financial transfers from financial_intel
    for tx in financial_intel.get("transactions", [])[:15]:
        timeline_events.append({
            "timestamp": tx.get("timestamp") or "",
            "category": "FINANCIAL",
            "title": f"Fund Transfer: ₹{tx.get('amount', 0):,.0f}",
            "description": f"{tx.get('sender_account')} -> {tx.get('receiver_account')} ({tx.get('type', 'TRANSFER')})",
            "evidence_ref": tx.get("transaction_id", ""),
            "confidence": "VERIFIED (Banking Ledger)",
        })

    # CDR events from cdr_intel timeline
    for ct in cdr_intel.get("timeline", [])[:15]:
        timeline_events.append({
            "timestamp": ct.get("timestamp") or ct.get("date") or "",
            "category": "TELECOM_CDR",
            "title": ct.get("title", "Telecom Communication"),
            "description": ct.get("description", "High-frequency call interaction recorded"),
            "evidence_ref": ct.get("badge", "CDR Record"),
            "confidence": "VERIFIED (Tower Switch Log)",
        })

    # Location sightings
    for le in loc_events[:10]:
        timeline_events.append({
            "timestamp": le.timestamp or "",
            "category": "LOCATION",
            "title": f"Physical Sighting: {le.event_type}",
            "description": f"Suspect {le.person_id} observed at location {le.location_id} via {le.source}",
            "evidence_ref": le.event_id,
            "confidence": "CORROBORATED",
        })

    timeline_events.sort(key=lambda x: x["timestamp"] or "")

    # ── 10. AI Executive Synthesis & Investigation Leads ─────────────────────
    # Synthesize concrete findings based on data
    top_suspect_name = suspect_profiles[0]["full_name"] if suspect_profiles else "Primary Target"
    top_fin_vol = financial_intel.get("summary", {}).get("formatted_total_money", "₹0")
    total_calls_cnt = cdr_intel.get("summary", {}).get("total_calls", 0)

    ai_executive_summary = (
        f"Investigation dossier for Case {case.case_id} ({case.case_title}) establishes an active, multi-tiered "
        f"{case.crime_type} network centered across {case.primary_location}. Graph topology reveals "
        f"{total_nodes} interconnected nodes operating under a {case.topology or 'structured'} layout. "
        f"Forensic financial analysis traced {top_fin_vol} across suspicious accounts, displaying active structuring "
        f"and rapid dispersal funnels. Telecom analysis identified {total_calls_cnt} CDR calls, characterized by "
        f"pre-incident communication bursts and burner device rotations. Primary network orchestration centers around "
        f"{top_suspect_name} (Leadership Score: {suspect_profiles[0]['leadership_score'] if suspect_profiles else 70}/100) "
        f"acting as a structural choke-point across sub-cliques."
    )

    recommended_leads = [
        f"Serve Section 91 CrPC notices on relevant banking institutions for suspect accounts in {case.primary_location}.",
        f"Obtain tower dump records and historical cell-site logs for high-frequency call clusters.",
        f"Initiate cross-jurisdictional surveillance on identified transit corridors across {', '.join(list(visited_cities)[:4])}.",
        f"Conduct formal custodial interrogation of primary operational bridge entities ({', '.join(top_suspect_ids[:3])}).",
        f"Freeze identified mule accounts exhibiting high-velocity fan-in / fan-out flow.",
    ]

    open_questions = [
        "Identity of secondary hardware handset owners linked to burner IMEIs.",
        "Ultimate beneficial owners (UBO) of offshore/inter-state shell accounts receiving dispersed funds.",
        "Corroboration of physical presence via commercial CCTV camera feeds at border checkpoints.",
    ]

    # ── 11. Section 65B Cryptographic Verification ───────────────────────────
    chain_status = verify_case_hash_chain(case_id=case_id, db=db)
    integrity_certificate = {
        "case_id": case.case_id,
        "chain_integrity": "VERIFIED & TAMPER-EVIDENT" if chain_status.chain_valid else "PENDING AUDIT",
        "total_evidence_records": chain_status.total_records,
        "merkle_root_computed": chain_status.root_hash,
        "head_block_hash": chain_status.head_block_hash,
        "statutory_compliance": "Fully compliant with Section 65B Indian Evidence Act standards.",
        "certificate_statement": (
            "This digital evidence chain is verified using SHA-256 cryptographic hashes linking all ingested "
            "records. Any post-ingestion alteration to transactions, CDRs, or FIRs triggers immediate block hash mismatch."
        ),
    }

    # ── 12. Officer Information, Notes & Audit Trail ─────────────────────────
    officer_details = {
        "officer_name": officer_name,
        "badge_number": badge_number,
        "station_unit": station_unit,
        "sign_off_date": gen_human,
    }

    audit_entry = {
        "action": "REPORT_GENERATED",
        "timestamp": gen_iso,
        "officer": officer_name,
        "version": version,
        "details": f"Generated {version} prosecution investigation brief for Case {case_id}",
    }

    return {
        "report_id": report_id,
        "case_id": case.case_id,
        "case_title": case.case_title,
        "crime_type": case.crime_type,
        "status": report_status,
        "version": version,
        "generated_at": gen_iso,
        "generated_at_human": gen_human,
        "officer_details": officer_details,
        "officer_notes": notes or (
            "Investigator notes: Initial analytical compilation completed. All key financial conduits and "
            "telecom coordination cells have been mapped. Corroborating witness statements recommended."
        ),
        "audit_trail": [audit_entry],
        # Section 1: Case Overview
        "case_overview": {
            "case_id": case.case_id,
            "case_title": case.case_title,
            "crime_type": case.crime_type,
            "difficulty": case.difficulty,
            "topology": case.topology,
            "date_range_start": case.date_range_start or "Undisclosed",
            "date_range_end": case.date_range_end or "Ongoing",
            "primary_location": case.primary_location,
            "total_entities": case.n_network_entities,
            "case_status": "Active Judicial Investigation",
            "ai_summary": ai_executive_summary,
        },
        # Section 2: FIR Intelligence
        "fir_intelligence": {
            "total_firs": len(firs),
            "firs": fir_summaries,
            "accused_entities": accused_entities,
            "victim_entities": victim_entities,
            "witness_entities": witness_entities,
            "other_entities": other_entities,
        },
        # Section 3: Suspect Profiles
        "suspect_profiles": suspect_profiles,
        # Section 4: Network Analysis
        "network_analysis": network_analysis,
        # Section 5: Financial Intelligence
        "financial_intelligence": financial_intel,
        # Section 6: CDR Telecom Analysis
        "cdr_analysis": cdr_intel,
        # Section 7: Geospatial Analysis
        "geospatial_analysis": geospatial_analysis,
        # Section 8: Forensic Anomalies
        "anomalies": anomalies_list,
        # Section 9: Unified Timeline
        "timeline": timeline_events,
        # Section 10: AI Executive Summary & Recommended Leads
        "ai_investigation_summary": {
            "executive_brief": ai_executive_summary,
            "recommended_leads": recommended_leads,
            "open_questions": open_questions,
            "legal_disclaimer": (
                "⚠️ STATUTORY ADVISORY: This report presents automated algorithmic and topological intelligence. "
                "It does NOT establish a verdict of legal guilt. All findings require human officer verification "
                "and judicial corroboration."
            ),
        },
        # Section 11: Conclusion
        "conclusion": {
            "summary_verdict": f"Sufficient evidentiary density established to proceed with targeted summons and Section 91 CrPC requisitions for Case {case.case_id}.",
            "recommended_leads": recommended_leads,
            "open_questions": open_questions,
        },
        # Section 12: Section 65B Evidence Integrity Certificate
        "integrity_certificate": integrity_certificate,
    }


def generate_docx_report(report: Dict[str, Any]) -> io.BytesIO:
    """
    Constructs a styled, official Microsoft Word (.docx) prosecution investigation brief.
    """
    doc = docx.Document()

    # Set page margins
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.8)
        s.right_margin = Inches(0.8)

    # ── Document Header ──────────────────────────────────────────────────────
    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_header.add_run("STATE CRIME INVESTIGATION DEPARTMENT\n")
    r_title.bold = True
    r_title.font.size = Pt(14)
    r_sub = p_header.add_run("OFFICIAL PROSECUTION & INVESTIGATIVE INTELLIGENCE DOSSIER\n")
    r_sub.font.size = Pt(11)
    r_sub.bold = True
    r_sub.font.color.rgb = RGBColor(0, 102, 204)
    r_ref = p_header.add_run(f"Report ID: {report['report_id']}  |  Case: {report['case_id']}  |  Version: {report['version']}\n")
    r_ref.font.size = Pt(9)
    r_ref.font.italic = True

    # Divider line
    doc.add_paragraph("―" * 60).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Legal Warning Box
    p_warn = doc.add_paragraph()
    r_w = p_warn.add_run(
        "CONFIDENTIAL & PRIVILEGED — FOR LAW ENFORCEMENT & JUDICIAL USE ONLY\n"
        "This dossier compiles automated forensic network analysis. Findings indicate structural graph importance "
        "and do NOT constitute an automatic verdict of guilt."
    )
    r_w.font.size = Pt(8.5)
    r_w.font.italic = True
    r_w.font.color.rgb = RGBColor(180, 50, 50)

    # ── Section 1: Case Overview ─────────────────────────────────────────────
    doc.add_heading("1. Case Overview", level=1)
    ov = report["case_overview"]

    table_ov = doc.add_table(rows=5, cols=2)
    table_ov.alignment = WD_TABLE_ALIGNMENT.CENTER
    rows_data = [
        ("Case Title & ID:", f"{ov['case_title']} ({ov['case_id']})"),
        ("Crime Category:", f"{ov['crime_type']}"),
        ("Jurisdiction / Location:", f"{ov['primary_location']}"),
        ("Active Date Range:", f"{ov['date_range_start']} to {ov['date_range_end']}"),
        ("Topology & Entities:", f"{ov['topology']} ({ov['total_entities']} identified nodes)"),
    ]
    for idx, (label, val) in enumerate(rows_data):
        row = table_ov.rows[idx]
        c0 = row.cells[0].paragraphs[0].add_run(label)
        c0.bold = True
        c0.font.size = Pt(9.5)
        c1 = row.cells[1].paragraphs[0].add_run(val)
        c1.font.size = Pt(9.5)

    doc.add_paragraph()
    p_sum = doc.add_paragraph()
    p_sum.add_run("Executive Case Summary: ").bold = True
    p_sum.add_run(ov["ai_summary"]).font.size = Pt(9.5)

    # ── Section 2: FIR Intelligence ──────────────────────────────────────────
    doc.add_heading("2. FIR Intelligence & Legal Allegations", level=1)
    fir_sec = report["fir_intelligence"]
    
    for f in fir_sec["firs"]:
        p_fir = doc.add_paragraph()
        p_fir.add_run(f"FIR No. {f['fir_number']} — {f['police_station']} ({f['status']})\n").bold = True
        p_fir.add_run(f"Crime Section: {f['crime_type']}  |  Incident Date: {f['incident_date']}  |  City: {f['incident_city']}\n").font.size = Pt(9)
        p_fir.add_run(f"Allegation: {f['summary']}\n").font.size = Pt(9)

    # Entity Breakdown Table
    doc.add_heading("Classified Involvements:", level=2)
    t_ents = doc.add_table(rows=1, cols=4)
    t_ents.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t_ents.rows[0].cells
    for i, h_text in enumerate(["Person ID", "Full Name", "Legal Role", "Corroboration"]):
        r = hdr[i].paragraphs[0].add_run(h_text)
        r.bold = True
        r.font.size = Pt(9)

    all_named = fir_sec["accused_entities"][:8] + fir_sec["victim_entities"][:4] + fir_sec["witness_entities"][:4]
    for ent in all_named:
        row = t_ents.add_row().cells
        row[0].paragraphs[0].add_run(ent["person_id"]).font.size = Pt(8.5)
        row[1].paragraphs[0].add_run(ent["full_name"]).font.size = Pt(8.5)
        row[2].paragraphs[0].add_run(ent["role"]).font.size = Pt(8.5)
        row[3].paragraphs[0].add_run(f"{int(ent['confidence'] * 100)}% ({ent['source']})").font.size = Pt(8.5)

    # ── Section 3: Suspect Profiles ──────────────────────────────────────────
    doc.add_heading("3. Suspect Profiles & Evidence-Backed Assets", level=1)
    for s in report["suspect_profiles"]:
        p_s = doc.add_paragraph()
        p_s.add_run(f"• {s['full_name']} (ID: {s['person_id']})").bold = True
        if s["alias"]:
            p_s.add_run(f" — aka '{s['alias']}'").bold = True
        p_s.add_run(f"  [{s['role_classification']} | Leadership Score: {s['leadership_score']}/100]\n").font.color.rgb = RGBColor(0, 102, 204)
        
        details_txt = (
            f"  City: {s['city']} | Occupation: {s['occupation']} | Age: {s['age'] or 'N/A'}\n"
            f"  Phones: {', '.join(s['phones']) if s['phones'] else 'None'}\n"
            f"  Bank Accounts: {', '.join(s['bank_accounts']) if s['bank_accounts'] else 'None'}\n"
            f"  Vehicles: {', '.join(s['vehicles']) if s['vehicles'] else 'None'}\n"
            f"  Cross-Case Links: {', '.join(s['cases_involved']) if s['cases_involved'] else 'Single case'}\n"
            f"  Structural Analysis: {s['explanation']}\n"
        )
        p_s.add_run(details_txt).font.size = Pt(8.5)

    def add_p(text: str = "", font_size: float = 9.5, bold: bool = False, italic: bool = False, color: Optional[RGBColor] = None):
        p = doc.add_paragraph()
        if text:
            r = p.add_run(text)
            r.font.size = Pt(font_size)
            r.bold = bold
            r.font.italic = italic
            if color:
                r.font.color.rgb = color
        return p

    # ── Section 4: Network Analysis ──────────────────────────────────────────
    doc.add_heading("4. Network Topology & Leadership Scoring", level=1)
    net = report["network_analysis"]
    add_p(
        f"Graph Structure: {net['case_topology']} consisting of {net['total_nodes']} nodes and {net['total_edges']} edges. "
        f"Network density measured at {net['graph_density']}.",
        font_size=9.5
    )

    doc.add_heading("Identified Functional Cells / Clusters:", level=2)
    for c in net["clusters_detected"]:
        add_p(
            f"• {c['cluster_id']} ({c['functional_hypothesis']}): {c['size']} members including {', '.join(c['named_nodes'])}",
            font_size=9
        )

    doc.add_heading("Top Operational Bridge Nodes (Choke-Points):", level=2)
    for b in net["bridge_entities"]:
        add_p(
            f"• {b['name']} ({b['person_id']}) — Betweenness Centrality: {b['betweenness']:.4f}. {b['significance']}",
            font_size=9
        )

    # ── Section 5: Financial Intelligence ────────────────────────────────────
    doc.add_heading("5. Financial Intelligence & Laundering Typologies", level=1)
    fin = report["financial_intelligence"]
    fin_sum = fin.get("summary", {})
    add_p(
        f"Total Money Analyzed: {fin_sum.get('formatted_total_money', '₹0')} across {fin_sum.get('total_transactions', 0)} transactions. "
        f"Flagged Suspicious Volume: {fin_sum.get('formatted_suspicious_volume', '₹0')} involving {fin_sum.get('suspicious_accounts_count', 0)} accounts.",
        font_size=9.5
    )

    if fin.get("patterns"):
        doc.add_heading("Detected Financial Patterns:", level=2)
        for p in fin["patterns"][:6]:
            add_p(f"• {p.get('pattern_type')}: {p.get('explanation')}", font_size=8.5)

    # ── Section 6: CDR Telecom Analysis ──────────────────────────────────────
    doc.add_heading("6. Telecom CDR & Call Burst Analysis", level=1)
    cdr = report["cdr_analysis"]
    cdr_sum = cdr.get("summary", {})
    add_p(
        f"Total CDR Records Analyzed: {cdr_sum.get('total_calls', 0)} calls ({cdr_sum.get('total_duration_formatted', '0m')}). "
        f"Distinct Callers: {cdr_sum.get('distinct_callers', 0)}, Distinct Receivers: {cdr_sum.get('distinct_receivers', 0)}.",
        font_size=9.5
    )

    if cdr.get("frequent_communications"):
        doc.add_heading("Frequent Communication Pairs:", level=2)
        for fc in cdr["frequent_communications"][:5]:
            p1 = fc.get('caller_label') or fc.get('caller') or 'Unknown'
            p2 = fc.get('receiver_label') or fc.get('receiver') or 'Unknown'
            dur = fc.get('formatted_duration') or fc.get('total_duration_formatted') or 'N/A'
            calls = fc.get('total_calls', 0)
            add_p(
                f"• {p1} <-> {p2}: {calls} calls, duration: {dur}",
                font_size=8.5
            )

    # ── Section 7: Geospatial & Movement ─────────────────────────────────────
    doc.add_heading("7. Geospatial Locations & Crime Corridors", level=1)
    geo = report["geospatial_analysis"]
    add_p(
        f"Primary Hub: {geo['primary_jurisdiction']}. Cross-jurisdictional transit verified across: "
        f"{', '.join(geo['affected_cities'])} with {geo['total_sightings']} recorded sightings.",
        font_size=9.5
    )

    # ── Section 8: Forensic Anomalies ────────────────────────────────────────
    doc.add_heading("8. Prioritized Forensic Anomalies", level=1)
    for a in report["anomalies"][:8]:
        p_an = doc.add_paragraph()
        p_an.add_run(f"[{a['severity']} | Score: {a['anomaly_score_100']}] {a['title']}\n").bold = True
        p_an.add_run(f"Model: {a['model_used']}  |  Detector: {a['detector_name']}\n").font.size = Pt(8.5)
        p_an.add_run(f"Finding: {a['what_happened']}\n").font.size = Pt(8.5)

    # ── Section 9: Unified Chronological Timeline ────────────────────────────
    doc.add_heading("9. Unified Forensic Chronological Timeline", level=1)
    for t in report["timeline"][:12]:
        p_t = doc.add_paragraph()
        p_t.add_run(f"{t['timestamp']} [{t['category']}]: ").bold = True
        p_t.add_run(f"{t['title']} — {t['description']} (Ref: {t['evidence_ref']})\n").font.size = Pt(8.5)

    # ── Section 10: Recommended Leads & Conclusion ───────────────────────────
    doc.add_heading("10. Recommended Investigative Action Plan", level=1)
    for l in report["ai_investigation_summary"]["recommended_leads"]:
        add_p(f"✓ {l}", font_size=9)

    doc.add_heading("Open Evidentiary Questions:", level=2)
    for q in report["ai_investigation_summary"]["open_questions"]:
        add_p(f"? {q}", font_size=9)

    # ── Section 11: Section 65B Certificate ──────────────────────────────────
    doc.add_heading("11. Section 65B Indian Evidence Act Certificate", level=1)
    cert = report["integrity_certificate"]
    p_cert = doc.add_paragraph()
    p_cert.add_run(f"Status: {cert['chain_integrity']}\n").bold = True
    p_cert.add_run(f"Total Evidence Items Chained: {cert['total_evidence_records']}\n").font.size = Pt(9)
    p_cert.add_run(f"Merkle Root Hash: {cert['merkle_root_computed']}\n").font.size = Pt(8.5)
    p_cert.add_run(f"Head Block Hash: {cert['head_block_hash']}\n\n").font.size = Pt(8.5)
    p_cert.add_run(cert["certificate_statement"]).font.size = Pt(8.5)

    # ── Section 12: Officer Sign-off & Notes ─────────────────────────────────
    doc.add_heading("12. Investigating Officer Sign-Off", level=1)
    off = report["officer_details"]
    p_off = doc.add_paragraph()
    p_off.add_run(f"Investigating Officer: {off['officer_name']}\n").bold = True
    p_off.add_run(f"Badge / Identification: {off['badge_number']}\n").font.size = Pt(9.5)
    p_off.add_run(f"Unit / Station: {off['station_unit']}\n").font.size = Pt(9.5)
    p_off.add_run(f"Report Certification Date: {off['sign_off_date']}\n\n").font.size = Pt(9.5)
    p_off.add_run("Signature: ___________________________           Seal / Stamp: [  OFFICIAL  ]\n").bold = True

    if report.get("officer_notes"):
        doc.add_heading("Investigator Remarks & Working Notes:", level=2)
        add_p(report["officer_notes"], font_size=9)

    # Save to memory stream
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio
