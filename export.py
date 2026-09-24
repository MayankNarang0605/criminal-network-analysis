import os, csv, json, random
import config as C
from generate_dataset import (
    persons, phones, vehicles, organizations, accounts, locations,
    cases_rows, fir_rows, fir_person_rows, cdr_rows, tx_rows, loc_event_rows,
    relationship_rows, gt_networks, gt_roles, gt_true_rel, gt_anomalies, gt_timelines,
    EV, GT, NEO, META, BASE, diff_counts,
)

def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row = dict(r)
            for k, v in row.items():
                if isinstance(v, list):
                    row[k] = "|".join(v)
            w.writerow(row)

# ---- evidence tables ----
write_csv(os.path.join(EV, "cases.csv"), cases_rows,
          ["case_id","case_title","crime_type","date_range_start","date_range_end",
           "primary_location","difficulty","topology","n_network_entities"])

write_csv(os.path.join(EV, "persons.csv"), persons,
          ["person_id","full_name","alias","age","gender","city","occupation","address",
           "phone_ids","vehicle_ids","organization_ids"])

write_csv(os.path.join(EV, "phones.csv"), phones, ["phone_id","person_id","number"])

write_csv(os.path.join(EV, "vehicles.csv"), vehicles,
          ["vehicle_id","registration_id","vehicle_type","make","model","color",
           "owner_person_id","registration_city"])

write_csv(os.path.join(EV, "organizations.csv"), organizations,
          ["organization_id","organization_name","organization_type","city","address"])

write_csv(os.path.join(EV, "locations.csv"), locations,
          ["location_id","city","area","location_name","latitude","longitude","location_type"])

write_csv(os.path.join(EV, "bank_accounts.csv"), accounts,
          ["account_id","person_id","bank_name","branch_city","account_type","opening_date"])

write_csv(os.path.join(EV, "fir.csv"), fir_rows,
          ["fir_id","case_id","fir_number","police_station_id","registration_date","incident_date",
           "crime_type","incident_city","incident_area","complainant_id","victim_id","officer_id",
           "summary","status"])

write_csv(os.path.join(EV, "fir_person.csv"), fir_person_rows,
          ["fir_id","person_id","role","confidence","source"])

write_csv(os.path.join(EV, "cdr.csv"), cdr_rows,
          ["cdr_id","case_id","caller_phone_id","receiver_phone_id","timestamp",
           "duration_seconds","call_type","tower_location_id"])

write_csv(os.path.join(EV, "transactions.csv"), tx_rows,
          ["transaction_id","case_id","timestamp","sender_account","receiver_account",
           "amount","transaction_type","location","description"])

write_csv(os.path.join(EV, "location_events.csv"), loc_event_rows,
          ["event_id","case_id","person_id","location_id","timestamp","event_type","source"])

write_csv(os.path.join(EV, "relationships.csv"), relationship_rows,
          ["relationship_id","source_entity","target_entity","relationship_type",
           "timestamp","source_record","confidence"])

# ---- ground truth tables (kept fully separate from evidence/) ----
write_csv(os.path.join(GT, "networks.csv"), gt_networks,
          ["case_id","network_id","topology","difficulty","n_entities"])
write_csv(os.path.join(GT, "roles.csv"), gt_roles, ["case_id","person_id","true_role"])
write_csv(os.path.join(GT, "true_relationships.csv"), gt_true_rel, ["case_id","source","target","type"])
write_csv(os.path.join(GT, "anomalies.csv"), gt_anomalies, ["case_id","anomaly_id","anomaly_type"])
write_csv(os.path.join(GT, "timelines.csv"), gt_timelines,
          ["event_id","case_id","timestamp","person_ids","location_id","event_type","description"])

# ---- train/validation/test split (by case, no ground truth leaked) ----
case_ids = [c["case_id"] for c in cases_rows]
random.shuffle(case_ids)
n = len(case_ids)
n_test = max(1, round(n*0.20))
n_val = max(1, round(n*0.20))
test_ids = set(case_ids[:n_test])
val_ids = set(case_ids[n_test:n_test+n_val])
train_ids = set(case_ids) - test_ids - val_ids
for split_name, id_set in [("train", train_ids), ("validation", val_ids), ("test", test_ids)]:
    with open(os.path.join(BASE, split_name, "case_ids.txt") if False else os.path.join(BASE, f"{split_name}_case_ids.txt"), "w") as f:
        f.write("\n".join(sorted(id_set)))

# ---- Neo4j export ----
def neo_write(name, rows, fieldnames):
    write_csv(os.path.join(NEO, name), rows, fieldnames)

neo_write("nodes_person.csv", [{"person_id:ID(Person)":p["person_id"], "full_name":p["full_name"],
                                 "city":p["city"]} for p in persons],
          ["person_id:ID(Person)","full_name","city"])
neo_write("nodes_vehicle.csv", [{"vehicle_id:ID(Vehicle)":v["vehicle_id"], "registration_id":v["registration_id"]} for v in vehicles],
          ["vehicle_id:ID(Vehicle)","registration_id"])
neo_write("nodes_organization.csv", [{"organization_id:ID(Organization)":o["organization_id"], "organization_name":o["organization_name"]} for o in organizations],
          ["organization_id:ID(Organization)","organization_name"])
neo_write("nodes_location.csv", [{"location_id:ID(Location)":l["location_id"], "location_name":l["location_name"]} for l in locations],
          ["location_id:ID(Location)","location_name"])
neo_write("nodes_case.csv", [{"case_id:ID(Case)":c["case_id"], "case_title":c["case_title"]} for c in cases_rows],
          ["case_id:ID(Case)","case_title"])
neo_write("relationships_calls.csv", [{":START_ID(Person)":r["source_entity"], ":END_ID(Person)":r["target_entity"],
                                       "confidence":r["confidence"], "source_record":r["source_record"]}
                                      for r in relationship_rows],
          [":START_ID(Person)",":END_ID(Person)","confidence","source_record"])

with open(os.path.join(NEO, "import.cypher"), "w") as f:
    f.write("""// Run with: neo4j-admin database import full --nodes=Person=nodes_person.csv \\
//   --nodes=Vehicle=nodes_vehicle.csv --nodes=Organization=nodes_organization.csv \\
//   --nodes=Location=nodes_location.csv --nodes=Case=nodes_case.csv \\
//   --relationships=CALLS=relationships_calls.csv
// Or, for an already-running DB, use LOAD CSV, e.g.:
LOAD CSV WITH HEADERS FROM 'file:///nodes_person.csv' AS row
MERGE (p:Person {person_id: row.`person_id:ID(Person)`}) SET p.full_name = row.full_name, p.city = row.city;

LOAD CSV WITH HEADERS FROM 'file:///relationships_calls.csv' AS row
MATCH (a:Person {person_id: row.`:START_ID(Person)`}), (b:Person {person_id: row.`:END_ID(Person)`})
MERGE (a)-[r:CALLS]->(b) SET r.confidence = toFloat(row.confidence), r.source_record = row.source_record;
""")

# ---- metadata / config snapshot ----
with open(os.path.join(META, "dataset_config.json"), "w") as f:
    json.dump({
        "seed": C.SEED, "demo_scale": C.DEMO_SCALE, "n_cases": C.N_CASES,
        "n_persons": C.N_PERSONS, "n_organizations": C.N_ORGS, "n_vehicles": C.N_VEHICLES,
        "n_phones": C.N_PHONES, "n_accounts": C.N_ACCOUNTS, "n_locations": C.N_LOCATIONS,
        "difficulty_distribution": diff_counts, "noise_config": C.NOISE,
    }, f, indent=2)

# ---- README ----
readme = f"""# Synthetic Criminal Network Investigation Dataset

**This dataset is entirely fictional.** All names, FIR numbers, phone numbers, account
numbers, vehicle registrations, and addresses are synthetically generated for academic
research and system evaluation. No real individuals, organizations, or events are
represented. Any resemblance to real records is coincidental.

## Purpose
Built to develop, test, and objectively evaluate an AI-powered criminal network
analysis system: entity extraction, entity resolution, relationship extraction,
knowledge-graph construction, network analysis, anomaly detection, timeline
reconstruction, and evidence fusion.

## Ground truth separation
- `evidence/` — everything the AI system is allowed to see (FIRs, CDRs, transactions,
  locations, vehicles, organizations, documents, relationships extracted from evidence).
- `ground_truth/` — sealed answer key (true networks, true roles, true relationships,
  anomalies, timelines, per-case `solutions/<CASE_ID>.json`). Never given to the system
  under test; used only by the evaluation harness.

## Scale (this run)
- Cases: {C.N_CASES} (Basic/Intermediate/Advanced/Expert ≈ {diff_counts})
- Persons: {C.N_PERSONS}, Organizations: {C.N_ORGS}, Vehicles: {C.N_VEHICLES},
  Phones: {C.N_PHONES}, Accounts: {C.N_ACCOUNTS}, Locations: {C.N_LOCATIONS}
- Seed: {C.SEED} (deterministic — same seed reproduces the same dataset)

This is a **demo-scale run**. The generator (`config.py` / `generate_dataset.py`)
supports the full spec (100+ cases, 1000+ persons, 10,000+ CDRs, etc.) by flipping
`DEMO_SCALE = False` in `config.py` — no schema changes needed, only larger loops.

## Schema
See `evidence/*.csv` headers and `ground_truth/*.csv` headers. Unstructured documents
(FIR narratives, witness statements) live under `evidence/documents/<CASE_ID>/`.

## Noise & ambiguity injected
Aliases, spelling variants, missing fields, duplicate FIR rows, contradictory witness
statements, false-lead relationships, and background/legitimate calls & transfers that
are NOT part of the true network — see `noise_config` in `metadata/dataset_config.json`.

## Train/validation/test split
Case IDs only (no ground truth) in `train_case_ids.txt`, `validation_case_ids.txt`,
`test_case_ids.txt` at the dataset root, roughly 60/20/20.

## Neo4j
`neo4j/nodes_*.csv`, `neo4j/relationships_calls.csv`, and `neo4j/import.cypher` —
either bulk `neo4j-admin database import` or `LOAD CSV` against a running instance.

## Evaluation
For each case, compare system output against `ground_truth/solutions/<CASE_ID>.json`:
entity resolution P/R/F1, relationship extraction P/R/F1, network/community overlap,
whether true hidden hubs/bridges rank highly, and timeline ordering accuracy. Report
per-case and aggregate scores — do not collapse into a single number only.

## Regenerating
```
python3 generate_dataset.py   # builds in-memory dataset
python3 export.py             # writes all CSV/JSON/Neo4j/README files
```
Change `SEED` in `config.py` for a different synthetic world; the same seed always
reproduces the same dataset.
"""
with open(os.path.join(BASE, "README.md"), "w") as f:
    f.write(readme)

# ---- final summary banner ----
n_docs = sum(len(files) for _,_,files in os.walk(os.path.join(EV, "documents")))
print("=" * 50)
print("SYNTHETIC CRIME INVESTIGATION DATASET GENERATED")
print("=" * 50)
print(f"Cases Generated:              {len(cases_rows)}")
print(f"Persons:                      {len(persons)}")
print(f"Organizations:                {len(organizations)}")
print(f"Vehicles:                     {len(vehicles)}")
print(f"Phones:                       {len(phones)}")
print(f"Bank Accounts:                {len(accounts)}")
print(f"Locations:                    {len(locations)}")
print()
print(f"FIR Records:                  {len(fir_rows)}")
print(f"CDR Records:                  {len(cdr_rows)}")
print(f"Transactions:                 {len(tx_rows)}")
print(f"Location Events:              {len(loc_event_rows)}")
print(f"Documents:                    {n_docs}")
print()
for k in ["Basic","Intermediate","Advanced","Expert"]:
    print(f"{k} Cases:{' '*(20-len(k))}{diff_counts.get(k,0)}")
print()
print(f"Ground Truth:                 SEALED (see ground_truth/)")
print(f"Dataset Seed:                 {C.SEED}")
print("=" * 50)
