# Synthetic Criminal Network Investigation Dataset

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
- Cases: 100 (Basic/Intermediate/Advanced/Expert ≈ {'Basic': 20, 'Intermediate': 30, 'Advanced': 30, 'Expert': 20})
- Persons: 1000, Organizations: 150, Vehicles: 300,
  Phones: 1200, Accounts: 800, Locations: 300
- Seed: 2026 (deterministic — same seed reproduces the same dataset)

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


## Gap-closure layer (`augment.py`)
Run after `export.py`. Adds, without modifying any base file:
- **Devices**: `evidence/sim_cards.csv`, `evidence/devices.csv`, `evidence/phone_sim_imei_device.csv`,
  `ground_truth/device_burner_flags.csv`
- **CCTV/ANPR**: `evidence/cctv_cameras.csv`, `evidence/cctv_anpr_events.csv`,
  `ground_truth/cctv_person_resolution.csv`
- **Financial typologies**: `evidence/transactions_typology.csv`, `ground_truth/financial_typologies.csv`,
  `ground_truth/financial_anomaly_labels.csv`
- **NER**: `ground_truth/ner_spans.csv`
- **Crime classification benchmark**: `ground_truth/crime_classification_benchmark.csv`
- **Entity resolution benchmark**: `ground_truth/er_benchmark_pairs.csv`
- **CDR anomaly labels**: `ground_truth/cdr_anomaly_labels.csv`
- **Link prediction benchmark**: `ground_truth/link_prediction_benchmark.csv`
- **Women Safety Intelligence**: `ground_truth/women_safety_case_flags.csv`, `ground_truth/women_safety_corridors.csv`
- **Known innocent entities**: `ground_truth/known_innocent_entities.csv`
- **Unified investigation timeline**: `ground_truth/unified_investigation_timeline.csv`
- **Evidence integrity**: `evidence/evidence_metadata.csv`, `evidence/evidence_hash_chain.csv`
  (SHA-256, previous-hash chain), `ground_truth/merkle_roots.csv`,
  `ground_truth/evidence_verification_benchmark.csv`
- **OCR / PDF**: `evidence/documents_pdf/`, `evidence/scanned_images/`, `ground_truth/ocr_ground_truth.csv`
- **Ablation protocol**: `ground_truth/ablation_protocol.json`
- **False-positive evaluation**: `ground_truth/false_positive_eval.csv`

See `GAP_ANALYSIS_STATUS.md` for the full before/after table.

## Regenerating (full pipeline)
```
python3 generate_dataset.py
python3 export.py
python3 augment.py
```
