"""
Case Investigation & Prosecution Reports Router (Phase 19).
Compiles court-ready investigation dossiers incorporating:
1. Case Overview & Short AI-Generated Case Summary
2. FIR Intelligence (Accused, Victims, Witnesses, Involvements)
3. Suspect Profiles (Aliases, Phones, Bank Accounts, Vehicles, Associates, Activities)
4. Network Analysis (Graph snapshot, Connections, Clusters, Bridges, Leadership Scores)
5. Financial Intelligence (Suspicious txs, Money flows, Fan-in/fan-out, Common accounts)
6. CDR Analysis (Call frequency, Communication bursts, Tower correlations)
7. Geospatial Analysis (Crime scenes, Hotspots, Displacement timeline map)
8. Forensic Anomalies (Detected patterns, Severity, Models used, Why flagged, Evidence)
9. Unified Forensic Timeline (FIR + Calls + Transactions + Locations)
10. AI Investigation Summary (Key findings, Important connections, Leads, No guilt verdict)
11. Conclusion & Open Questions (Next steps, recommended subpoenas)
12. Section 65B Indian Evidence Act Cryptographic Verification Certificate
13. Officer Sign-Off, Editable Notes, Versioning, and Audit Trail

Export options:
- DOCX Export: /api/reports/{case_id}/export/docx
- JSON Export: /api/reports/{case_id}/export/json
- Print / PDF: Clean print media styling via window.print()
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.postgres import get_db
from backend.services.report_service import build_structured_case_report, generate_docx_report

router = APIRouter(prefix="/api/reports", tags=["Reports"])

# In-memory storage for saved drafts and officer notes
SAVED_REPORT_CUSTOMIZATIONS: Dict[str, Dict[str, Any]] = {}


class SaveReportRequest(BaseModel):
    officer_name: Optional[str] = "Investigating Officer (DSP / Inspector)"
    badge_number: Optional[str] = "POL-IND-8842"
    station_unit: Optional[str] = "Central Crime Investigation Department / Cyber Cell"
    notes: Optional[str] = None
    version: Optional[str] = "v1.0"
    status: Optional[str] = "FINAL"


@router.get("/{case_id}")
def get_case_report(
    case_id: str,
    officer_name: Optional[str] = None,
    badge_number: Optional[str] = None,
    station_unit: Optional[str] = None,
    version: Optional[str] = None,
    report_status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Generate comprehensive court-ready structured investigation dossier for a specific case.
    """
    saved = SAVED_REPORT_CUSTOMIZATIONS.get(case_id, {})
    
    off_name = officer_name or saved.get("officer_name") or "Investigating Officer (DSP / Inspector)"
    b_num = badge_number or saved.get("badge_number") or "POL-IND-8842"
    st_unit = station_unit or saved.get("station_unit") or "Central Crime Investigation Department / Cyber Cell"
    ver = version or saved.get("version") or "v1.0"
    st = report_status or saved.get("status") or "FINAL"
    custom_notes = saved.get("notes")

    try:
        report = build_structured_case_report(
            db=db,
            case_id=case_id,
            officer_name=off_name,
            badge_number=b_num,
            station_unit=st_unit,
            notes=custom_notes,
            version=ver,
            report_status=st,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Report generation error: {exc}")

    # Ensure backwards compatibility keys for legacy components
    report["case_info"] = report["case_overview"]
    report["firs"] = report["fir_intelligence"]["firs"]
    report["firs_registered"] = report["fir_intelligence"]["firs"]
    report["key_suspects"] = report["network_analysis"]["top_leadership_ranking"]
    report["key_investigative_leads"] = report["network_analysis"]["top_leadership_ranking"]
    report["forensic_typologies"] = report["anomalies"]
    report["detected_forensic_anomalies"] = report["anomalies"]

    return report


@router.post("/{case_id}/save")
def save_case_report_notes(
    case_id: str,
    payload: SaveReportRequest,
    db: Session = Depends(get_db)
):
    """
    Save officer notes, versioning, and investigator customizations for a case report.
    """
    now_iso = datetime.utcnow().isoformat() + "Z"
    
    if case_id not in SAVED_REPORT_CUSTOMIZATIONS:
        SAVED_REPORT_CUSTOMIZATIONS[case_id] = {
            "audit_log": []
        }

    SAVED_REPORT_CUSTOMIZATIONS[case_id]["officer_name"] = payload.officer_name
    SAVED_REPORT_CUSTOMIZATIONS[case_id]["badge_number"] = payload.badge_number
    SAVED_REPORT_CUSTOMIZATIONS[case_id]["station_unit"] = payload.station_unit
    SAVED_REPORT_CUSTOMIZATIONS[case_id]["notes"] = payload.notes
    SAVED_REPORT_CUSTOMIZATIONS[case_id]["version"] = payload.version
    SAVED_REPORT_CUSTOMIZATIONS[case_id]["status"] = payload.status
    SAVED_REPORT_CUSTOMIZATIONS[case_id]["last_updated"] = now_iso

    audit_entry = {
        "action": "NOTES_SAVED",
        "timestamp": now_iso,
        "officer": payload.officer_name,
        "version": payload.version,
        "notes_preview": (payload.notes[:60] + "...") if payload.notes else "No notes",
    }
    SAVED_REPORT_CUSTOMIZATIONS[case_id].setdefault("audit_log", []).append(audit_entry)

    return {
        "status": "success",
        "message": f"Investigation report draft saved for case {case_id}",
        "saved_data": SAVED_REPORT_CUSTOMIZATIONS[case_id],
    }


@router.get("/{case_id}/export/docx")
def export_case_report_docx(
    case_id: str,
    officer_name: Optional[str] = None,
    badge_number: Optional[str] = None,
    station_unit: Optional[str] = None,
    version: Optional[str] = None,
    report_status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Generate and download official Microsoft Word (.docx) Investigation Brief document.
    """
    saved = SAVED_REPORT_CUSTOMIZATIONS.get(case_id, {})
    off_name = officer_name or saved.get("officer_name") or "Investigating Officer (DSP / Inspector)"
    b_num = badge_number or saved.get("badge_number") or "POL-IND-8842"
    st_unit = station_unit or saved.get("station_unit") or "Central Crime Investigation Department / Cyber Cell"
    ver = version or saved.get("version") or "v1.0"
    st = report_status or saved.get("status") or "FINAL"
    custom_notes = saved.get("notes")

    try:
        report = build_structured_case_report(
            db=db,
            case_id=case_id,
            officer_name=off_name,
            badge_number=b_num,
            station_unit=st_unit,
            notes=custom_notes,
            version=ver,
            report_status=st,
        )
        docx_stream = generate_docx_report(report)
        docx_bytes = docx_stream.getvalue()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DOCX export failed: {exc}")

    filename = f"Investigation_Dossier_{case_id}_{datetime.utcnow().strftime('%Y%m%d')}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/{case_id}/export/json")
def export_case_report_json(
    case_id: str,
    db: Session = Depends(get_db)
):
    """
    Download complete structured case investigation data as JSON.
    """
    return get_case_report(case_id=case_id, db=db)
