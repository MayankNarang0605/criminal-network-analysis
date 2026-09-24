"""
Geospatial Intelligence Router (Phases 14 & 15).
Provides coordinates, CCTV camera infrastructure, ANPR vehicle tracks, and Women Safety corridors.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.postgres import get_db
from backend.models.evidence import Location, CCTVCamera, CCTVAnprEvent, FIR

router = APIRouter(prefix="/api/geo", tags=["Geospatial"])


@router.get("/locations")
def list_locations(
    city: Optional[str] = Query(None, description="Filter locations by city"),
    location_type: Optional[str] = Query(None, description="transport, warehouse, commercial, public, office"),
    limit: int = Query(300, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Retrieve geo-tagged locations for interactive Leaflet map rendering."""
    query = db.query(Location)
    if city:
        query = query.filter(Location.city.ilike(city))
    if location_type:
        query = query.filter(Location.location_type == location_type)

    locs = query.limit(limit).all()
    return [
        {
            "location_id": l.location_id,
            "city": l.city,
            "area": l.area,
            "name": l.location_name,
            "latitude": l.latitude,
            "longitude": l.longitude,
            "location_type": l.location_type,
        }
        for l in locs
        if l.latitude and l.longitude
    ]


@router.get("/movements")
def list_vehicle_movements(
    case_id: Optional[str] = None,
    plate_number: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Retrieve CCTV and ANPR vehicle sighting events with coordinates."""
    query = db.query(CCTVAnprEvent)
    if case_id:
        query = query.filter(CCTVAnprEvent.case_id == case_id)
    if plate_number:
        query = query.filter(CCTVAnprEvent.plate_number.ilike(f"%{plate_number}%"))

    events = query.order_by(CCTVAnprEvent.timestamp.desc()).limit(limit).all()

    # Join location coordinates
    loc_ids = [e.location_id for e in events if e.location_id]
    locs = db.query(Location).filter(Location.location_id.in_(loc_ids)).all() if loc_ids else []
    loc_map = {l.location_id: l for l in locs}

    res = []
    for e in events:
        loc = loc_map.get(e.location_id)
        res.append({
            "event_id": e.event_id,
            "case_id": e.case_id,
            "plate_number": e.plate_number,
            "timestamp": e.timestamp,
            "camera_id": e.camera_id,
            "location_id": e.location_id,
            "location_name": loc.location_name if loc else None,
            "city": loc.city if loc else None,
            "latitude": loc.latitude if loc else None,
            "longitude": loc.longitude if loc else None,
            "description": e.description,
        })
    return res


@router.get("/corridors")
def list_women_safety_corridors(db: Session = Depends(get_db)):
    """Analyze high-density incident corridors from FIR locations."""
    locs = db.query(Location).all()
    loc_map = {l.location_id: l for l in locs}

    firs = db.query(FIR).all()
    city_counts = {}
    for f in firs:
        city = f.incident_city or "Unknown"
        city_counts[city] = city_counts.get(city, 0) + 1

    corridors = []
    for city, count in sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:15]:
        sample_loc = next((l for l in locs if l.city and l.city.lower() == city.lower()), None)
        corridors.append({
            "corridor_name": f"{city} Priority Surveillance Corridor",
            "city": city,
            "incident_count": count,
            "risk_level": "CRITICAL" if count >= 8 else "HIGH" if count >= 4 else "ELEVATED",
            "latitude": sample_loc.latitude if sample_loc else 28.6139,
            "longitude": sample_loc.longitude if sample_loc else 77.2090,
            "recommended_action": "Deploy mobile ANPR patrols and intensive lighting inspection.",
        })
    return corridors
