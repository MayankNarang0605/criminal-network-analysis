import csv, json, os
from collections import defaultdict

EV = "dataset/evidence"
GT = "dataset/ground_truth"

def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))

cases = load_csv(f"{EV}/cases.csv")
fir = load_csv(f"{EV}/fir.csv")
fir_person = load_csv(f"{EV}/fir_person.csv")
cdr = load_csv(f"{EV}/cdr.csv")
tx = load_csv(f"{EV}/transactions.csv")
locev = load_csv(f"{EV}/location_events.csv")
rels = load_csv(f"{EV}/relationships.csv")

gt_networks = load_csv(f"{GT}/networks.csv")
gt_roles = load_csv(f"{GT}/roles.csv")
gt_true_rel = load_csv(f"{GT}/true_relationships.csv")
gt_anom = load_csv(f"{GT}/anomalies.csv")
gt_timelines = load_csv(f"{GT}/timelines.csv")

# index by case
fir_by_case = defaultdict(list)
for r in fir: fir_by_case[r["case_id"]].append(r)
cdr_by_case = defaultdict(list)
for r in cdr: cdr_by_case[r["case_id"]].append(r)
tx_by_case = defaultdict(list)
for r in tx: tx_by_case[r["case_id"]].append(r)
locev_by_case = defaultdict(list)
for r in locev: locev_by_case[r["case_id"]].append(r)
true_rel_by_case = defaultdict(list)
for r in gt_true_rel: true_rel_by_case[r["case_id"]].append(r)
anom_by_case = defaultdict(list)
for r in gt_anom: anom_by_case[r["case_id"]].append(r)
roles_by_case = defaultdict(list)
for r in gt_roles: roles_by_case[r["case_id"]].append(r)

# person -> phone lookup for CDR-backing check
persons = load_csv(f"{EV}/persons.csv")
person_phones = {}
for p in persons:
    ids = p["phone_ids"].split("|") if p["phone_ids"] else []
    person_phones[p["person_id"]] = set(ids)
phone_to_person = {}
for p in persons:
    for ph in (p["phone_ids"].split("|") if p["phone_ids"] else []):
        phone_to_person[ph] = p["person_id"]

print("="*70)
print("PER-CASE COMPLETENESS + SOLVABILITY CHECK")
print("="*70)

report = []
for c in cases:
    cid = c["case_id"]
    n_fir = len(fir_by_case[cid])
    n_cdr = len(cdr_by_case[cid])
    n_tx = len(tx_by_case[cid])
    n_locev = len(locev_by_case[cid])
    n_docs = len(os.listdir(f"{EV}/documents/{cid}")) if os.path.isdir(f"{EV}/documents/{cid}") else 0
    true_edges = true_rel_by_case[cid]
    n_true_edges = len(true_edges)

    # check: for each true edge, is there at least one CDR connecting the two people's phones?
    case_cdrs = cdr_by_case[cid]
    cdr_pairs = set()
    for r in case_cdrs:
        pa = phone_to_person.get(r["caller_phone_id"])
        pb = phone_to_person.get(r["receiver_phone_id"])
        if pa and pb:
            cdr_pairs.add(frozenset([pa,pb]))
    backed = 0
    unbacked_edges = []
    for e in true_edges:
        pair = frozenset([e["source"], e["target"]])
        if pair in cdr_pairs:
            backed += 1
        else:
            unbacked_edges.append((e["source"], e["target"]))

    n_anom = len(anom_by_case[cid])
    n_roles = len(roles_by_case[cid])

    solvable = (n_true_edges > 0 and backed == n_true_edges and n_fir>0 and n_docs>0)

    report.append({
        "case_id": cid, "title": c["case_title"], "difficulty": c["difficulty"],
        "topology": c["topology"], "n_fir": n_fir, "n_cdr": n_cdr, "n_tx": n_tx,
        "n_locev": n_locev, "n_docs": n_docs, "n_true_edges": n_true_edges,
        "edges_backed_by_cdr": backed, "unbacked_edges": unbacked_edges,
        "n_anomalies": n_anom, "n_roles": n_roles, "solvable_flag": solvable,
    })

for r in report:
    print(f"\n{r['case_id']} | {r['title']}  [{r['difficulty']} / {r['topology']}]")
    print(f"  FIR:{r['n_fir']}  CDR:{r['n_cdr']}  TX:{r['n_tx']}  LocEvents:{r['n_locev']}  Docs:{r['n_docs']}")
    print(f"  True network edges: {r['n_true_edges']}  | backed by CDR evidence: {r['edges_backed_by_cdr']}/{r['n_true_edges']}")
    print(f"  Ground-truth roles assigned: {r['n_roles']}  | Anomalies flagged: {r['n_anomalies']}")
    print(f"  --> Fully evidence-backed & solvable: {r['solvable_flag']}")
    if r["unbacked_edges"]:
        print(f"  !! UNBACKED EDGES (no CDR support): {r['unbacked_edges']}")

n_solvable = sum(1 for r in report if r["solvable_flag"])
print("\n" + "="*70)
print(f"SUMMARY: {n_solvable}/{len(report)} cases fully evidence-backed (CDR covers every true edge)")
print("="*70)

with open("analysis_report.json","w") as f:
    json.dump(report, f, indent=2)
