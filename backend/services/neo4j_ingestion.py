"""
Neo4j Graph Ingestion Service.
Loads Persons, Cases, Phones, Bank Accounts, Vehicles, Locations, and Relationships
from dataset/evidence and dataset/ground_truth into Neo4j.
"""
import csv
from pathlib import Path
from typing import Dict, Any, List
from backend.database import neo4j_db
from backend.services.schema_manager import init_neo4j_schema
from backend.logging_config import logger


def _read_csv(filepath: Path) -> List[Dict[str, str]]:
    if not filepath.exists():
        logger.warning(f"File not found: {filepath}")
        return []
    with open(filepath, mode="r", encoding="utf-8-sig", errors="replace") as f:
        return list(csv.DictReader(f))


def ingest_to_neo4j(evidence_dir: Path = Path("dataset/evidence"), gt_dir: Path = Path("dataset/ground_truth")) -> Dict[str, Any]:
    """Populate Neo4j with complete criminal network graph entities and edges."""
    if not neo4j_db.is_healthy():
        raise RuntimeError("Neo4j database is not healthy or reachable.")

    counts = {}

    with neo4j_db.get_session() as session:
        # 1. Initialize constraints and indexes
        init_neo4j_schema(session)

        # 2. Ingest Cases
        cases_file = evidence_dir / "cases.csv"
        cases = _read_csv(cases_file)
        if cases:
            session.run("""
            UNWIND $batch AS row
            MERGE (c:Case {case_id: row.case_id})
            SET c.case_title = row.case_title,
                c.crime_type = row.crime_type,
                c.difficulty = row.difficulty,
                c.topology = row.topology,
                c.primary_location = row.primary_location
            """, batch=[{
                "case_id": r["case_id"],
                "case_title": r.get("case_title", ""),
                "crime_type": r.get("crime_type", ""),
                "difficulty": r.get("difficulty", ""),
                "topology": r.get("topology", ""),
                "primary_location": r.get("primary_location", ""),
            } for r in cases])
            counts["cases"] = len(cases)

        # 3. Ingest Persons
        persons_file = evidence_dir / "persons.csv"
        persons = _read_csv(persons_file)
        if persons:
            session.run("""
            UNWIND $batch AS row
            MERGE (p:Person {person_id: row.person_id})
            SET p.full_name = row.full_name,
                p.alias = row.alias,
                p.city = row.city,
                p.occupation = row.occupation,
                p.age = toInteger(row.age),
                p.gender = row.gender
            """, batch=[{
                "person_id": r["person_id"],
                "full_name": r.get("full_name", r["person_id"]),
                "alias": r.get("alias", ""),
                "city": r.get("city", ""),
                "occupation": r.get("occupation", ""),
                "age": r.get("age") or "0",
                "gender": r.get("gender", ""),
            } for r in persons])
            counts["persons"] = len(persons)

        # 4. Ingest Bank Accounts
        accounts_file = evidence_dir / "bank_accounts.csv"
        accounts = _read_csv(accounts_file)
        if accounts:
            session.run("""
            UNWIND $batch AS row
            MERGE (b:BankAccount {account_id: row.account_id})
            SET b.bank_name = row.bank_name,
                b.branch_city = row.branch_city,
                b.account_type = row.account_type
            WITH b, row
            WHERE row.person_id IS NOT NULL AND row.person_id <> ''
            MATCH (p:Person {person_id: row.person_id})
            MERGE (p)-[:OWNS_ACCOUNT]->(b)
            """, batch=[{
                "account_id": r["account_id"],
                "bank_name": r.get("bank_name", ""),
                "branch_city": r.get("branch_city", ""),
                "account_type": r.get("account_type", ""),
                "person_id": r.get("person_id", ""),
            } for r in accounts])
            counts["bank_accounts"] = len(accounts)

        # 5. Ingest Phones
        phones_file = evidence_dir / "phones.csv"
        phones = _read_csv(phones_file)
        if phones:
            session.run("""
            UNWIND $batch AS row
            MERGE (ph:Phone {phone_id: row.phone_id})
            SET ph.number = row.number
            WITH ph, row
            WHERE row.person_id IS NOT NULL AND row.person_id <> ''
            MATCH (p:Person {person_id: row.person_id})
            MERGE (p)-[:OWNS_PHONE]->(ph)
            """, batch=[{
                "phone_id": r["phone_id"],
                "number": r.get("number", ""),
                "person_id": r.get("person_id", ""),
            } for r in phones])
            counts["phones"] = len(phones)

        # 6. Ingest Vehicles
        vehicles_file = evidence_dir / "vehicles.csv"
        vehicles = _read_csv(vehicles_file)
        if vehicles:
            session.run("""
            UNWIND $batch AS row
            MERGE (v:Vehicle {vehicle_id: row.vehicle_id})
            SET v.registration_id = row.registration_id,
                v.vehicle_type = row.vehicle_type,
                v.make = row.make,
                v.model = row.model
            WITH v, row
            WHERE row.owner_person_id IS NOT NULL AND row.owner_person_id <> ''
            MATCH (p:Person {person_id: row.owner_person_id})
            MERGE (p)-[:OWNS_VEHICLE]->(v)
            """, batch=[{
                "vehicle_id": r["vehicle_id"],
                "registration_id": r.get("registration_id", ""),
                "vehicle_type": r.get("vehicle_type", ""),
                "make": r.get("make", ""),
                "model": r.get("model", ""),
                "owner_person_id": r.get("owner_person_id", ""),
            } for r in vehicles])
            counts["vehicles"] = len(vehicles)

        # 7. Ingest Locations
        loc_file = evidence_dir / "locations.csv"
        locations = _read_csv(loc_file)
        if locations:
            session.run("""
            UNWIND $batch AS row
            MERGE (l:Location {location_id: row.location_id})
            SET l.location_name = row.location_name,
                l.city = row.city,
                l.area = row.area,
                l.latitude = toFloat(row.latitude),
                l.longitude = toFloat(row.longitude)
            """, batch=[{
                "location_id": r["location_id"],
                "location_name": r.get("location_name", ""),
                "city": r.get("city", ""),
                "area": r.get("area", ""),
                "latitude": r.get("latitude") or "0",
                "longitude": r.get("longitude") or "0",
            } for r in locations])
            counts["locations"] = len(locations)

        # 8. Ingest Person-to-Case Involvement (from FIR + FIRPerson)
        fir_file = evidence_dir / "fir.csv"
        fir_person_file = evidence_dir / "fir_person.csv"
        firs = {r["fir_id"]: r["case_id"] for r in _read_csv(fir_file)}
        fir_persons = _read_csv(fir_person_file)
        inv_batch = []
        for fp in fir_persons:
            c_id = firs.get(fp["fir_id"])
            if c_id and fp.get("person_id"):
                inv_batch.append({
                    "person_id": fp["person_id"],
                    "case_id": c_id,
                    "role": fp.get("role", "Suspect"),
                })
        if inv_batch:
            session.run("""
            UNWIND $batch AS row
            MATCH (p:Person {person_id: row.person_id})
            MATCH (c:Case {case_id: row.case_id})
            MERGE (p)-[r:INVOLVED_IN]->(c)
            SET r.role = row.role,
                r.case_id = row.case_id
            """, batch=inv_batch)
            counts["case_involvements"] = len(inv_batch)

        # 9. Ingest Relationships with case_id
        # We load true_relationships.csv which has exact (case_id, source, target, type)
        true_rel_file = gt_dir / "true_relationships.csv"
        true_rels = _read_csv(true_rel_file)
        if true_rels:
            session.run("""
            UNWIND $batch AS row
            MATCH (s:Person {person_id: row.source})
            MATCH (t:Person {person_id: row.target})
            MERGE (s)-[r:CALLS {case_id: row.case_id}]->(t)
            SET r.type = row.type,
                r.confidence = 0.95
            """, batch=[{
                "source": r["source"],
                "target": r["target"],
                "case_id": r["case_id"],
                "type": r.get("type", "CALLS"),
            } for r in true_rels])
            counts["true_relationships"] = len(true_rels)

        # 10. Also link transactions between Bank Accounts with case_id
        tx_file = evidence_dir / "transactions.csv"
        txs = _read_csv(tx_file)
        if txs:
            session.run("""
            UNWIND $batch AS row
            MATCH (s:BankAccount {account_id: row.sender})
            MATCH (t:BankAccount {account_id: row.receiver})
            MERGE (s)-[r:TRANSFERS_TO {transaction_id: row.tx_id}]->(t)
            SET r.amount = toFloat(row.amount),
                r.timestamp = row.timestamp,
                r.case_id = row.case_id
            """, batch=[{
                "tx_id": r["transaction_id"],
                "sender": r["sender_account"],
                "receiver": r["receiver_account"],
                "amount": r.get("amount") or "0",
                "timestamp": r.get("timestamp", ""),
                "case_id": r.get("case_id", ""),
            } for r in txs])
            counts["transactions"] = len(txs)

    logger.info(f"Neo4j ingestion successful: {counts}")
    return counts


if __name__ == "__main__":
    result = ingest_to_neo4j()
    print("Ingestion Complete:", result)
