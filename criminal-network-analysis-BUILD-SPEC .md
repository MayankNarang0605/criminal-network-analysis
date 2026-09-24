# AI-POWERED CRIMINAL NETWORK ANALYSIS & INVESTIGATION SYSTEM
## Master Build Specification (Antigravity-ready, dataset-locked)

> **How to use this file:** paste this whole document into Antigravity as the project
> brief. It replaces guesswork with exact contracts — every module below is wired to a
> real file, real column name, and real ground-truth CSV that already exists in the
> dataset shipped alongside this spec. Do not invent field names. If a module needs data
> that isn't listed in Section 2, either skip that module for v1 or say so explicitly —
> never fabricate a column or a metric.

---

## Quick start — getting this into Antigravity with the dataset

1. **Create the project folder** on disk, e.g. `criminal-network-analysis/`.
2. **Unzip your dataset into it** so the paths this spec references resolve as-is:
   ```
   criminal-network-analysis/
   ├── BUILD-SPEC.md              ← this file
   └── dataset/
       ├── evidence/
       ├── ground_truth/
       ├── neo4j/
       ├── metadata/
       ├── train_case_ids.txt
       ├── validation_case_ids.txt
       ├── test_case_ids.txt
       └── README.md
   ```
   i.e. unzip `crime-network-dataset-full100-COMPLETE.zip` and keep its inner `dataset/`
   folder at the project root — don't flatten it or rename subfolders, since every
   column/path in Section 2 assumes those exact locations.
3. **Open that folder as the workspace in Antigravity** (not a subfolder, not the zip
   itself — Antigravity needs to see both `BUILD-SPEC.md` and `dataset/` side by side so
   its agent can read the CSVs directly while coding against them).
4. **Give Antigravity this file as the task/brief** — paste the whole document into the
   chat/task box, or if Antigravity supports attaching a file as context, attach
   `BUILD-SPEC.md` directly. Either way, say up front: *"Follow this build spec exactly.
   The dataset is already present at `dataset/` in this workspace — read the real CSVs
   there before writing ingestion code, don't invent schemas."*
5. **Let it start at Phase 1** (Section 10) — infra only (React + FastAPI + Postgres +
   Neo4j + Docker booting). Don't let it try to build all 21 phases in one shot; after
   each phase, tell it to actually run ingestion/tests against `dataset/evidence/` and
   fix issues before moving on, per Section 0 rule 8.
6. **Keep `dataset/ground_truth/` present but tell Antigravity it's off-limits to the
   app** — it needs to be on disk for Phase 20 (the evaluation harness), just not wired
   into anything the running system queries. If Antigravity's agent tries to import
   `ground_truth/` into backend/frontend code, point it back to Section 0 rule 4.
7. Everything else (Neo4j seeding via `dataset/neo4j/import.cypher`, evaluation metrics,
   which repo pattern to follow) is already fully specified below — you shouldn't need
   to answer clarifying questions about schema; if Antigravity asks something not
   covered here, the answer is almost always "check the actual CSV headers in
   `dataset/evidence/` or `dataset/ground_truth/`."

---

## 0. Non-negotiable rules (read first, obey always)

1. **This is a decision-support prototype, not an accusation engine.** Never output
   "is a criminal," "arrest," or similar. Use: *potential relationship*, *strong
   structural leadership candidate*, *high-priority investigative lead*, *requires
   investigator review*.
2. **Every analytical claim must cite evidence** — a `case_id`, `evidence_id`,
   `transaction_id`, `cdr_id`, or graph finding that exists in the dataset. No invented
   suspects, scores, or transactions.
3. **Never fabricate metrics.** Every accuracy/precision/recall number the system reports
   must come from actually running an evaluator against the `ground_truth/` files in
   Section 2 — not from a hard-coded number or a plausible-sounding guess.
4. **Ground-truth separation is sacred.** Application code, ingestion, NLP, entity
   resolution, and the AI Copilot may only ever read from `dataset/evidence/`,
   `dataset/neo4j/`, and `dataset/metadata/`. Nothing under `dataset/ground_truth/`
   (including `solutions/*.json`) may be loaded by the running application — it is
   read **only** by a separate, offline `evaluation/` harness that scores the system
   after the fact. Wire this as a hard rule (e.g. the app's config never points at
   `ground_truth/`, and CI fails if it does).
5. **LLM is an explainer, never the source of truth.** Pipeline is always:
   raw data → extraction → entity resolution → graph → rules/statistics/ML → evidence
   → risk/network intelligence → LLM explanation. The LLM must never directly query an
   unrestricted database or invent a finding not already produced by a deterministic
   module.
6. **The app must fully function with the LLM off** (no API key / rate-limited /
   offline). Fallback = deterministic graph analytics + detectors + risk engine,
   rendered as plain evidence-backed text instead of a natural-language explanation.
7. **Every feature must actually work end-to-end against the real dataset files below.**
   No placeholder buttons, no mocked API responses in the delivered build.
8. Build in phases (Section 10). After each phase: implement → run it against the real
   dataset → fix → document → only then proceed.

---

## 1. Objective

Build a graph-centric criminal-network investigation platform that ingests the exact
dataset described in Section 2, resolves entities, builds a Neo4j knowledge graph,
runs detection/risk/kingpin analytics, and lets an investigator explore it through an
interactive network graph, a suspect dossier, a map, and an evidence-grounded AI
Copilot — then **measurably score itself** against the sealed ground truth using the
benchmark files that ship with the dataset. Target quality: an investigator command
center, not a CRUD dashboard.

**Concrete success criterion:** the system should correctly solve as many of the 100
cases in this dataset as possible — i.e. for each `CASE001`–`CASE100`, its predicted
network/kingpins/relationships should match `ground_truth/solutions/<CASE_ID>.json` as
closely as the difficulty tier allows. Section 9.5 defines "solved," how to score it per
case, and the tuning loop for pushing the solve rate up without compromising the
false-positive/evidence rules in Section 0.

---

## 2. THE DATASET — exact contract (read this before writing any ingestion code)

Root: `dataset/`. Fictional, synthetic, Indian-context data. Deterministic (seed-based).
Scale of this run: **100 cases**, 1000 persons, 150 organizations, 300 vehicles,
1200 phones, 800 accounts, 300 locations (`dataset/metadata/dataset_config.json` has
the exact counts, difficulty distribution `{Basic:20, Intermediate:30, Advanced:30,
Expert:20}`, and `noise_config`). `dataset/README.md` and `dataset/GAP_ANALYSIS_STATUS.md`
document intent and coverage — read both once before building ingestion.

### 2.1 `dataset/evidence/` — everything the application is allowed to see

| File | Columns |
|---|---|
| `persons.csv` | `person_id, full_name, alias, age, gender, city, occupation, address, phone_ids, vehicle_ids, organization_ids` |
| `phones.csv` | `phone_id, person_id, number` |
| `sim_cards.csv` | `sim_id, phone_id, imsi, operator, activation_date` |
| `devices.csv` | `device_id, imei, make, model` |
| `phone_sim_imei_device.csv` | `link_id, phone_id, sim_id, device_id, person_id, first_seen, last_seen, is_primary` |
| `vehicles.csv` | `vehicle_id, registration_id, vehicle_type, make, model, color, owner_person_id, registration_city` |
| `bank_accounts.csv` | `account_id, person_id, bank_name, branch_city, account_type, opening_date` |
| `organizations.csv` | `organization_id, organization_name, organization_type, city, address` |
| `locations.csv` | `location_id, city, area, location_name, latitude, longitude, location_type` |
| `cases.csv` | `case_id, case_title, crime_type, date_range_start, date_range_end, primary_location, difficulty, topology, n_network_entities` |
| `fir.csv` | `fir_id, case_id, fir_number, police_station_id, registration_date, incident_date, crime_type, incident_city, incident_area, complainant_id, victim_id, officer_id, summary, status` |
| `fir_person.csv` | `fir_id, person_id, role, confidence, source` |
| `cdr.csv` | `cdr_id, case_id, caller_phone_id, receiver_phone_id, timestamp, duration_seconds, call_type, tower_location_id` |
| `transactions.csv` | `transaction_id, case_id, timestamp, sender_account, receiver_account, amount, transaction_type, location, description` |
| `transactions_typology.csv` | same columns as `transactions.csv` — a labeled subset engineered to contain known laundering typologies (join to `ground_truth/financial_typologies.csv`) |
| `cctv_cameras.csv` | `camera_id, location_id, camera_type, city` |
| `cctv_anpr_events.csv` | `event_id, case_id, camera_id, location_id, timestamp, detection_type, plate_number, description` (`detection_type` includes vehicle sightings — this is also the vehicle-movement feed) |
| `location_events.csv` | `event_id, case_id, person_id, location_id, timestamp, event_type, source` |
| `relationships.csv` | `relationship_id, source_entity, target_entity, relationship_type, timestamp, source_record, confidence` — this is the noisy, evidence-derived relationship set (includes false leads); it is **not** the answer key |
| `evidence_metadata.csv` | `evidence_id, case_id, source_table, record_id, evidence_type, collected_date, custodian` |
| `evidence_hash_chain.csv` | `evidence_id, case_id, source_table, record_id, sequence_index, content_sha256, previous_hash, block_hash` — the hash-chain ledger for the Evidence Integrity module |
| `documents/<CASE_ID>/FIR_<fir_number>.txt` and `WITNESS_<CASE_ID>_N.txt` | unstructured FIR narratives and witness statements — feed the NLP/NER pipeline |
| `documents_pdf/` | PDF versions of documents, for the OCR/PDF ingestion path |
| `scanned_images/` | scanned image versions, ground-truthed by `ground_truth/ocr_ground_truth.csv` |

### 2.2 `dataset/neo4j/` — pre-built graph bulk-import files (use these; don't recompute)

`nodes_person.csv` (`person_id:ID(Person),full_name,city`), `nodes_case.csv`,
`nodes_location.csv`, `nodes_organization.csv`, `nodes_vehicle.csv`,
`relationships_calls.csv` (`:START_ID(Person),:END_ID(Person),confidence,source_record`),
and `import.cypher` (ready-made `neo4j-admin database import` / `LOAD CSV` script).
Use `import.cypher` as the seed loader for Section 6's graph schema, then extend it with
the additional node/relationship types your ingestion pipeline derives from the rest of
`evidence/` (Phone, SIM, IMEI, Device, BankAccount, Transaction, CCTV, Evidence, etc. —
these aren't pre-exported, so your Neo4j loader must create them from the corresponding
`evidence/*.csv` files using the node/relationship model in Section 6).

### 2.3 `dataset/ground_truth/` — sealed answer key. NEVER read from the running app.

Used **only** by `evaluation/` (Section 9).

| File | Columns | Scores which module |
|---|---|---|
| `networks.csv` | `case_id, network_id, topology, difficulty, n_entities` | network detection |
| `roles.csv` | `case_id, person_id, true_role` | kingpin/role engine |
| `true_relationships.csv` | `case_id, source, target, type` | relationship extraction / link prediction |
| `solutions/<CASE_ID>.json` | `case_id, true_network[], key_entities[], bridge_entities[], false_leads[], important_relationships[{source,target,type,evidence[]}]` | per-case end-to-end scoring — this is the master answer key per case |
| `anomalies.csv` | `case_id, anomaly_id, anomaly_type` | anomaly engine |
| `cdr_anomaly_labels.csv` | `case_id, cdr_id, anomaly_pattern` | CDR intelligence detectors |
| `financial_anomaly_labels.csv` | `case_id, transaction_id, anomaly_pattern` | financial intelligence detectors |
| `financial_typologies.csv` | `case_id, typology, transaction_ids, accounts_involved, description` | fan-in/out, layering, round-tripping, structuring, dormant→burst detectors |
| `device_burner_flags.csv` | `device_id, num_links, distinct_persons, is_burner_suspect` | burner SIM/IMEI detector |
| `cctv_person_resolution.csv` | `event_id, case_id, true_person_id` | CCTV/ANPR entity resolution |
| `link_prediction_benchmark.csv` | `case_id, source, target, label, split` | link prediction (Adamic-Adar/Jaccard/Resource Allocation/Preferential Attachment) |
| `er_benchmark_pairs.csv` | `pair_id, mention_a, mention_b, entity_a_id, entity_b_id, label, pair_type` | entity resolution precision/recall/F1/false-merge-rate |
| `ner_spans.csv` | `span_id, doc_id, case_id, start, end, text, label, entity_id` | NER extraction quality |
| `crime_classification_benchmark.csv` | `case_id, text, label, split` | crime classification accuracy/F1 |
| `known_innocent_entities.csv` | `case_id, person_id, true_role, is_innocent` | false-positive control |
| `false_positive_eval.csv` | `case_id, person_id, category, expected_system_behavior` | false-positive control |
| `evidence_verification_benchmark.csv` | `test_id, case_id, evidence_id, stored_content_sha256, presented_content_sha256, is_tampered, expected_verification_result, tamper_type` | evidence-integrity tamper detection |
| `merkle_roots.csv` | `case_id, merkle_root, n_evidence_items, chain_head_hash` | evidence-ledger Merkle verification |
| `ocr_ground_truth.csv` | `doc_id, case_id, image_path, ground_truth_text` | OCR accuracy |
| `timelines.csv` / `unified_investigation_timeline.csv` | per-case and cross-source timelines | timeline reconstruction ordering accuracy |
| `women_safety_case_flags.csv` | `fir_id, case_id, victim_gender, is_women_safety_case, location_id, area, city` | Women Safety module |
| `women_safety_corridors.csv` | `location_id, area, city, incident_count, risk_score` | trafficking-corridor / hotspot module |
| `ablation_protocol.json` | 7 named configs (e.g. PageRank-only → full model) | ablation study (Section 9.3) |

Splits: `dataset/train_case_ids.txt`, `validation_case_ids.txt`, `test_case_ids.txt`
(~60/20/20, case IDs only — no leakage of ground truth).

### 2.4 Regeneration (if a bigger run is ever needed)

```bash
python3 generate_dataset.py   # base synthetic world (seeded)
python3 export.py             # writes evidence/ + ground_truth/ + neo4j/
python3 augment.py            # adds devices, CCTV/ANPR, typologies, OCR, hash-chain, benchmarks
```
Do not re-run these as part of the application build — the dataset is already generated
and delivered; ingest it as-is.

---

## 3. Reference implementations (architecture inspiration only — dataset above wins on data shape)

Inspect, don't blindly clone, these four repos and take their **strongest pattern** for
each capability, adapted to the schema in Section 2:

### 3.1 Per-capability source table (use this as the primary decision rule)

If more than one repo has a given capability, use whichever implementation is more
mature/explainable/accurate for the unified architecture — this table just says where
to look first.

| Capability | Preferred source |
|---|---|
| FIR ingestion | Rohit / ATLAS |
| CDR analysis | **Rohit** |
| Banking / financial analysis | **Rohit** |
| CCTV / ANPR | **Thxrun / ATLAS** |
| Real-time events | **Thxrun / ATLAS** |
| Multi-modal ingestion architecture | **ATLAS / Thxrun** |
| Advanced entity extraction, Indian-name/phone/vehicle normalization | **Rohit** |
| Fuzzy entity matching, entity resolution | **Rohit** |
| Financial typologies (structuring/layering/fan-in/out/round-tripping/dormant→burst) | **Rohit** |
| Anomaly detection | **Rohit** |
| Kingpin detection, explainable risk | **Rohit** |
| Link prediction (Adamic-Adar, Jaccard, Preferential Attachment) | **Rohit** |
| Link prediction (Resource Allocation) | **Vaishnavi** |
| Cross-jurisdiction analysis | **Rohit** |
| Disruption / network-fragmentation simulation | **Rohit** |
| Women Safety intelligence, trafficking corridors, district hotspots | **Rohit** |
| PII masking, RBAC (data model) | **Rohit** |
| Hash-chain / Merkle evidence integrity | **Rohit / Thxrun / ATLAS** |
| FIR intake UI, NER workflow | **Vaishnavi** |
| Crime classification | **Vaishnavi** |
| Case intake, suspect dossier layout | **Vaishnavi** |
| Investigation timeline UI | **Vaishnavi** |
| Closeness centrality, shortest path, Louvain communities | **Vaishnavi** |
| Report generation, audit verification | **Vaishnavi** |
| **Network graph — visual & interaction baseline** | **Thxrun** (do not replace with a generic graph — see Section 7) |
| Neo4j architecture | **Thxrun** |
| 10 core detection engines (orchestration pattern) | **Thxrun** |
| Real-time event pipeline (WebSockets/SSE) | **Thxrun / ATLAS** |
| AI Copilot UX + deterministic offline fallback | **Thxrun / ATLAS** |
| Centrality visualization workflow | **Thxrun / ATLAS** |
| Docker architecture, testing architecture | **Thxrun / ATLAS** |
| Overall command-center layout, investigator dashboard flow | **ATLAS** |
| Evidence/ledger workflow UX | **ATLAS** |
| Detector orchestration | **ATLAS** |
| Reproducible demo flow, Docker deployment | **ATLAS** |
| Deterministic entity-matching foundation (baseline to improve on) | **ATLAS** |

### 3.2 Per-repo summary (same mapping, grouped the other way)

- **github.com/rohitselote/AI-Powered-Criminal-Network-Analysis** — primary source for:
  entity extraction/resolution, Indian-name/phone/vehicle normalization, fuzzy matching,
  CDR intelligence, financial-typology detection (structuring, layering, fan-in/fan-out,
  round-tripping, dormant→burst), anomaly detection, kingpin scoring, link prediction,
  cross-jurisdiction analysis, disruption simulation, Women Safety intelligence, PII
  masking, RBAC, hash-chain/Merkle integrity.
- **github.com/VaishnaviSalunke26/ministry_of_home_affairs** — primary source for: FIR
  intake UI, NER workflow, crime classification, case intake, suspect dossier,
  investigation timeline, closeness centrality/shortest path/Louvain, Resource
  Allocation link prediction, report generation, RBAC, audit verification.
- **github.com/Thxrun-07/AI-Powered-Criminal-Network-Analysis-System** — primary source
  for: the interactive network-graph UX (this is the visual/interaction baseline for
  Section 7 — the graph screen must feel like Thxrun's, not a static picture), Neo4j
  architecture, multi-modal ingestion, real-time event pipeline, Gemini Copilot with
  deterministic fallback, hash-chain ledger, Docker/testing architecture.
- **github.com/SIH-Novelex/ATLAS-AI-Powered-Criminal-Network-Analysis-System** —
  primary source for: overall command-center layout/architecture, investigator
  dashboard flow, Copilot workflow, evidence ledger UX, detector orchestration, live
  events, reproducible demo flow, Docker deployment.

Do not fabricate a feature just because one repo claims it — if a repo's feature has no
corresponding data in Section 2, it can still be built (the code doesn't need ground
truth to run), but it **cannot be claimed as benchmarked/accurate** unless a
Section 2.3 file backs it.

---

## 4. Technology stack

- **Frontend:** React + TypeScript + Vite + Tailwind CSS + shadcn/ui + React Router +
  TanStack Query + Lucide React
- **Graph visualization:** Cytoscape.js (interaction quality = Thxrun baseline, Section 7)
- **Map:** Leaflet (uses `locations.csv` lat/long + `women_safety_corridors.csv`)
- **Charts:** Recharts (D3 only if Recharts genuinely can't do it)
- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic
- **Databases:** PostgreSQL (system of record — mirrors `evidence/*.csv` tables) +
  Neo4j (relationship intelligence — seeded from `neo4j/*.csv` + `import.cypher`,
  extended per Section 6). Use both; do not replace Neo4j with Postgres graph tables.
- **NLP/ML:** spaCy (NER against `ner_spans.csv` schema), RapidFuzz (fuzzy entity
  matching), scikit-learn, NumPy, Pandas
- **OCR:** Tesseract and/or EasyOCR, scored against `ocr_ground_truth.csv`
- **LLM:** Gemini behind a swappable abstraction layer; must be disable-able
- **Security:** JWT, RBAC, Argon2/bcrypt, PII masking, audit logging, rate limiting
- **Deployment:** Docker + Docker Compose; whole system runs via `docker compose up`

---

## 5. Core pipeline

```
evidence/*.csv + documents/  ──►  OCR (scanned_images/, documents_pdf/)
       │                                    │
       ▼                                    ▼
  Structured loaders                  Text extraction
       │                                    │
       └───────────────► NER (spaCy, scored vs ner_spans.csv) ◄───┘
                              │
                              ▼
                  Entity normalization (Section 6.2)
                              │
                              ▼
              Entity resolution (scored vs er_benchmark_pairs.csv)
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
            PostgreSQL                   Neo4j (seeded from neo4j/*.csv)
                 │                         │
                 └────────────┬────────────┘
                              ▼
                     Detection engine (Section 6.4, scored vs *_anomaly_labels.csv,
                                        financial_typologies.csv, device_burner_flags.csv)
                              ▼
                      Anomaly engine (vs anomalies.csv)
                              ▼
              Kingpin / risk engine (vs roles.csv, solutions/*.json)
                              ▼
        Cross-case intelligence (vs true_relationships.csv, solutions/*.json)
                              ▼
     Geospatial intelligence (locations.csv, women_safety_corridors.csv)
                              ▼
              Disruption simulation (Neo4j recompute, no ground truth needed)
                              ▼
      AI Copilot (Gemini + deterministic fallback, evidence-grounded)
                              ▼
             Evidence-grounded report (PDF, per case)
```

---

## 6. Module-by-module contract

### 6.1 Ingestion
Load every `evidence/*.csv` into Postgres with schemas matching Section 2.1 exactly
(column names verbatim). Parse `documents/<CASE_ID>/*.txt` and `documents_pdf/` for the
FIR/witness-statement NLP path; run OCR on `scanned_images/` and diff output against
`ground_truth/ocr_ground_truth.csv` (offline, in `evaluation/`) to report OCR accuracy.
Every ingested record gets `source_id, case_id, source_type, timestamp,
ingestion_timestamp, content_hash, confidence, provenance` — `content_hash` and chain
fields should reconcile with `evidence_hash_chain.csv` for records that already have a
hash-chain entry.

### 6.2 Entity normalization & resolution
Normalize phone numbers (`+91 98765 43210` / `09876543210` / `9876543210` → one
identifier), vehicle registrations (`HR26AB1234` variants), and Indian name/alias
variants (`Mohd./Mohammed/Mohammad/Md`), using `persons.csv.alias` as a source of known
alias pairs. Exact-match on `phone_ids`, `vehicle_ids`, IMEI, account IDs first, then
RapidFuzz (Levenshtein/Jaro-Winkler) + phonetic matching, then contextual scoring
(shared phone/vehicle/address/account/case/associates). Produce a confidence-weighted
`ENTITY_MATCH_SCORE` bucketed HIGH/REVIEW/LOW — never auto-merge LOW. Score this module
by joining your resolved pairs against `er_benchmark_pairs.csv` (`label` = true/false
match, `pair_type` for slicing) → precision/recall/F1/false-merge-rate.

### 6.3 Neo4j knowledge graph
Nodes: `Person, Alias, Case, Phone, SIM, IMEI, Device, Vehicle, BankAccount, UPI,
Company/Organization, Location, CCTV, PoliceStation, Crime, Transaction, Evidence`.
Relationships: `KNOWS, CALLED, MESSAGED, USES_PHONE, USES_SIM, USES_DEVICE,
OWNS_VEHICLE, SEEN_IN_VEHICLE, USES_ACCOUNT, TRANSFERRED_TO, WORKS_FOR, MEMBER_OF,
INVOLVED_IN, LOCATED_AT, SEEN_AT, CONNECTED_TO_CASE, ASSOCIATED_WITH, SHARED_ADDRESS,
SHARED_DEVICE, SHARED_ACCOUNT, PART_OF_NETWORK`, each carrying
`confidence, source, timestamp, case_id, evidence_id`. Seed with `neo4j/import.cypher`,
then derive the remaining node/relationship types from `evidence/cdr.csv`,
`transactions.csv`, `phone_sim_imei_device.csv`, `cctv_anpr_events.csv`,
`fir_person.csv`, `bank_accounts.csv`, `organizations.csv`.

### 6.4 Detection engine (10 core + 13 financial/behavioral, per Section 3)
Frequent-caller spike, burner SIM/IMEI multi-swap (label vs `device_burner_flags.csv`),
hawala/layering chains, mule-account syndicates, cross-case suspect overlap, vehicle
convoy (`cctv_anpr_events.csv` co-location), crime-scene co-location, association
clusters, shell-company/dummy-address detection, centrality/leadership, plus
structuring/layering/fan-in/fan-out/rapid-pass-through/round-tripping/dormant-to-burst/
transaction-velocity (all scoreable against `financial_typologies.csv` and
`financial_anomaly_labels.csv`), CDR surge/burner-handset signature (vs
`cdr_anomaly_labels.csv`), cross-jurisdiction network, repeat offender, device sharing.
Every detector returns `detector_name, severity, confidence, entities, evidence,
explanation, case_ids, timestamps`.

### 6.5 Kingpin & risk engine
Composite score (defaults, tunable): 25% betweenness, 20% PageRank, 15% financial
control, 15% communication control, 10% brokerage, 10% cross-domain influence, 5%
disruption impact. Score against `roles.csv` (`true_role`) and each case's
`solutions/<CASE_ID>.json` `key_entities`/`bridge_entities` using Precision@1,
Precision@3, Recall@3, MRR, MAP. Output `KINGPIN_SCORE, CONFIDENCE, RANK, EVIDENCE,
EXPLANATION` — language: "Strong structural leadership candidate," never "Criminal."

### 6.6 Link prediction
Adamic-Adar, Jaccard, Preferential Attachment, Resource Allocation, enhanced with
shared location/device/vehicle/financial signals. Score against
`link_prediction_benchmark.csv` (`label`, `split`) with Precision@K/Recall@K/AUC.

### 6.7 Cross-case / cross-jurisdiction
Detect shared person/phone/vehicle/account/company/address/device/MO across cases.
Validate against `true_relationships.csv` and per-case `solutions/*.json`
`important_relationships`.

### 6.8 Women Safety Intelligence
Repeat-offender/escalation/hotspot/corridor analysis driven by
`women_safety_case_flags.csv` and `women_safety_corridors.csv` (`risk_score`,
`incident_count`). Human-review only, no autonomous action.

### 6.9 Evidence integrity
SHA-256 + previous-hash chain per `evidence_hash_chain.csv`
(`content_sha256, previous_hash, block_hash`); Merkle root per case from
`merkle_roots.csv`. Tamper-detection endpoint scored against
`evidence_verification_benchmark.csv` (`is_tampered`, `expected_verification_result`).
State plainly this does not itself guarantee legal admissibility.

### 6.10 Geospatial
Leaflet map using `locations.csv` (lat/long), `cctv_anpr_events.csv` for
movement/sightings, `women_safety_corridors.csv` for corridor/hotspot layers.
Distinguish persistent vs. emerging hotspots.

### 6.11 Disruption simulation
Investigator selects a node → recompute graph without it → report impact score,
affected nodes/edges, communities separated, financial/communication disruption.
Label clearly **SIMULATION ONLY**; no operational apprehension guidance.

### 6.12 AI Copilot
Pipeline: question → intent detection → tool selection → Postgres/Neo4j query →
analytics → structured findings → evidence validation → Gemini → grounded response.
Must run entirely on the deterministic fallback (Section 0.6) when Gemini is
unavailable. Every answer includes `Finding, Confidence, Evidence, Source, Case ID`,
each evidence item clickable back to the source record.

### 6.13 360° suspect dossier & timeline
Per person: identity/aliases, risk, kingpin score, cases, phones/SIMs/IMEIs, vehicles,
accounts, companies, locations, associates, communities, financial flows,
communication graph, timeline (built from `timelines.csv` /
`unified_investigation_timeline.csv`), anomalies, detected patterns, evidence,
cross-case links, and a "why flagged" evidence list.

### 6.14 Report generation
Per-case PDF: case info, executive summary, key candidates, network graph, risk scores,
financial/CDR analysis, timeline, geospatial findings, detected patterns, evidence
references, AI summary — clearly separating **system-generated analysis** from
**investigator conclusions**.

---

## 7. Frontend — network screen is the priority screen

Visual/interaction baseline = Thxrun (Section 3). The graph is the primary
investigative workspace, never a static picture: node/edge selection, expand-on-click,
double-click to expand neighbors, right-click context menu (Expand / Shortest Path /
Find Connections / View Evidence / View Timeline / Open Dossier), search across
Person/Phone/Vehicle/Account/Case/Company, filters (type/risk/case/district/
relationship/date/community), visual encoding by entity-type icon + risk/community
color (never color-only). Default render = selected node + 1-hop neighbors, with
explicit 2-hop/3-hop expansion — never render thousands of nodes at once.

Overall layout: dark, high-density, professional command-center aesthetic (per Section
34 concepts: top bar with global search/alerts/status; left sidebar with Command
Center/Cases/FIR Intelligence/Network Analysis/Financial/CDR/Geospatial/Women
Safety/Anomalies/Dossiers/AI Copilot/Evidence/Reports/Audit; center = live network +
active threats + risk overview; right = alerts/AI insights/selected entity). Avoid
neon, unneeded 3D, oversized KPI cards.

FIR screen: split view, left = document/`documents/<CASE_ID>/FIR_*.txt`, right =
extracted entities/relationships/classification/confidence/timeline with
Approve/Reject/Edit/Create-Graph-Links actions writing corrections back to Postgres.

---

## 8. Security / RBAC

Roles: `ADMIN, INVESTIGATING_OFFICER, INTELLIGENCE_ANALYST, AUDITOR`. JWT auth,
Argon2/bcrypt hashing, PII masking, per-endpoint authorization, rate limiting, audit
logs, session management, financial-data access controls.

---

## 9. Evaluation harness (`evaluation/`) — build this, it's the accuracy proof

A separate module/service that is the **only** code allowed to read
`dataset/ground_truth/`. For each metric below, join the system's live output
(from Postgres/Neo4j) against the named ground-truth file and report per-case +
aggregate — never collapse to one number only.

### 9.1 Metrics by module
- **Entity resolution:** vs `er_benchmark_pairs.csv` → precision, recall, F1, false-merge rate
- **NER extraction:** vs `ner_spans.csv` → span-level precision/recall/F1
- **Crime classification:** vs `crime_classification_benchmark.csv` (respect its `split`) → accuracy, precision, recall, F1, confusion matrix
- **Kingpin/role identification:** vs `roles.csv` + `solutions/*.json key_entities/bridge_entities` → Precision@1, Precision@3, Recall@3, MRR, MAP
- **Link prediction:** vs `link_prediction_benchmark.csv` (respect its `split`) → Precision@K, Recall@K, AUC
- **Anomaly detection (CDR):** vs `cdr_anomaly_labels.csv` → precision, recall, F1, false-positive rate
- **Anomaly detection (financial):** vs `financial_anomaly_labels.csv` and `financial_typologies.csv` → precision, recall, F1, false-positive rate, per-typology breakdown
- **Burner device detection:** vs `device_burner_flags.csv` → precision/recall
- **CCTV/ANPR resolution:** vs `cctv_person_resolution.csv` → accuracy
- **Network/community detection:** vs `networks.csv` + `solutions/*.json true_network` → overlap (Jaccard/NMI)
- **Relationship extraction:** vs `true_relationships.csv` → precision/recall/F1
- **Evidence integrity/tamper detection:** vs `evidence_verification_benchmark.csv` → accuracy, per `tamper_type`
- **OCR:** vs `ocr_ground_truth.csv` → character/word error rate
- **Timeline ordering:** vs `timelines.csv`/`unified_investigation_timeline.csv` → Kendall-tau or ordering accuracy
- **False-positive control:** vs `known_innocent_entities.csv` and `false_positive_eval.csv` → confirm innocents aren't flagged HIGH, confirm `expected_system_behavior` is met

### 9.2 Splits
Always evaluate on `test_case_ids.txt` for headline numbers; use `train_case_ids.txt`
for any fitting/threshold-tuning and `validation_case_ids.txt` for model selection.
Never tune against `test_case_ids.txt`.

### 9.3 Ablation study
Run the 7 configurations already defined in `ablation_protocol.json` (e.g. PageRank-only
→ full ensemble) and report whether the full model measurably beats simpler baselines
on the kingpin/network metrics above — do not assert this, show the numbers.

### 9.4 Reporting
Every accuracy claim anywhere in the UI, README, or generated PDF report must trace to
a number this harness produced this run. If a module has no corresponding ground-truth
file in Section 2.3, its README section must say "not independently benchmarked" rather
than quote a number.

### 9.5 Solve mode — maximizing accuracy on these exact 100 cases

Two different goals need two different modes. Don't conflate them:

- **Investigator app (Sections 5–8):** must generalize to *new* cases an investigator
  uploads later, so it never touches `ground_truth/` at runtime (Section 0 rule 4 still
  applies unchanged).
- **Solve mode (this section):** a separate, offline, developer-facing loop whose only
  goal is to get the system's output as close as possible to `solutions/<CASE_ID>.json`
  for these specific 100 cases. Since these 100 cases *are* the target — not a proxy for
  some future unseen case — it is legitimate here to use ALL case IDs (train + val +
  test) and the full `ground_truth/` folder as a tuning oracle. This mode never ships in
  the investigator app; it only produces the calibrated thresholds/weights that the app
  then uses.

**Define a solve score per case**, e.g.:
```
network_overlap   = Jaccard(system_predicted_network, solutions[case].true_network)
key_entity_hit    = key_entities found in system's top-K kingpin ranking
bridge_hit        = bridge_entities correctly flagged as bridges/articulation points
false_lead_reject = false_leads correctly kept at LOW/REVIEW confidence, not HIGH
relationship_f1   = F1 of important_relationships vs system's extracted relationships
SOLVE_SCORE(case) = weighted combination of the above (weights are a judgment call —
                     document whatever you pick)
```
A case counts as **"solved"** once it clears a threshold you set and document (e.g.
network_overlap ≥ 0.9 AND all key_entities in top-3 AND no false_lead promoted to HIGH).
Report solved/100 broken down by `difficulty` (Basic/Intermediate/Advanced/Expert) and by
`topology` (`A_hierarchical` … `J_decoy_heavy`) from `cases.csv` — don't average difficulty
tiers together, since Expert/`J_decoy_heavy`/`G_hidden_bridge` cases are supposed to be
harder and a single blended number hides that.

**Iterative tuning loop** (run this repeatedly, it's the actual mechanism for improving
the solve rate — not a one-shot build):
```
1. Run the full pipeline (Sections 5–6) over all 100 cases → predictions
2. Score every case against solutions/*.json (9.5 formula above)
3. Bucket failures: which detector/module missed which case, and how
     (missed bridge entity? false lead promoted to HIGH? wrong topology assumption?
      entity-resolution false merge/split? kingpin weights favoring wrong signal?)
4. Adjust ONE thing at a time and note why:
     - entity-resolution match thresholds (Section 6.2)
     - kingpin composite-score weights (Section 6.5) — the 25/20/15/15/10/10/5 split is
       a starting point, not fixed; re-derive it by fitting against roles.csv + solutions
     - detector thresholds (Section 6.4) per financial/CDR anomaly type
     - link-prediction score cutoffs (Section 6.6)
5. Re-run step 1–2. Keep the change only if aggregate + per-tier solve rate improves
   without regressing false-positive control (known_innocent_entities.csv,
   false_positive_eval.csv must still pass — don't trade false-positive safety for
   solve rate)
6. Repeat until solve rate plateaus or you've covered the ablation configs in 9.3
```
This is legitimate calibration on a fixed known dataset (like tuning hyperparameters on
your own labeled data), not cheating — the ground-truth separation rule in Section 0 is
about the *runtime app* never seeing answers for a real, unsolved investigation, not
about refusing to learn from labels you already possess for this specific dataset. Keep
solve-mode code in its own `evaluation/solver/` directory, clearly separate from the
app's production ingestion/analytics code, so it's obvious this calibration step never
ships as part of the investigator-facing product.

**Be upfront about the ceiling:** even after tuning, expect Basic/Intermediate cases to
approach 100% and Expert/decoy-heavy/hidden-bridge cases to land lower — that gap is
diagnostic information (it tells you which detector needs work), not a bug to suppress.
Report it, don't hide it.

---

## 10. Development phases (build in this order; test against the real dataset after each)

1. Infra: React + FastAPI + Postgres + Neo4j + Docker, all boot successfully
2. Auth + RBAC
3. Case management (backed by `cases.csv`)
4. Ingestion: FIR/CDR/bank/CCTV/vehicle/phone/device loaders (Section 6.1)
5. NLP/OCR (Section 6.1, scored later by `evaluation/`)
6. Entity resolution (Section 6.2)
7. Neo4j graph (Section 6.3, seeded via `import.cypher`)
8. Thxrun-style interactive network UI (Section 7)
9. Detection engine (Section 6.4)
10. Financial + CDR analytics
11. Anomaly engine
12. Kingpin + risk engine (Section 6.5)
13. Cross-case/cross-jurisdiction (Section 6.7)
14. Geospatial (Section 6.10)
15. Women Safety (Section 6.8)
16. Disruption simulation (Section 6.11)
17. AI Copilot + offline fallback (Section 6.12)
18. Evidence ledger (Section 6.9)
19. Reports (Section 6.14)
20. **Evaluation harness + ablation** (Section 9) — run against `test_case_ids.txt`, publish real numbers
21. Final UI polish

---

## 11. Deliverables

Full source (frontend/backend), Postgres schema + migrations, Neo4j schema/loader
extending `import.cypher`, NLP/entity-resolution/detection/financial/CDR/anomaly/
kingpin/risk/geospatial/Women-Safety/disruption/Copilot/evidence-ledger/report modules,
`evaluation/` harness with real benchmark output, Docker Compose, tests, README, API
docs, architecture doc, this feature-to-repository mapping, detector docs, risk/kingpin
formula docs, entity-resolution methodology, evaluation methodology + actual benchmark
results + actual ablation results, known limitations, security model, demo script.

## 12. Final priority order

Accuracy → Evidence → Explainability → Entity resolution → Graph intelligence →
Investigator workflow → Security → Performance → UI/UX → Visual effects. Never trade
accuracy for visual polish.
