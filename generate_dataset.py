import os, csv, json, random, datetime, shutil
import config as C

random.seed(C.SEED)
BASE = os.path.join(os.path.dirname(__file__), "dataset")
EV = os.path.join(BASE, "evidence")
GT = os.path.join(BASE, "ground_truth")
DOCS = os.path.join(EV, "documents")
NEO = os.path.join(BASE, "neo4j")
META = os.path.join(BASE, "metadata")

for d in [BASE, EV, GT, DOCS, NEO, META, os.path.join(GT, "solutions")]:
    os.makedirs(d, exist_ok=True)

def pad(prefix, n, width=4):
    return f"{prefix}{str(n).zfill(width)}"

def rand_date(start, end):
    delta = (end - start).days
    return start + datetime.timedelta(days=random.randint(0, max(delta,0)),
                                       hours=random.randint(0,23), minutes=random.randint(0,59))

def synth_phone(i):
    return f"98{str(100000+i).zfill(8)}"[:10]

def synth_reg(city_code, i):
    return f"{city_code}-{random.randint(10,99)}-{chr(65+random.randint(0,25))}{chr(65+random.randint(0,25))}-{str(i).zfill(4)}"

CITY_CODE = {c: (c[:2].upper()) for c in C.CITIES}

# ---------------------------------------------------------------------------
# 1. GLOBAL ENTITY POOLS
# ---------------------------------------------------------------------------
persons = []       # list of dicts
phones = []
vehicles = []
organizations = []
accounts = []
locations = []

def make_name(gender):
    fn = random.choice(C.MALE_FIRST if gender=="M" else C.FEMALE_FIRST)
    ln = random.choice(C.LAST_NAMES)
    return fn, ln

def alias_variants(full_name):
    parts = full_name.split()
    fn, ln = parts[0], parts[-1]
    variants = [f"{fn[0]}. {ln}", f"{fn} {ln[0]}.", f"{fn} Kumar {ln}", f'"{fn[:3]}u"']
    return variants

# organizations first (persons reference them)
for i in range(1, C.N_ORGS+1):
    otype = random.choice(C.ORG_TYPES)
    city = random.choice(C.CITIES)
    name_root = random.choice(C.LAST_NAMES)
    template = random.choice(C.ORG_NAME_TEMPLATES)
    oname = template.format(name=name_root, suffix=C.ORG_SUFFIX[otype])
    organizations.append({
        "organization_id": pad("ORG", i),
        "organization_name": oname,
        "organization_type": otype,
        "city": city,
        "address": f"{random.randint(1,400)}, {random.choice(C.AREA_TEMPLATES).format(n=random.randint(1,60), letter=random.choice('ABCD'))}, {city}",
    })

# locations
for i in range(1, C.N_LOCATIONS+1):
    city = random.choice(C.CITIES)
    ltype = random.choice(list(C.LOCATION_NAME_TEMPLATES.keys()))
    area = random.choice(C.AREA_TEMPLATES).format(n=random.randint(1,60), letter=random.choice("ABCD"))
    lname = random.choice(C.LOCATION_NAME_TEMPLATES[ltype]).format(area=area)
    locations.append({
        "location_id": pad("LOC", i),
        "city": city,
        "area": area,
        "location_name": lname,
        "latitude": round(20 + random.random()*10, 6),
        "longitude": round(72 + random.random()*15, 6),
        "location_type": ltype,
    })

# persons
for i in range(1, C.N_PERSONS+1):
    gender = random.choice(["M","F"])
    fn, ln = make_name(gender)
    full_name = f"{fn} {ln}"
    alias = random.choice(alias_variants(full_name)) if random.random() < C.NOISE["aliases"] else ""
    city = random.choice(C.CITIES)
    persons.append({
        "person_id": pad("P", i),
        "full_name": full_name,
        "alias": alias,
        "age": random.randint(19,62),
        "gender": gender,
        "city": city,
        "occupation": random.choice(C.OCCUPATIONS),
        "address": f"House {random.randint(1,900)}, {random.choice(C.AREA_TEMPLATES).format(n=random.randint(1,60), letter=random.choice('ABCD'))}, {city}",
        "phone_ids": [],
        "vehicle_ids": [],
        "organization_ids": [],
    })

# phones (most persons 1, some 2)
phone_counter = 1
for p in persons:
    n_phones = 1 if random.random() > 0.15 else 2
    for _ in range(n_phones):
        if phone_counter > C.N_PHONES: break
        pid = pad("PH", phone_counter)
        phones.append({"phone_id": pid, "person_id": p["person_id"], "number": synth_phone(phone_counter)})
        p["phone_ids"].append(pid)
        phone_counter += 1

# vehicles (subset of persons own vehicles)
vehicle_counter = 1
owners = random.sample(persons, min(C.N_VEHICLES, len(persons)))
for owner in owners:
    if vehicle_counter > C.N_VEHICLES: break
    vtype = random.choice(C.VEHICLE_TYPES)
    make = random.choice(C.VEHICLE_MAKES[vtype])
    model = random.choice(C.VEHICLE_MODELS[make])
    city = owner["city"]
    vid = pad("VEH", vehicle_counter)
    vehicles.append({
        "vehicle_id": vid,
        "registration_id": synth_reg(CITY_CODE[city], vehicle_counter),
        "vehicle_type": vtype, "make": make, "model": model,
        "color": random.choice(C.VEHICLE_COLORS),
        "owner_person_id": owner["person_id"],
        "registration_city": city,
    })
    owner["vehicle_ids"].append(vid)
    vehicle_counter += 1

# bank accounts
account_counter = 1
acct_holders = random.sample(persons, min(C.N_ACCOUNTS, len(persons)))
for holder in acct_holders:
    if account_counter > C.N_ACCOUNTS: break
    aid = pad("ACC", account_counter)
    accounts.append({
        "account_id": aid, "person_id": holder["person_id"],
        "bank_name": random.choice(C.BANK_NAMES),
        "branch_city": holder["city"],
        "account_type": random.choice(["Savings","Current"]),
        "opening_date": rand_date(datetime.datetime(2015,1,1), datetime.datetime(2025,1,1)).date().isoformat(),
    })
    account_counter += 1

# person <-> organization associations (legit employment fabric)
for p in persons:
    if random.random() < 0.6:
        org = random.choice(organizations)
        p["organization_ids"].append(org["organization_id"])

PERSON_BY_ID = {p["person_id"]: p for p in persons}
ACCOUNTS_BY_PERSON = {}
for a in accounts:
    ACCOUNTS_BY_PERSON.setdefault(a["person_id"], []).append(a["account_id"])
VEHICLES_BY_PERSON = {}
for v in vehicles:
    VEHICLES_BY_PERSON.setdefault(v["owner_person_id"], []).append(v["vehicle_id"])
PHONES_BY_PERSON = {}
for ph in phones:
    PHONES_BY_PERSON.setdefault(ph["person_id"], []).append(ph["phone_id"])

# ---------------------------------------------------------------------------
# 2. DIFFICULTY / CASE PLAN
# ---------------------------------------------------------------------------
diff_counts = {}
remaining = C.N_CASES
keys = list(C.DIFFICULTY_RATIO.keys())
for i, k in enumerate(keys):
    if i == len(keys)-1:
        diff_counts[k] = remaining
    else:
        n = round(C.N_CASES * C.DIFFICULTY_RATIO[k])
        diff_counts[k] = n
        remaining -= n

case_plan = []
for k, n in diff_counts.items():
    case_plan += [k]*n
random.shuffle(case_plan)

# ---------------------------------------------------------------------------
# 3. ACCUMULATORS (global evidence tables)
# ---------------------------------------------------------------------------
cases_rows = []
fir_rows, fir_person_rows = [], []
cdr_rows = []
tx_rows = []
loc_event_rows = []
relationship_rows = []
gt_networks, gt_roles, gt_true_rel, gt_anomalies, gt_timelines = [], [], [], [], []

fir_counter = cdr_counter = tx_counter = locev_counter = rel_counter = 1
officer_pool = [pad("OFF", i) for i in range(1, 26)]
police_stations = [f"PS-{CITY_CODE[c]}-{str(i).zfill(3)}" for i, c in enumerate(C.CITIES, start=1)]

CROSS_CASE_CANDIDATES = random.sample(persons, max(3, C.N_CASES//10))
cross_case_used = {p["person_id"]: [] for p in CROSS_CASE_CANDIDATES}

def maybe_missing(value):
    return "" if random.random() < C.NOISE["missing_data"] else value

def alias_or_name(person):
    if random.random() < C.NOISE["spelling_variations"]:
        parts = person["full_name"].split()
        misspelled = parts[0][:-1] + random.choice("aeiou") if len(parts[0])>3 else parts[0]
        return f"{misspelled} {parts[-1]}"
    if person["alias"] and random.random() < 0.5:
        return person["alias"]
    return person["full_name"]

NARRATIVE_TEMPLATES = [
    "On {date}, the complainant reported that {detail1}. During preliminary inquiry, references were made to an individual identified as {alias} and {detail2}. Investigators noted that {detail3}.",
    "The complainant, associated with {org}, stated that between {date1} and {date2} several communications were received. A person locally referred to as {alias} was reportedly seen near {location} shortly before the incident. {detail3}",
    "Preliminary inquiry into the matter revealed that {alias} was in contact with the complainant. A vehicle matching the description of {vehicle} was observed near {location}. Witnesses gave differing accounts of the timeline.",
]

WITNESS_TEMPLATES = [
    "I saw a person I believe was {alias} near {location} on the evening in question, though I cannot be fully certain given the poor lighting.",
    "{alias} was present at {location} along with another individual. They appeared to be discussing something in a hurried manner.",
    "I am not entirely sure, but the person resembled {alias}. It could also have been someone else of similar build.",
]

def write_document(case_id, doc_id, doc_type, text):
    case_dir = os.path.join(DOCS, case_id)
    os.makedirs(case_dir, exist_ok=True)
    with open(os.path.join(case_dir, f"{doc_id}.txt"), "w") as f:
        f.write(f"DOCUMENT_TYPE: {doc_type}\nCASE: {case_id}\n\n{text}\n")

# ---------------------------------------------------------------------------
# 4. CASE GENERATION LOOP
# ---------------------------------------------------------------------------
for case_num, difficulty in enumerate(case_plan, start=1):
    case_id = pad("CASE", case_num, 3)
    lo, hi = C.DIFFICULTY_ENTITY_RANGE[difficulty]
    cap = max(lo, min(hi, 30)) if C.DEMO_SCALE else hi
    n_entities = random.randint(lo, cap)  # cap for demo runtime
    topology = random.choice(C.TOPOLOGIES)
    crime_type = random.choice(C.CRIME_TYPES)
    primary_city = random.choice(C.CITIES)

    # pick network persons: mostly fresh, occasionally reuse a cross-case candidate
    use_cross = topology == "I_cross_case" or random.random() < 0.08
    network_people = random.sample(persons, min(n_entities, len(persons)))
    if use_cross and CROSS_CASE_CANDIDATES:
        bridge_person = random.choice(CROSS_CASE_CANDIDATES)
        if bridge_person not in network_people:
            network_people[-1] = bridge_person
        cross_case_used[bridge_person["person_id"]].append(case_id)
    else:
        bridge_person = None

    node_ids = [p["person_id"] for p in network_people]

    # assign hidden roles
    roles_assignment = {}
    coordinator = network_people[0]
    roles_assignment[coordinator["person_id"]] = "Coordinator"
    if len(network_people) > 1:
        fin_inter = network_people[1]
        roles_assignment[fin_inter["person_id"]] = "Financial Intermediary"
    else:
        fin_inter = coordinator
    remaining_people = network_people[2:]
    n_false_leads = max(1, int(len(network_people) * C.NOISE["false_leads"]))
    false_leads = random.sample(remaining_people, min(n_false_leads, len(remaining_people))) if remaining_people else []
    for fl in false_leads:
        roles_assignment[fl["person_id"]] = "False Lead"
    bridge_id = None
    if bridge_person:
        roles_assignment[bridge_person["person_id"]] = "Bridge / Communicator"
        bridge_id = bridge_person["person_id"]
    for p in network_people:
        if p["person_id"] not in roles_assignment:
            roles_assignment[p["person_id"]] = random.choice(
                ["Logistics Coordinator","Recruiter","Communicator","Document Handler",
                 "Vehicle Provider","Operational Member","Associate","Unrelated Person"])

    # true edges according to topology (simplified generative rule per type)
    true_edges = []
    ids = node_ids
    if topology in ("A_hierarchical",):
        for idx in range(1, len(ids)):
            true_edges.append((ids[0], ids[idx]))
    elif topology == "B_chain":
        for idx in range(len(ids)-1):
            true_edges.append((ids[idx], ids[idx+1]))
    elif topology == "C_dense_cluster":
        for a_i in range(len(ids)):
            for b_i in range(a_i+1, min(a_i+3, len(ids))):
                true_edges.append((ids[a_i], ids[b_i]))
    elif topology == "D_two_communities_broker":
        mid = len(ids)//2
        for idx in range(mid-1):
            true_edges.append((ids[idx], ids[idx+1]))
        for idx in range(mid, len(ids)-1):
            true_edges.append((ids[idx], ids[idx+1]))
        if mid < len(ids):
            true_edges.append((ids[mid-1] if mid>0 else ids[0], ids[mid]))
    elif topology in ("E_hub_spoke","F_multi_hub"):
        hubs = ids[:2] if topology=="F_multi_hub" and len(ids)>3 else ids[:1]
        for idx, nid in enumerate(ids):
            if nid not in hubs:
                true_edges.append((random.choice(hubs), nid))
    elif topology == "G_hidden_bridge":
        half = len(ids)//2
        for idx in range(half-1):
            true_edges.append((ids[idx], ids[idx+1]))
        for idx in range(half, len(ids)-1):
            true_edges.append((ids[idx], ids[idx+1]))
        if half>0 and half<len(ids):
            true_edges.append((ids[half-1], ids[half]))  # the bridge edge
    elif topology == "H_layered":
        third = max(1, len(ids)//3)
        layer1, layer2, layer3 = ids[:third], ids[third:2*third], ids[2*third:]
        for a in layer1:
            if layer2: true_edges.append((a, random.choice(layer2)))
        for b in layer2:
            if layer3: true_edges.append((b, random.choice(layer3)))
    elif topology == "I_cross_case":
        for idx in range(len(ids)-1):
            true_edges.append((ids[idx], ids[idx+1]))
    elif topology == "J_decoy_heavy":
        for idx in range(0, len(ids)-1, 2):
            true_edges.append((ids[idx], ids[idx+1]))

    # ---- timeline ----
    incident_dt = rand_date(datetime.datetime(2025,6,1), datetime.datetime(2026,8,1))
    timeline_events = []
    ev_id_local = 1
    for src, tgt in true_edges:
        ts = incident_dt - datetime.timedelta(days=random.randint(1,10), hours=random.randint(0,20))
        eid = f"{case_id}-EVT{str(ev_id_local).zfill(3)}"
        timeline_events.append({"event_id": eid, "case_id": case_id, "timestamp": ts.isoformat(),
                                 "person_ids": f"{src}|{tgt}", "location_id": random.choice(locations)["location_id"],
                                 "event_type": random.choice(["meeting","phone_call","vehicle_movement"]),
                                 "description": "Interaction preceding the reported incident."})
        ev_id_local += 1
    incident_event_id = f"{case_id}-EVT{str(ev_id_local).zfill(3)}"
    timeline_events.append({"event_id": incident_event_id, "case_id": case_id, "timestamp": incident_dt.isoformat(),
                             "person_ids": coordinator["person_id"], "location_id": random.choice(locations)["location_id"],
                             "event_type": "incident", "description": f"Reported {crime_type.lower()} incident."})
    gt_timelines.extend(timeline_events)

    # ---- FIR ----
    fir_id = pad("FIR", fir_counter); fir_counter += 1
    ps = random.choice(police_stations)
    victim = random.choice([p for p in network_people if roles_assignment[p["person_id"]] not in ("Coordinator",)] or network_people)
    complainant = victim
    fir_number = f"FIR/{incident_dt.year}/{case_id[-3:]}/{str(fir_counter).zfill(3)}"
    area = random.choice(C.AREA_TEMPLATES).format(n=random.randint(1,60), letter=random.choice("ABCD"))
    alias_used = alias_or_name(fin_inter)
    veh_choice = random.choice(vehicles)["registration_id"] if vehicles else "N/A"
    org_choice = random.choice(organizations)["organization_name"]
    loc_choice = random.choice(locations)["location_name"]
    narrative = random.choice(NARRATIVE_TEMPLATES).format(
        date=incident_dt.date().isoformat(), date1=(incident_dt-datetime.timedelta(days=3)).date().isoformat(),
        date2=incident_dt.date().isoformat(), alias=alias_used, org=org_choice,
        location=loc_choice, vehicle=veh_choice,
        detail1="an unauthorized transfer occurred from an associated account",
        detail2="a vehicle observed near the commercial premises",
        detail3="the sequence of events remains under verification")
    fir_rows.append({
        "fir_id": fir_id, "case_id": case_id, "fir_number": fir_number, "police_station_id": ps,
        "registration_date": (incident_dt+datetime.timedelta(days=1)).date().isoformat(),
        "incident_date": incident_dt.date().isoformat(), "crime_type": crime_type,
        "incident_city": primary_city, "incident_area": area,
        "complainant_id": complainant["person_id"], "victim_id": maybe_missing(victim["person_id"]),
        "officer_id": random.choice(officer_pool), "summary": narrative, "status": random.choice(["Registered","Under Investigation","Closed"]),
    })
    write_document(case_id, f"FIR_{fir_id}", "FIR", narrative)

    for p in network_people:
        role = "suspect" if roles_assignment[p["person_id"]] in ("Coordinator","Financial Intermediary") else \
               "witness" if roles_assignment[p["person_id"]]=="Witness" else \
               "victim" if p["person_id"]==victim["person_id"] else "mentioned_person"
        fir_person_rows.append({"fir_id": fir_id, "person_id": p["person_id"], "role": role,
                                 "confidence": round(random.uniform(0.4,0.95),2), "source": fir_id})

    # duplicate FIR row occasionally
    if random.random() < C.NOISE["duplicates"]:
        dup = dict(fir_rows[-1]); dup["fir_id"] = pad("FIR", fir_counter); fir_counter += 1
        fir_rows.append(dup)

    # ---- witness statement doc (with contradiction chance) ----
    witness = random.choice(network_people)
    wtext = random.choice(WITNESS_TEMPLATES).format(alias=alias_or_name(fin_inter), location=loc_choice)
    if random.random() < C.NOISE["contradictions"]:
        wtext += " On reflection, I may be mistaken about the exact date of this sighting."
    write_document(case_id, f"WITNESS_{case_id}_1", "Witness Statement", wtext)

    # ---- CDR generation (network calls + background noise) ----
    all_case_phones = []
    for p in network_people:
        all_case_phones += PHONES_BY_PERSON.get(p["person_id"], [])
    if not all_case_phones:
        all_case_phones = [random.choice(phones)["phone_id"]]

    for src, tgt in true_edges:
        src_phones = PHONES_BY_PERSON.get(src, [])
        tgt_phones = PHONES_BY_PERSON.get(tgt, [])
        if not src_phones or not tgt_phones: continue
        n_calls = random.randint(2,6)
        for _ in range(n_calls):
            ts = incident_dt - datetime.timedelta(days=random.randint(0,9), hours=random.randint(0,23))
            cdr_rows.append({
                "cdr_id": pad("CDR", cdr_counter), "case_id": case_id,
                "caller_phone_id": random.choice(src_phones), "receiver_phone_id": random.choice(tgt_phones),
                "timestamp": ts.isoformat(), "duration_seconds": random.randint(15,900),
                "call_type": random.choice(["voice","voice","sms"]),
                "tower_location_id": random.choice(locations)["location_id"],
            }); cdr_counter += 1
    # background/legit noise calls unrelated to true edges
    for _ in range(C.CDR_PER_CASE_BG):
        ts = incident_dt - datetime.timedelta(days=random.randint(0,20), hours=random.randint(0,23))
        cdr_rows.append({
            "cdr_id": pad("CDR", cdr_counter), "case_id": case_id,
            "caller_phone_id": random.choice(all_case_phones), "receiver_phone_id": random.choice(phones)["phone_id"],
            "timestamp": ts.isoformat(), "duration_seconds": random.randint(10,600),
            "call_type": random.choice(["voice","sms"]), "tower_location_id": random.choice(locations)["location_id"],
        }); cdr_counter += 1

    # ---- transactions (true chain + background legit transfers) ----
    coord_accts = ACCOUNTS_BY_PERSON.get(coordinator["person_id"], [])
    fin_accts = ACCOUNTS_BY_PERSON.get(fin_inter["person_id"], [])
    chain_accounts = (coord_accts + fin_accts) or [random.choice(accounts)["account_id"]]
    for other in network_people[2:5]:
        chain_accounts += ACCOUNTS_BY_PERSON.get(other["person_id"], [])
    chain_accounts = list(dict.fromkeys(chain_accounts))[:5] or [random.choice(accounts)["account_id"]]
    anomaly_tx_ids = []
    for idx in range(len(chain_accounts)-1):
        ts = incident_dt - datetime.timedelta(days=random.randint(0,5))
        amt = random.choice([49500, 82000, 150000, 235000])
        tid = pad("TX", tx_counter); tx_counter += 1
        tx_rows.append({"transaction_id": tid, "case_id": case_id, "timestamp": ts.isoformat(),
                         "sender_account": chain_accounts[idx], "receiver_account": chain_accounts[idx+1],
                         "amount": amt, "transaction_type": "transfer", "location": primary_city,
                         "description": "Fund transfer"})
        anomaly_tx_ids.append(tid)
    for _ in range(C.TX_PER_CASE_BG):
        ts = incident_dt - datetime.timedelta(days=random.randint(0,30))
        a1, a2 = random.choice(accounts)["account_id"], random.choice(accounts)["account_id"]
        tx_rows.append({"transaction_id": pad("TX", tx_counter), "case_id": case_id, "timestamp": ts.isoformat(),
                         "sender_account": a1, "receiver_account": a2, "amount": random.randint(500,20000),
                         "transaction_type": "legitimate transfer", "location": random.choice(C.CITIES),
                         "description": "Routine payment"}); tx_counter += 1

    # ---- location events (true co-location + legit noise) ----
    shared_loc = random.choice(locations)
    anomaly_loc_ids = []
    for p in [coordinator, fin_inter] + ([bridge_person] if bridge_person else []):
        ts = incident_dt - datetime.timedelta(days=random.randint(1,4), hours=random.randint(0,5))
        leid = f"{case_id}-LE{str(locev_counter).zfill(4)}"
        loc_event_rows.append({"event_id": leid, "case_id": case_id, "person_id": p["person_id"],
                                "location_id": shared_loc["location_id"], "timestamp": ts.isoformat(),
                                "event_type": "co-location", "source": "surveillance"})
        anomaly_loc_ids.append(leid); locev_counter += 1
    for p in random.sample(network_people, min(3, len(network_people))):
        ts = incident_dt - datetime.timedelta(days=random.randint(0,15))
        loc_event_rows.append({"event_id": f"{case_id}-LE{str(locev_counter).zfill(4)}", "case_id": case_id,
                                "person_id": p["person_id"], "location_id": random.choice(locations)["location_id"],
                                "timestamp": ts.isoformat(), "event_type": "routine", "source": "witness"}); locev_counter += 1

    # ---- relationships (graph edges w/ evidence pointer) ----
    for src, tgt in true_edges:
        rel_id = pad("REL", rel_counter); rel_counter += 1
        relationship_rows.append({"relationship_id": rel_id, "source_entity": src, "target_entity": tgt,
                                   "relationship_type": "CALLS", "timestamp": incident_dt.isoformat(),
                                   "source_record": "CDR", "confidence": round(random.uniform(0.5,0.95),2)})
    # false-lead decoy relationship (looks suspicious, is legitimate)
    if false_leads and network_people:
        fl = false_leads[0]
        other = random.choice(network_people)
        relationship_rows.append({"relationship_id": pad("REL", rel_counter), "source_entity": fl["person_id"],
                                   "target_entity": other["person_id"], "relationship_type": "ASSOCIATED_WITH",
                                   "timestamp": incident_dt.isoformat(), "source_record": "SHARED_ORG",
                                   "confidence": 0.3}); rel_counter += 1

    # ---- ground truth rows ----
    net_id = f"NET_{case_id}"
    gt_networks.append({"case_id": case_id, "network_id": net_id, "topology": topology,
                         "difficulty": difficulty, "n_entities": len(network_people)})
    for pid, role in roles_assignment.items():
        gt_roles.append({"case_id": case_id, "person_id": pid, "true_role": role})
    for src, tgt in true_edges:
        gt_true_rel.append({"case_id": case_id, "source": src, "target": tgt, "type": "TRUE_NETWORK_EDGE"})
    for tid in anomaly_tx_ids:
        gt_anomalies.append({"case_id": case_id, "anomaly_id": tid, "anomaly_type": "financial_chain"})
    for leid in anomaly_loc_ids:
        gt_anomalies.append({"case_id": case_id, "anomaly_id": leid, "anomaly_type": "co_location"})

    cases_rows.append({
        "case_id": case_id, "case_title": f"The {crime_type} in {primary_city}",
        "crime_type": crime_type, "date_range_start": (incident_dt-datetime.timedelta(days=20)).date().isoformat(),
        "date_range_end": incident_dt.date().isoformat(), "primary_location": primary_city,
        "difficulty": difficulty, "topology": topology, "n_network_entities": len(network_people),
    })

    solution = {
        "case_id": case_id, "true_network": ids,
        "key_entities": [coordinator["person_id"], fin_inter["person_id"]] + ([bridge_id] if bridge_id else []),
        "bridge_entities": [bridge_id] if bridge_id else [],
        "false_leads": [fl["person_id"] for fl in false_leads],
        "important_relationships": [{"source": s, "target": t, "type": "NETWORK_EDGE", "evidence": ["CDR", fir_id]} for s,t in true_edges],
        "anomalies": anomaly_tx_ids + anomaly_loc_ids,
        "timeline": [e["event_id"] for e in timeline_events],
    }
    with open(os.path.join(GT, "solutions", f"{case_id}.json"), "w") as f:
        json.dump(solution, f, indent=2)

print(f"Generated {len(cases_rows)} cases.")
