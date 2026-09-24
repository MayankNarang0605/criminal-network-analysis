"""
Evidence CSV Ingestion Engine.
Reads all 21 evidence tables from `dataset/evidence/` and inserts into Postgres system-of-record.
Enforces exact schemas matching BUILD-SPEC Section 2.1 verbatim.
"""
import os
import csv
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.config import settings
from backend.logging_config import logger
from backend.postgres import SessionLocal, engine, Base
from backend.models import (
    Case, Person, Phone, SimCard, Device, PhoneSimImeiDevice,
    Vehicle, BankAccount, Organization, Location, FIR, FIRPerson,
    CDR, Transaction, TransactionTypology, CCTVCamera, CCTVAnprEvent,
    LocationEvent, Relationship, EvidenceMetadata, EvidenceHashChain
)


def get_dataset_evidence_dir() -> Path:
    """Resolve the evidence directory path."""
    configured_path = Path(settings.DATASET_PATH) / "evidence"
    if configured_path.exists():
        return configured_path
    
    # Check local workspace relative paths
    workspace_candidates = [
        Path("E:/criminal-network-analysis/dataset/evidence"),
        Path("./dataset/evidence"),
        Path("../dataset/evidence"),
    ]
    for c in workspace_candidates:
        if c.exists():
            return c
    return configured_path


def compute_sha256(row: Dict[str, Any]) -> str:
    """Deterministic SHA-256 content hash of row dictionary."""
    content = "|".join(f"{k}:{v}" for k, v in sorted(row.items()) if v is not None)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_csv_rows(file_path: Path) -> List[Dict[str, str]]:
    """Load rows from CSV using DictReader with utf-8-sig encoding."""
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return []
    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        return list(reader)


def ingest_cases(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "cases.csv")
    db.query(Case).delete()
    objects = []
    for r in rows:
        n_entities = int(r.get("n_network_entities", 0)) if r.get("n_network_entities") else 0
        objects.append(Case(
            case_id=r["case_id"],
            case_title=r["case_title"],
            crime_type=r["crime_type"],
            date_range_start=r.get("date_range_start"),
            date_range_end=r.get("date_range_end"),
            primary_location=r.get("primary_location"),
            difficulty=r.get("difficulty"),
            topology=r.get("topology"),
            n_network_entities=n_entities,
        ))
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} cases")
    return len(objects)


def ingest_persons(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "persons.csv")
    db.query(Person).delete()
    objects = []
    for r in rows:
        age_val = int(r["age"]) if r.get("age") and r["age"].isdigit() else None
        objects.append(Person(
            person_id=r["person_id"],
            full_name=r["full_name"],
            alias=r.get("alias") or None,
            age=age_val,
            gender=r.get("gender") or None,
            city=r.get("city") or None,
            occupation=r.get("occupation") or None,
            address=r.get("address") or None,
            phone_ids=r.get("phone_ids") or None,
            vehicle_ids=r.get("vehicle_ids") or None,
            organization_ids=r.get("organization_ids") or None,
        ))
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} persons")
    return len(objects)


def ingest_phones(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "phones.csv")
    db.query(Phone).delete()
    objects = [
        Phone(
            phone_id=r["phone_id"],
            person_id=r.get("person_id") or None,
            number=r["number"],
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} phones")
    return len(objects)


def ingest_sim_cards(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "sim_cards.csv")
    db.query(SimCard).delete()
    objects = [
        SimCard(
            sim_id=r["sim_id"],
            phone_id=r.get("phone_id") or None,
            imsi=r.get("imsi") or None,
            operator=r.get("operator") or None,
            activation_date=r.get("activation_date") or None,
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} sim cards")
    return len(objects)


def ingest_devices(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "devices.csv")
    db.query(Device).delete()
    objects = [
        Device(
            device_id=r["device_id"],
            imei=r["imei"],
            make=r.get("make") or None,
            model=r.get("model") or None,
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} devices")
    return len(objects)


def ingest_phone_sim_imei_device(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "phone_sim_imei_device.csv")
    db.query(PhoneSimImeiDevice).delete()
    objects = [
        PhoneSimImeiDevice(
            link_id=r["link_id"],
            phone_id=r.get("phone_id") or None,
            sim_id=r.get("sim_id") or None,
            device_id=r.get("device_id") or None,
            person_id=r.get("person_id") or None,
            first_seen=r.get("first_seen") or None,
            last_seen=r.get("last_seen") or None,
            is_primary=r.get("is_primary", "").lower() in ("true", "1", "t"),
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} phone_sim_imei_device links")
    return len(objects)


def ingest_vehicles(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "vehicles.csv")
    db.query(Vehicle).delete()
    objects = [
        Vehicle(
            vehicle_id=r["vehicle_id"],
            registration_id=r["registration_id"],
            vehicle_type=r.get("vehicle_type") or None,
            make=r.get("make") or None,
            model=r.get("model") or None,
            color=r.get("color") or None,
            owner_person_id=r.get("owner_person_id") or None,
            registration_city=r.get("registration_city") or None,
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} vehicles")
    return len(objects)


def ingest_bank_accounts(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "bank_accounts.csv")
    db.query(BankAccount).delete()
    objects = [
        BankAccount(
            account_id=r["account_id"],
            person_id=r.get("person_id") or None,
            bank_name=r.get("bank_name") or None,
            branch_city=r.get("branch_city") or None,
            account_type=r.get("account_type") or None,
            opening_date=r.get("opening_date") or None,
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} bank accounts")
    return len(objects)


def ingest_organizations(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "organizations.csv")
    db.query(Organization).delete()
    objects = [
        Organization(
            organization_id=r["organization_id"],
            organization_name=r["organization_name"],
            organization_type=r.get("organization_type") or None,
            city=r.get("city") or None,
            address=r.get("address") or None,
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} organizations")
    return len(objects)


def ingest_locations(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "locations.csv")
    db.query(Location).delete()
    objects = []
    for r in rows:
        lat = float(r["latitude"]) if r.get("latitude") else None
        lon = float(r["longitude"]) if r.get("longitude") else None
        objects.append(Location(
            location_id=r["location_id"],
            city=r.get("city") or None,
            area=r.get("area") or None,
            location_name=r.get("location_name") or None,
            latitude=lat,
            longitude=lon,
            location_type=r.get("location_type") or None,
        ))
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} locations")
    return len(objects)


def ingest_fir(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "fir.csv")
    db.query(FIR).delete()
    objects = [
        FIR(
            fir_id=r["fir_id"],
            case_id=r["case_id"],
            fir_number=r["fir_number"],
            police_station_id=r.get("police_station_id") or None,
            registration_date=r.get("registration_date") or None,
            incident_date=r.get("incident_date") or None,
            crime_type=r.get("crime_type") or None,
            incident_city=r.get("incident_city") or None,
            incident_area=r.get("incident_area") or None,
            complainant_id=r.get("complainant_id") or None,
            victim_id=r.get("victim_id") or None,
            officer_id=r.get("officer_id") or None,
            summary=r.get("summary") or None,
            status=r.get("status") or None,
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} FIR records")
    return len(objects)


def ingest_fir_person(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "fir_person.csv")
    db.query(FIRPerson).delete()
    objects = []
    for r in rows:
        conf = float(r["confidence"]) if r.get("confidence") else 1.0
        objects.append(FIRPerson(
            fir_id=r["fir_id"],
            person_id=r["person_id"],
            role=r.get("role") or None,
            confidence=conf,
            source=r.get("source") or None,
        ))
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} fir_person links")
    return len(objects)


def ingest_cdr(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "cdr.csv")
    db.query(CDR).delete()
    # Batch in chunks of 5000 for high volume
    chunk_size = 5000
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i+chunk_size]
        objects = []
        for r in chunk:
            dur = int(r["duration_seconds"]) if r.get("duration_seconds") and r["duration_seconds"].isdigit() else 0
            objects.append(CDR(
                cdr_id=r["cdr_id"],
                case_id=r["case_id"],
                caller_phone_id=r["caller_phone_id"],
                receiver_phone_id=r["receiver_phone_id"],
                timestamp=r["timestamp"],
                duration_seconds=dur,
                call_type=r.get("call_type") or None,
                tower_location_id=r.get("tower_location_id") or None,
            ))
        db.bulk_save_objects(objects)
        db.commit()
        total += len(objects)
    logger.info(f"Ingested {total} CDR records")
    return total


def ingest_transactions(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "transactions.csv")
    db.query(Transaction).delete()
    chunk_size = 5000
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i+chunk_size]
        objects = []
        for r in chunk:
            amt = float(r["amount"]) if r.get("amount") else 0.0
            objects.append(Transaction(
                transaction_id=r["transaction_id"],
                case_id=r["case_id"],
                timestamp=r["timestamp"],
                sender_account=r["sender_account"],
                receiver_account=r["receiver_account"],
                amount=amt,
                transaction_type=r.get("transaction_type") or None,
                location=r.get("location") or None,
                description=r.get("description") or None,
            ))
        db.bulk_save_objects(objects)
        db.commit()
        total += len(objects)
    logger.info(f"Ingested {total} transactions")
    return total


def ingest_transactions_typology(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "transactions_typology.csv")
    db.query(TransactionTypology).delete()
    objects = []
    for r in rows:
        amt = float(r["amount"]) if r.get("amount") else 0.0
        objects.append(TransactionTypology(
            transaction_id=r["transaction_id"],
            case_id=r["case_id"],
            timestamp=r.get("timestamp") or None,
            sender_account=r.get("sender_account") or None,
            receiver_account=r.get("receiver_account") or None,
            amount=amt,
            transaction_type=r.get("transaction_type") or None,
            location=r.get("location") or None,
            description=r.get("description") or None,
        ))
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} typology transactions")
    return len(objects)


def ingest_cctv(db: Session, evidence_dir: Path) -> Dict[str, int]:
    cam_rows = load_csv_rows(evidence_dir / "cctv_cameras.csv")
    db.query(CCTVCamera).delete()
    cam_objects = [
        CCTVCamera(
            camera_id=r["camera_id"],
            location_id=r.get("location_id") or None,
            camera_type=r.get("camera_type") or None,
            city=r.get("city") or None,
        )
        for r in cam_rows
    ]
    db.bulk_save_objects(cam_objects)
    db.commit()

    event_rows = load_csv_rows(evidence_dir / "cctv_anpr_events.csv")
    db.query(CCTVAnprEvent).delete()
    event_objects = [
        CCTVAnprEvent(
            event_id=r["event_id"],
            case_id=r["case_id"],
            camera_id=r.get("camera_id") or None,
            location_id=r.get("location_id") or None,
            timestamp=r.get("timestamp") or None,
            detection_type=r.get("detection_type") or None,
            plate_number=r.get("plate_number") or None,
            description=r.get("description") or None,
        )
        for r in event_rows
    ]
    db.bulk_save_objects(event_objects)
    db.commit()
    logger.info(f"Ingested {len(cam_objects)} cameras, {len(event_objects)} CCTV/ANPR events")
    return {"cameras": len(cam_objects), "events": len(event_objects)}


def ingest_location_events(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "location_events.csv")
    db.query(LocationEvent).delete()
    objects = [
        LocationEvent(
            event_id=r["event_id"],
            case_id=r["case_id"],
            person_id=r["person_id"],
            location_id=r.get("location_id") or None,
            timestamp=r.get("timestamp") or None,
            event_type=r.get("event_type") or None,
            source=r.get("source") or None,
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} location events")
    return len(objects)


def ingest_relationships(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "relationships.csv")
    db.query(Relationship).delete()
    objects = []
    for r in rows:
        conf = float(r["confidence"]) if r.get("confidence") else 1.0
        objects.append(Relationship(
            relationship_id=r["relationship_id"],
            source_entity=r["source_entity"],
            target_entity=r["target_entity"],
            relationship_type=r["relationship_type"],
            timestamp=r.get("timestamp") or None,
            source_record=r.get("source_record") or None,
            confidence=conf,
        ))
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} relationships")
    return len(objects)


def ingest_evidence_metadata(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "evidence_metadata.csv")
    db.query(EvidenceMetadata).delete()
    objects = [
        EvidenceMetadata(
            evidence_id=r["evidence_id"],
            case_id=r["case_id"],
            source_table=r.get("source_table") or None,
            record_id=r.get("record_id") or None,
            evidence_type=r.get("evidence_type") or None,
            collected_date=r.get("collected_date") or None,
            custodian=r.get("custodian") or None,
        )
        for r in rows
    ]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Ingested {len(objects)} evidence metadata entries")
    return len(objects)


def ingest_evidence_hash_chain(db: Session, evidence_dir: Path) -> int:
    rows = load_csv_rows(evidence_dir / "evidence_hash_chain.csv")
    db.query(EvidenceHashChain).delete()
    chunk_size = 5000
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i+chunk_size]
        objects = []
        for r in chunk:
            seq = int(r["sequence_index"]) if r.get("sequence_index") and r["sequence_index"].isdigit() else None
            objects.append(EvidenceHashChain(
                evidence_id=r["evidence_id"],
                case_id=r["case_id"],
                source_table=r.get("source_table") or None,
                record_id=r.get("record_id") or None,
                sequence_index=seq,
                content_sha256=r["content_sha256"],
                previous_hash=r.get("previous_hash") or None,
                block_hash=r.get("block_hash") or None,
            ))
        db.bulk_save_objects(objects)
        db.commit()
        total += len(objects)
    logger.info(f"Ingested {total} evidence hash chain records")
    return total


def run_full_ingestion() -> Dict[str, Any]:
    """Execute complete ingestion of all 21 evidence tables into Postgres."""
    start_time = time.time()
    evidence_dir = get_dataset_evidence_dir()
    logger.info(f"Starting ingestion from {evidence_dir}")

    # Ensure tables are created
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    counts = {}
    try:
        counts["cases"] = ingest_cases(db, evidence_dir)
        counts["persons"] = ingest_persons(db, evidence_dir)
        counts["phones"] = ingest_phones(db, evidence_dir)
        counts["sim_cards"] = ingest_sim_cards(db, evidence_dir)
        counts["devices"] = ingest_devices(db, evidence_dir)
        counts["phone_sim_imei_device"] = ingest_phone_sim_imei_device(db, evidence_dir)
        counts["vehicles"] = ingest_vehicles(db, evidence_dir)
        counts["bank_accounts"] = ingest_bank_accounts(db, evidence_dir)
        counts["organizations"] = ingest_organizations(db, evidence_dir)
        counts["locations"] = ingest_locations(db, evidence_dir)
        counts["fir"] = ingest_fir(db, evidence_dir)
        counts["fir_person"] = ingest_fir_person(db, evidence_dir)
        counts["cdr"] = ingest_cdr(db, evidence_dir)
        counts["transactions"] = ingest_transactions(db, evidence_dir)
        counts["transactions_typology"] = ingest_transactions_typology(db, evidence_dir)
        cctv_counts = ingest_cctv(db, evidence_dir)
        counts.update(cctv_counts)
        counts["location_events"] = ingest_location_events(db, evidence_dir)
        counts["relationships"] = ingest_relationships(db, evidence_dir)
        counts["evidence_metadata"] = ingest_evidence_metadata(db, evidence_dir)
        counts["evidence_hash_chain"] = ingest_evidence_hash_chain(db, evidence_dir)
    finally:
        db.close()

    elapsed = round(time.time() - start_time, 2)
    logger.info(f"Ingestion completed in {elapsed}s: {counts}")
    return {
        "status": "success",
        "elapsed_seconds": elapsed,
        "counts": counts,
        "total_records": sum(counts.values()),
    }
