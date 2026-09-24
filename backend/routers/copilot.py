"""
Investigative AI Copilot Router (Phase 17).
Adheres strictly to BUILD-SPEC Rule 5 and Rule 6:
- LLM is an explainer, never the source of truth.
- Dual-engine: Gemini API when configured + 100% deterministic offline fallback.
- Strictly grounds every response in real case_ids, transaction_ids, and CDR records.
"""
from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.logging_config import logger
from backend.postgres import get_db
from backend.models.evidence import Case, Person, FIR, Transaction, CDR
from backend.services.detectors import run_all_detectors
from backend.services.kingpin import compute_kingpin_scores

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])


class CopilotQueryRequest(BaseModel):
    query: str
    case_id: Optional[str] = None
    context_mode: Optional[str] = "comprehensive"


class EvidenceCitation(BaseModel):
    source_type: str
    identifier: str
    summary: str


class CopilotQueryResponse(BaseModel):
    query: str
    answer: str
    engine_used: str  # "gemini-pro" or "deterministic_fallback"
    citations: List[EvidenceCitation]
    recommended_leads: List[str]


def generate_deterministic_answer(query: str, case_id: Optional[str], db: Session) -> Tuple[str, List[EvidenceCitation], List[str]]:
    q_lower = query.lower()
    citations = []
    leads = []

    # 1. Target specific case if mentioned or passed
    target_case = None
    if case_id:
        target_case = db.query(Case).filter(Case.case_id == case_id).first()
    else:
        # Check if CASEXXX is in query string
        import re
        case_match = re.search(r"case\d{3}", q_lower)
        if case_match:
            cid = case_match.group(0).upper()
            target_case = db.query(Case).filter(Case.case_id == cid).first()

    if target_case:
        cid = target_case.case_id
        firs = db.query(FIR).filter(FIR.case_id == cid).all()
        anomalies = run_all_detectors(db, case_id=cid)
        kingpins = compute_kingpin_scores(db, case_id=cid, limit=3)

        citations.append(EvidenceCitation(
            source_type="cases.csv",
            identifier=cid,
            summary=f"Title: {target_case.case_title} | Crime: {target_case.crime_type} | Location: {target_case.primary_location}",
        ))

        for f in firs[:2]:
            citations.append(EvidenceCitation(
                source_type="fir.csv",
                identifier=f.fir_id,
                summary=f"FIR #{f.fir_number} registered at {f.police_station_id} on {f.registration_date}",
            ))

        for a in anomalies[:2]:
            citations.append(EvidenceCitation(
                source_type="forensic_detector",
                identifier=a["detector_name"],
                summary=a["explanation"],
            ))

        leads_text = "\n".join([f"- Candidate: {k['full_name']} (Composite Leadership Score: {k['kingpin_score']})" for k in kingpins])
        leads = [k["full_name"] for k in kingpins]

        answer = (
            f"### Investigative Brief: {target_case.case_title} ({cid})\n\n"
            f"**Classification:** {target_case.crime_type} ({target_case.difficulty} difficulty tier)\n"
            f"**Primary Jurisdiction:** {target_case.primary_location}\n"
            f"**Network Topology:** {target_case.topology} with {target_case.n_network_entities} identified operational entities.\n\n"
            f"#### Key Forensic Findings\n"
            f"- **FIR Records:** {len(firs)} formal registrations on file.\n"
            f"- **Flagged Anomalies:** {len(anomalies)} structural anomalies detected across telecom and financial layers.\n\n"
            f"#### Prioritized Investigative Leads:\n{leads_text}\n\n"
            f"> *Note: These candidates represent potential structural focal points identified by graph metrics, requiring investigator verification.*"
        )
        return answer, citations, leads

    # 2. General Syndicate & System Query
    top_kingpins = compute_kingpin_scores(db, limit=5)
    anomalies = run_all_detectors(db)

    for k in top_kingpins[:3]:
        citations.append(EvidenceCitation(
            source_type="persons.csv",
            identifier=k["person_id"],
            summary=f"{k['full_name']} ({k['city']}) - Score: {k['kingpin_score']}",
        ))
        leads.append(f"{k['full_name']} ({k['person_id']})")

    answer = (
        f"### CrimeNet Central Intelligence Overview\n\n"
        f"Currently monitoring **100 Active Cases** across synthetic Indian jurisdictions.\n\n"
        f"#### High-Priority Cross-Case Candidates:\n"
        + "\n".join([f"- **{k['full_name']}** ({k['person_id']}) | Score: {k['kingpin_score']} | Role: {k['role_classification']}" for k in top_kingpins[:5]])
        + f"\n\n#### Total Active Forensic Detections:\n"
        f"- Structuring & Mule Alerts: {len([a for a in anomalies if 'FINANCIAL' in a['detector_name']])}\n"
        f"- Burner Handset & Call Bursts: {len([a for a in anomalies if 'TELECOM' in a['detector_name'] or 'CDR' in a['detector_name']])}\n"
        f"- Cross-Case Syndicate Overlaps: {len([a for a in anomalies if 'CROSS_CASE' in a['detector_name']])}\n"
    )
    return answer, citations, leads


@router.post("/query", response_model=CopilotQueryResponse)
def query_copilot(body: CopilotQueryRequest, db: Session = Depends(get_db)):
    """
    Process an investigative question with evidence grounding.
    Uses Gemini API if key is present; otherwise falls back to deterministic engine.
    """
    # Deterministic evidence gathering
    det_answer, citations, leads = generate_deterministic_answer(body.query, body.case_id, db)
    engine_used = "deterministic_fallback"

    # Attempt Gemini API enhancement if key exists
    if settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-1.5-flash")

            prompt = (
                "You are an investigative assistant for the CrimeNet criminal network analysis system.\n"
                "Strict rule: NEVER accuse someone of being a criminal or call for an arrest. "
                "Use neutral, evidentiary terms: 'potential relationship', 'strong structural leadership candidate', 'investigative lead'.\n"
                "Ground all claims strictly in the following deterministic evidence:\n"
                f"{det_answer}\n\n"
                f"User Question: {body.query}\n"
                "Synthesize this into a professional, concise intelligence summary for an investigator."
            )
            resp = model.generate_content(prompt)
            if resp and resp.text:
                return CopilotQueryResponse(
                    query=body.query,
                    answer=resp.text,
                    engine_used="gemini-1.5-flash",
                    citations=citations,
                    recommended_leads=leads,
                )
        except Exception as exc:
            logger.warning(f"Gemini API call failed, falling back to deterministic: {exc}")

    return CopilotQueryResponse(
        query=body.query,
        answer=det_answer,
        engine_used=engine_used,
        citations=citations,
        recommended_leads=leads,
    )
