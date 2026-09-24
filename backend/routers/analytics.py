"""
Analytics & Anomaly Detection Router (Phases 9, 10, 11).
Serves live alerts for structuring, fan-in/fan-out, burner phones, and cross-case syndicates.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.postgres import get_db
from backend.services.detectors import (
    run_all_detectors,
    detect_structuring,
    detect_fan_in_fan_out,
    detect_burner_devices,
    detect_frequent_caller_spikes,
    detect_cross_case_overlap,
)
from backend.services.kingpin import compute_kingpin_scores

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

DETECTOR_REGISTRY = [
    {
        "name": "FINANCIAL_STRUCTURING_SMURFING",
        "category": "Financial",
        "description": "Detects transactions clustered just below legal anti-money laundering thresholds.",
        "default_severity": "HIGH",
    },
    {
        "name": "FINANCIAL_FAN_IN_AGGREGATION",
        "category": "Financial",
        "description": "Identifies funnel and mule accounts rapidly aggregating funds from multiple sources.",
        "default_severity": "HIGH",
    },
    {
        "name": "FINANCIAL_FAN_OUT_DISPERSAL",
        "category": "Financial",
        "description": "Identifies rapid fund dispersion across multiple recipient accounts.",
        "default_severity": "HIGH",
    },
    {
        "name": "TELECOM_BURNER_DEVICE_MULTI_SIM",
        "category": "Telecom",
        "description": "Identifies hardware handsets (IMEIs) cycled across multiple SIM cards or suspect identities.",
        "default_severity": "CRITICAL",
    },
    {
        "name": "CDR_FREQUENT_CALLER_BURST",
        "category": "Telecom",
        "description": "High-frequency communication bursts indicating operational syndicate coordination.",
        "default_severity": "HIGH",
    },
    {
        "name": "CROSS_CASE_SYNDICATE_OVERLAP",
        "category": "Syndicate",
        "description": "Discovers criminal operators present across multiple independent case investigations.",
        "default_severity": "CRITICAL",
    },
]


@router.get("/detectors")
def list_detectors():
    """Retrieve catalog of available forensic pattern detectors."""
    return DETECTOR_REGISTRY


@router.get("/anomalies")
def get_anomalies(
    case_id: Optional[str] = Query(None, description="Filter anomalies by case ID"),
    anomaly_type: Optional[str] = Query(None, description="Financial, CDR, Geospatial"),
    severity: Optional[str] = Query(None, description="HIGH, CRITICAL, MEDIUM, LOW"),
    detector_name: Optional[str] = Query(None, description="Specific detector algorithm"),
    engine: Optional[str] = Query(None, description="ML or RULE"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Retrieve prioritized grouped anomalies (ML + Rules) with triage funnel stats."""
    alerts = run_all_detectors(db, case_id=case_id)

    # Compute overall funnel counts for this case
    total_detected = len(alerts)
    critical_count = sum(1 for a in alerts if a.get("severity") == "CRITICAL")
    high_count = sum(1 for a in alerts if a.get("severity") == "HIGH")
    medium_count = sum(1 for a in alerts if a.get("severity") == "MEDIUM")
    low_count = sum(1 for a in alerts if a.get("severity") == "LOW")

    financial_count = sum(1 for a in alerts if a.get("anomaly_type") == "Financial")
    cdr_count = sum(1 for a in alerts if a.get("anomaly_type") == "CDR")
    geospatial_count = sum(1 for a in alerts if a.get("anomaly_type") == "Geospatial")

    ml_list = [a for a in alerts if a.get("detection_engine") == "ML"]
    rule_list = [a for a in alerts if a.get("detection_engine") == "RULE"]

    # Apply filters
    filtered = alerts
    if engine:
        filtered = [a for a in filtered if a.get("detection_engine") == engine.upper()]

    if anomaly_type:
        filtered = [a for a in filtered if a.get("anomaly_type", "").lower() == anomaly_type.lower()]

    if severity:
        filtered = [a for a in filtered if a.get("severity") == severity.upper()]

    if detector_name:
        filtered = [a for a in filtered if a.get("detector_name") == detector_name]

    return {
        "case_id": case_id,
        "total_detected": total_detected,
        "total_anomalies": len(filtered),
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "financial_count": financial_count,
        "cdr_count": cdr_count,
        "geospatial_count": geospatial_count,
        "ml_count": len(ml_list),
        "rule_count": len(rule_list),
        "ml_anomalies": ml_list[:limit],
        "rule_anomalies": rule_list[:limit],
        "anomalies": filtered[:limit],
    }


@router.get("/financial")
def get_financial_analytics(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieve comprehensive Financial Intelligence:
    - 💰 Transaction Analysis (Inflows, Outflows, Senders, Receivers, Volume Spikes)
    - 🔄 Money Flow Chains (Multi-hop tracking: A -> B -> C -> D)
    - 🚨 Money Laundering Patterns (Structuring, Fan-in, Fan-out, Mule Funnels, Circular Flows)
    - 🔗 Cross-Case Financial Connections (Shared bank accounts, multi-case suspects)
    - 📊 Financial Risk Analytics (Total money analyzed, suspicious volume, pattern breakdown)
    """
    from backend.services.financial_service import analyze_financial_intelligence
    return analyze_financial_intelligence(db, case_id=case_id)


@router.get("/telecom")
def get_telecom_analytics(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieve comprehensive CDR & Telecom Intelligence:
    - Directional call summaries, durations, frequency, modality, top cell towers
    - Frequent communication pairs (A <-> B)
    - Hidden connector detection (A -> X, B -> X, C -> X)
    - Temporal communication escalation / pre-incident surges
    - Cell tower location correlation and co-location
    - Unified Forensic Communication Timeline
    - Multi-SIM burner devices and shared handsets
    """
    from backend.services.cdr_service import analyze_case_cdr
    return analyze_case_cdr(db, case_id=case_id)



@router.get("/kingpins")
def get_kingpin_rankings(
    case_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Retrieve ranked structural leadership candidates with multi-factor breakdown."""
    candidates = compute_kingpin_scores(db, case_id=case_id, limit=limit)
    return {
        "case_id": case_id,
        "total_ranked": len(candidates),
        "candidates": candidates,
        "disclaimer": "⚠️ Network Leadership/Centrality Score is a structural topological metric — NOT a measure of legal guilt probability.",
    }
