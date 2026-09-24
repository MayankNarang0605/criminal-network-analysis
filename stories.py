import csv, json, os
from collections import defaultdict

EV = "dataset/evidence"
GT = "dataset/ground_truth"

def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))

cases = load_csv(f"{EV}/cases.csv")
persons = {p["person_id"]: p for p in load_csv(f"{EV}/persons.csv")}
fir = load_csv(f"{EV}/fir.csv")

fir_by_case = defaultdict(list)
for r in fir:
    fir_by_case[r["case_id"]].append(r)

for c in cases:
    cid = c["case_id"]
    sol_path = f"{GT}/solutions/{cid}.json"
    with open(sol_path) as f:
        sol = json.load(f)
    print("="*70)
    print(f"{cid}: {c['case_title']}")
    print(f"Crime type: {c['crime_type']} | Location: {c['primary_location']} | Difficulty: {c['difficulty']} | Topology: {c['topology']}")
    print(f"Incident window: {c['date_range_start']} to {c['date_range_end']}")
    f0 = fir_by_case[cid][0] if fir_by_case[cid] else None
    if f0:
        print(f"\nFIR narrative ({f0['fir_id']}):")
        print(f"  {f0['summary']}")
    print(f"\nNetwork size: {len(sol['true_network'])} entities")
    key = sol["key_entities"]
    names = [f"{pid} ({persons[pid]['full_name']})" for pid in key if pid in persons]
    print(f"Key entities (coordinator/financial-intermediary/bridge): {', '.join(names)}")
    if sol["bridge_entities"]:
        print(f"Bridge entity: {sol['bridge_entities']}")
    fl_names = [f"{pid} ({persons[pid]['full_name']})" for pid in sol["false_leads"] if pid in persons]
    print(f"False leads (should NOT be flagged as culprits): {', '.join(fl_names)}")
    print(f"True relationship edges: {len(sol['important_relationships'])}")
    print(f"Anomalies (hidden signal records): {sol['anomalies']}")
    print(f"Timeline events: {len(sol['timeline'])}")
    print()
