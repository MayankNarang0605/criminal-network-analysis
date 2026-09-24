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

lines = []
lines.append("# Synthetic Criminal Network Investigation Dataset — 100 Case Stories\n")
lines.append("All names, FIR numbers, phone/account/vehicle identifiers, and addresses below are "
              "synthetically generated for academic research and system evaluation. No real people, "
              "organizations, or events are represented.\n")
lines.append("## Summary table\n")
lines.append("| Case | Title | Crime Type | City | Difficulty | Topology | Network Size |")
lines.append("|---|---|---|---|---|---|---|")
for c in cases:
    lines.append(f"| {c['case_id']} | {c['case_title']} | {c['crime_type']} | {c['primary_location']} | "
                 f"{c['difficulty']} | {c['topology']} | {c['n_network_entities']} |")

lines.append("\n---\n\n## Full case details\n")
for c in cases:
    cid = c["case_id"]
    with open(f"{GT}/solutions/{cid}.json") as f:
        sol = json.load(f)
    lines.append(f"### {cid}: {c['case_title']}")
    lines.append(f"**Crime type:** {c['crime_type']}  \n"
                  f"**Location:** {c['primary_location']}  \n"
                  f"**Difficulty / Topology:** {c['difficulty']} / {c['topology']}  \n"
                  f"**Incident window:** {c['date_range_start']} to {c['date_range_end']}  \n"
                  f"**Network size:** {len(sol['true_network'])} entities")
    f0 = fir_by_case[cid][0] if fir_by_case[cid] else None
    if f0:
        lines.append(f"\n**FIR narrative ({f0['fir_id']}):** {f0['summary']}")
    key = sol["key_entities"]
    key_names = [f"{pid} ({persons[pid]['full_name']})" for pid in key if pid in persons]
    lines.append(f"\n**Key entities (coordinator / financial intermediary / bridge):** {', '.join(key_names)}")
    if sol["bridge_entities"]:
        lines.append(f"**Bridge entity:** {sol['bridge_entities']}")
    fl_names = [f"{pid} ({persons[pid]['full_name']})" for pid in sol["false_leads"] if pid in persons]
    lines.append(f"**False leads (ground truth — should NOT be flagged as culprits):** {', '.join(fl_names) if fl_names else 'none'}")
    lines.append(f"**True relationship edges:** {len(sol['important_relationships'])}  \n"
                  f"**Anomalies (hidden signal records):** {', '.join(sol['anomalies'])}  \n"
                  f"**Timeline events:** {len(sol['timeline'])}")
    lines.append("\n---\n")

with open("stories_100.md", "w") as f:
    f.write("\n".join(lines))

print("Wrote stories_100.md with", len(cases), "cases")
