"""
Case Management Router.
Backed by cases.csv and fir.csv ingested into the database system-of-record.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.postgres import get_db
from backend.models.evidence import Case, FIR, FIRPerson, Person, Vehicle, Transaction, CDR

router = APIRouter(prefix="/api/cases", tags=["Cases"])


class CaseSummaryResponse(BaseModel):
    case_id: str
    case_title: str
    crime_type: str
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    primary_location: Optional[str] = None
    difficulty: Optional[str] = None
    topology: Optional[str] = None
    n_network_entities: int = 0

    class Config:
        from_attributes = True


class FIRSummaryResponse(BaseModel):
    fir_id: str
    case_id: str
    fir_number: str
    registration_date: Optional[str] = None
    incident_date: Optional[str] = None
    incident_city: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


class CaseDetailResponse(CaseSummaryResponse):
    firs: List[FIRSummaryResponse] = []


@router.get("", response_model=List[CaseSummaryResponse])
def list_cases(
    search: Optional[str] = Query(None, description="Search in case title or primary location"),
    crime_type: Optional[str] = Query(None, description="Filter by crime category"),
    difficulty: Optional[str] = Query(None, description="Basic, Intermediate, Advanced, Expert"),
    topology: Optional[str] = Query(None, description="Network topology structure"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all criminal cases with flexible search, difficulty and topology filters."""
    query = db.query(Case)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Case.case_title.ilike(pattern),
                Case.primary_location.ilike(pattern),
                Case.case_id.ilike(pattern),
            )
        )

    if crime_type:
        query = query.filter(Case.crime_type == crime_type)

    if difficulty:
        query = query.filter(Case.difficulty.ilike(difficulty))

    if topology:
        query = query.filter(Case.topology == topology)

    cases = query.order_by(Case.case_id.asc()).offset(offset).limit(limit).all()
    return cases


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(case_id: str, db: Session = Depends(get_db)):
    """Fetch detailed metadata, network topology, and FIR records for a single case."""
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found",
        )

    firs = db.query(FIR).filter(FIR.case_id == case_id).all()
    
    return CaseDetailResponse(
        case_id=case.case_id,
        case_title=case.case_title,
        crime_type=case.crime_type,
        date_range_start=case.date_range_start,
        date_range_end=case.date_range_end,
        primary_location=case.primary_location,
        difficulty=case.difficulty,
        topology=case.topology,
        n_network_entities=case.n_network_entities,
        firs=[FIRSummaryResponse.model_validate(f) for f in firs],
    )


@router.get("/{case_id}/firs", response_model=List[FIRSummaryResponse])
def get_case_firs(case_id: str, db: Session = Depends(get_db)):
    """Retrieve all FIRs registered under the given case ID."""
    firs = db.query(FIR).filter(FIR.case_id == case_id).all()
    return [FIRSummaryResponse.model_validate(f) for f in firs]


@router.get("/{case_id}/assets")
def get_case_assets(case_id: str, db: Session = Depends(get_db)):
    """Fetch all vehicles, transactions, telecom records, and FIRs associated with this case."""
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case with ID '{case_id}' not found")

    firs = db.query(FIR).filter(FIR.case_id == case_id).all()
    fir_ids = [f.fir_id for f in firs]
    fir_persons = db.query(FIRPerson).filter(FIRPerson.fir_id.in_(fir_ids)).all() if fir_ids else []
    person_ids = list(set([fp.person_id for fp in fir_persons]))

    persons = db.query(Person).filter(Person.person_id.in_(person_ids)).all() if person_ids else []
    person_map = {p.person_id: p for p in persons}

    vehicles = db.query(Vehicle).filter(Vehicle.owner_person_id.in_(person_ids)).all() if person_ids else []
    vehicle_data = [{
        "vehicle_id": v.vehicle_id,
        "registration_id": v.registration_id,
        "make": v.make,
        "model": v.model,
        "color": v.color,
        "type": v.vehicle_type,
        "owner_person_id": v.owner_person_id,
        "owner_name": person_map[v.owner_person_id].full_name if v.owner_person_id in person_map else "Unknown",
        "city": v.registration_city
    } for v in vehicles]

    txs = db.query(Transaction).filter(Transaction.case_id == case_id).all()
    total_volume = sum(t.amount for t in txs) if txs else 0.0
    tx_data = [{
        "transaction_id": t.transaction_id,
        "sender_account": t.sender_account,
        "receiver_account": t.receiver_account,
        "amount": t.amount,
        "timestamp": t.timestamp,
        "type": t.transaction_type,
        "location": t.location
    } for t in txs[:50]]

    cdrs = db.query(CDR).filter(CDR.case_id == case_id).all()
    unique_callers = len(set([c.caller_phone_id for c in cdrs] + [c.receiver_phone_id for c in cdrs])) if cdrs else 0

    return {
        "case_id": case_id,
        "case_title": case.case_title,
        "crime_type": case.crime_type,
        "primary_location": case.primary_location,
        "total_suspects": len(person_ids),
        "firs": [{
            "fir_id": f.fir_id,
            "fir_number": f.fir_number,
            "incident_city": f.incident_city,
            "incident_date": f.incident_date,
            "summary": f.summary,
            "status": f.status
        } for f in firs],
        "vehicles_count": len(vehicle_data),
        "vehicles": vehicle_data,
        "financial_summary": {
            "total_transactions": len(txs),
            "total_volume": round(total_volume, 2),
            "recent_transactions": tx_data[:20]
        },
        "telecom_summary": {
            "total_calls": len(cdrs),
            "unique_numbers": unique_callers
        }
    }

