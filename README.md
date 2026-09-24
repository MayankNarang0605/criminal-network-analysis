<div align="center">

# 🔍 CrimeNet — AI-Powered Criminal Network Analysis System

<img src="https://img.shields.io/badge/Status-Active%20Development-brightgreen?style=for-the-badge" />
<img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python" />
<img src="https://img.shields.io/badge/React-TypeScript-61DAFB?style=for-the-badge&logo=react" />
<img src="https://img.shields.io/badge/Neo4j-Graph%20DB-008CC1?style=for-the-badge&logo=neo4j" />
<img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker" />
<img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />

**A graph-centric, evidence-grounded investigative intelligence platform built for law enforcement — not a dashboard, a command center.**

[Features](#-features) · [Architecture](#-architecture) · [Tech Stack](#-tech-stack) · [Dataset](#-dataset) · [Quick Start](#-quick-start) · [Evaluation](#-evaluation-harness) · [Security](#-security--rbac)

</div>

---

## 🚨 Problem Statement

Modern criminal investigations are drowning in data. A single case can span **thousands of phone call records, hundreds of financial transactions, multiple FIRs, CCTV footage, vehicle movements, and cross-jurisdictional leads** — all scattered across disconnected silos. Investigators face:

| Challenge | Impact |
|-----------|--------|
| **Fragmented evidence** — FIRs, CDRs, bank records, CCTV events in separate systems | Critical connections missed; investigations stall |
| **Hidden network structure** — criminal organizations deliberately obscure leadership and communication chains | Kingpins and bridge entities go undetected |
| **Entity ambiguity** — aliases, number changes, borrowed vehicles, dummy companies | Suspects slip through the cracks due to name/ID mismatches |
| **Financial obfuscation** — hawala, layering, smurfing, round-tripping, dormant-to-burst accounts | Money flow and control remain invisible |
| **Scale** — 100s of active cases, 1000s of persons, simultaneous cross-case networks | No analyst can manually correlate at this volume |
| **Evidence integrity** — risk of tampering in digital records before court admission | Chain of custody breaks down without cryptographic verification |
| **No objective accuracy metric** — current tools give outputs with no way to measure how right they are | Investigators can't trust or tune the system |

> ⚠️ **This is a decision-support prototype, not an accusation engine.** Every finding is framed as a *lead requiring investigator review* — never as a verdict.

---

## 💡 Solution

**CrimeNet** is a full-stack investigative intelligence platform that:

1. **Ingests all evidence modalities** — structured CSVs, unstructured FIR narratives, witness statements, PDFs, scanned images — into a unified, cryptographically-hashed evidence store
2. **Resolves entities** with fuzzy matching across 1,000+ persons, aliases, phone numbers, and vehicle registrations — scored against a ground-truth benchmark
3. **Builds a live Neo4j knowledge graph** connecting every person, phone, account, vehicle, location, and case through evidence-backed relationships
4. **Runs 23 detection engines** across CDR, financial, CCTV, and behavioral signals to surface structured criminal patterns
5. **Identifies kingpins and bridge entities** using a composite graph-intelligence score (betweenness + PageRank + financial control + communication dominance)
6. **Provides an interactive investigation workspace** — network graph, geospatial map, 360° suspect dossier, and a timeline — all evidence-grounded
7. **Explains every finding** through an AI Copilot (Gemini-powered, with a full deterministic offline fallback) that cites the specific evidence record behind every claim
8. **Measures its own accuracy** against a sealed ground-truth benchmark and reports real, per-case, per-difficulty-tier numbers — no fabricated metrics

---

## ✨ Features

### 🗂️ Data Ingestion & NLP
- Multi-modal ingestion: CSV, FIR `.txt`, witness statements, PDF documents, scanned images (OCR via Tesseract/EasyOCR)
- spaCy NER pipeline for Indian-context entity extraction (persons, organizations, locations, phone numbers, vehicle registrations)
- Every ingested record carries `content_hash`, `provenance`, and `ingestion_timestamp`

### 🔗 Entity Resolution
- Indian name/alias normalization (`Mohd. / Mohammed / Mohammad / Md`)
- Phone number normalization (`+91 98765 43210` → canonical form)
- Vehicle registration standardization (`HR26AB1234` variants)
- RapidFuzz (Levenshtein / Jaro-Winkler) + phonetic matching + contextual scoring
- Confidence-bucketed output: `HIGH / REVIEW / LOW` — LOW matches never auto-merged
- Scored against `er_benchmark_pairs.csv` → Precision / Recall / F1 / False-Merge Rate

### 🌐 Neo4j Knowledge Graph
**17 node types:** `Person · Alias · Case · Phone · SIM · IMEI · Device · Vehicle · BankAccount · Organization · Location · CCTV · PoliceStation · Crime · Transaction · Evidence · UPI`

**20+ relationship types** including `CALLED · TRANSFERRED_TO · SEEN_AT · SHARED_DEVICE · PART_OF_NETWORK` — each carrying `confidence, source, timestamp, case_id, evidence_id`

### 🔍 Detection Engine (23 Detectors)

**CDR Intelligence**
- Frequent-caller spike detection
- Burner SIM/IMEI multi-swap detection
- CDR surge / burner-handset signature

**Financial Intelligence**
- Structuring (smurfing), layering, fan-in / fan-out
- Rapid pass-through, round-tripping
- Dormant-to-burst account activation
- Transaction velocity anomalies
- Hawala / mule-account syndicate detection

**Network Intelligence**
- Cross-case suspect overlap
- Vehicle convoy detection (CCTV/ANPR co-location)
- Crime-scene co-location clusters
- Shell company / dummy-address detection
- Cross-jurisdiction network bridges
- Repeat offender escalation
- Device sharing groups

### 👑 Kingpin & Risk Engine
Composite score with tunable weights:

| Signal | Default Weight |
|--------|---------------|
| Betweenness centrality | 25% |
| PageRank | 20% |
| Financial control | 15% |
| Communication control | 15% |
| Brokerage (structural holes) | 10% |
| Cross-domain influence | 10% |
| Disruption impact | 5% |

Output language: *"Strong structural leadership candidate"* — never *"criminal"*

### 🗺️ Geospatial Intelligence
- Interactive Leaflet map with real lat/long from `locations.csv`
- CCTV/ANPR movement trails and co-location events
- Women Safety corridors and trafficking hotspot layers (risk-scored)
- Persistent vs. emerging hotspot distinction

### 👤 360° Suspect Dossier
Per-person view: identity + aliases · risk score · all cases · phones/SIMs/IMEIs/devices · vehicles · bank accounts · organizations · known locations · social graph · financial flows · communication graph · full timeline · anomaly flags · "why flagged" evidence list · cross-case links

### 🤖 AI Copilot
- **Online mode:** Gemini 1.5 Pro with evidence-grounded prompting
- **Offline mode:** Deterministic fallback — full analytics rendered as plain evidence-backed text (no API key required)
- Every answer includes: `Finding · Confidence · Evidence · Source · Case ID` — each evidence item links back to the source record
- Pipeline: `Question → Intent → Tool Selection → DB Query → Analytics → Evidence Validation → LLM → Grounded Response`

### 🔐 Evidence Integrity Ledger
- SHA-256 content hashing with previous-hash chain (blockchain-style per-case ledger)
- Merkle root verification per case
- Tamper-detection endpoint scored against `evidence_verification_benchmark.csv`

### 💥 Disruption Simulation
Select any node → recompute graph without it → report impact score, affected nodes/edges, communities separated, financial/communication disruption. Clearly labelled **SIMULATION ONLY**.

### 📊 Evaluation Harness
Separate offline module — the **only** code allowed to read ground truth — that scores every module against sealed benchmark files and reports per-case, per-difficulty, per-topology accuracy numbers. See [Evaluation](#-evaluation-harness).

### 📄 Report Generation
Per-case PDF: case info · executive summary · key candidates · network graph export · risk scores · financial/CDR analysis · geospatial findings · timeline · detected patterns · evidence references · AI summary — clearly separating system-generated analysis from investigator conclusions.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND  (React + TypeScript + Vite)        │
│  Command Center Layout · Network Graph (Cytoscape.js) · Leaflet Map │
│  Dossier · Timeline · AI Copilot · Evidence Ledger · Reports        │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ REST / WebSocket
┌───────────────────────────▼─────────────────────────────────────────┐
│                       BACKEND  (FastAPI + Python)                   │
│                                                                     │
│  Auth/RBAC  ·  Ingest  ·  NLP/NER  ·  Entity Resolution           │
│  Detection Engine (23 detectors)  ·  Kingpin/Risk Engine            │
│  AI Copilot  ·  Geospatial  ·  Reports  ·  Evidence Ledger         │
└────────────┬───────────────────────────┬────────────────────────────┘
             │                          │
┌────────────▼──────────┐  ┌────────────▼──────────────────────────────┐
│   PostgreSQL           │  │              Neo4j                        │
│  (System of record)   │  │  (Relationship intelligence graph)        │
│  All evidence/*.csv   │  │  Seeded from neo4j/*.csv + import.cypher  │
│  tables verbatim      │  │  Extended by ingestion pipeline            │
└───────────────────────┘  └───────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼──────────────────────────────┐
│                    EVALUATION HARNESS  (offline only)                │
│  Reads ground_truth/  ·  Scores all modules  ·  Reports real numbers │
└──────────────────────────────────────────────────────────────────────┘
```

### Core Pipeline

```
evidence/*.csv + documents/  ──►  OCR (scanned_images/, documents_pdf/)
       │                                    │
       ▼                                    ▼
  Structured loaders                  Text extraction
       │                                    │
       └───────────────► NER (spaCy) ◄──────┘
                              │
                              ▼
                  Entity normalization
                              │
                              ▼
              Entity resolution (RapidFuzz + contextual)
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
            PostgreSQL                   Neo4j
                 │                         │
                 └────────────┬────────────┘
                              ▼
                     Detection engine (23 detectors)
                              ▼
                      Anomaly engine
                              ▼
              Kingpin / risk engine
                              ▼
        Cross-case intelligence
                              ▼
     Geospatial intelligence
                              ▼
              Disruption simulation
                              ▼
      AI Copilot (Gemini + deterministic fallback)
                              ▼
             Evidence-grounded report (PDF)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui |
| **State & Data** | TanStack Query + React Router |
| **Graph Viz** | Cytoscape.js |
| **Map** | Leaflet |
| **Charts** | Recharts |
| **Backend** | Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy + Alembic |
| **Primary DB** | PostgreSQL 16 |
| **Graph DB** | Neo4j 5 |
| **NLP** | spaCy + RapidFuzz |
| **ML** | scikit-learn + NumPy + Pandas |
| **OCR** | Tesseract + EasyOCR |
| **LLM** | Gemini 1.5 Pro (swappable abstraction layer; fully disable-able) |
| **Security** | JWT + Argon2/bcrypt + RBAC + PII masking + audit logs |
| **Deployment** | Docker + Docker Compose |

---

## 📦 Dataset

> **Synthetic, Indian-context, deterministic (seeded) — 100 cases**

| Entity Type | Count |
|-------------|-------|
| Cases | 100 |
| Persons | 1,000 |
| Organizations | 150 |
| Vehicles | 300 |
| Phones | 1,200 |
| Bank Accounts | 800 |
| Locations | 300 |

**Difficulty distribution:** Basic (20) · Intermediate (30) · Advanced (30) · Expert (20)

**Evidence modalities:**
- Structured: `persons.csv`, `cdr.csv`, `transactions.csv`, `fir.csv`, `cctv_anpr_events.csv`, `bank_accounts.csv`, `vehicles.csv`, `phones.csv`, `sim_cards.csv`, `devices.csv`, `organizations.csv`, `locations.csv`, `relationships.csv`, `evidence_hash_chain.csv`, and more
- Unstructured: FIR narratives (`.txt`), witness statements, PDF documents, scanned images
- Graph: `dataset/neo4j/import.cypher` — ready-made bulk-import script

**Sealed ground truth** (used only by the evaluation harness, never by the running app):
`networks.csv` · `roles.csv` · `true_relationships.csv` · `solutions/<CASE_ID>.json` · anomaly labels · financial typologies · device burner flags · NER spans · entity resolution benchmark · link prediction benchmark · evidence integrity benchmark · OCR ground truth

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### 1. Clone & Setup

```bash
git clone https://github.com/MayankNarang0605/criminal-network-analysis.git
cd criminal-network-analysis
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env — set your GEMINI_API_KEY (optional; system works fully without it)
# Set JWT_SECRET_KEY to a random 32+ character string
```

### 3. Boot the Stack

```bash
docker compose up --build
```

This starts:
- **Frontend** → http://localhost:5173
- **Backend API** → http://localhost:8000
- **PostgreSQL** → localhost:5432
- **Neo4j Browser** → http://localhost:7474

### 4. Seed the Database

```bash
# The ingestion pipeline loads all evidence/*.csv into PostgreSQL
# and seeds Neo4j from dataset/neo4j/import.cypher automatically on first boot.
# To manually trigger re-ingestion:
docker compose exec backend python -m services.ingest
```

### 5. Access the App

| URL | Description |
|-----|-------------|
| http://localhost:5173 | Investigator command center |
| http://localhost:8000/docs | FastAPI interactive API docs |
| http://localhost:7474 | Neo4j Browser (user: `neo4j`, pass: from `.env`) |

---

## 🧪 Evaluation Harness

The `evaluation/` module is the **only** code allowed to read `dataset/ground_truth/`. It scores every analytical module against sealed benchmark files and reports real numbers.

```bash
# Run the full evaluation suite against test_case_ids.txt
docker compose exec backend python -m evaluation.harness --split test

# Run solve-mode scoring (calibration only — never ships in the app)
docker compose exec backend python -m evaluation.solver
```

### Metrics reported

| Module | Ground-truth file | Metric |
|--------|------------------|--------|
| Entity resolution | `er_benchmark_pairs.csv` | Precision / Recall / F1 / False-Merge Rate |
| NER extraction | `ner_spans.csv` | Span-level P / R / F1 |
| Crime classification | `crime_classification_benchmark.csv` | Accuracy / F1 / Confusion Matrix |
| Kingpin identification | `roles.csv` + `solutions/*.json` | Precision@1 / Precision@3 / MRR / MAP |
| Link prediction | `link_prediction_benchmark.csv` | Precision@K / Recall@K / AUC |
| CDR anomaly detection | `cdr_anomaly_labels.csv` | P / R / F1 / FPR |
| Financial anomaly detection | `financial_anomaly_labels.csv` + `financial_typologies.csv` | P / R / F1 / per-typology breakdown |
| Burner device detection | `device_burner_flags.csv` | Precision / Recall |
| Network/community detection | `networks.csv` + `solutions/*.json` | Jaccard / NMI |
| Relationship extraction | `true_relationships.csv` | P / R / F1 |
| Evidence integrity | `evidence_verification_benchmark.csv` | Accuracy / per tamper-type |
| OCR | `ocr_ground_truth.csv` | Character Error Rate / Word Error Rate |
| False-positive control | `known_innocent_entities.csv` | Innocent entities not flagged HIGH |

Results are reported **per-case and per-difficulty-tier** (Basic / Intermediate / Advanced / Expert) — never as a single blended number.

> All accuracy claims in the UI, generated reports, and this README trace to numbers actually produced by this harness. Modules without a corresponding ground-truth file are marked *"not independently benchmarked."*

---

## 🔐 Security & RBAC

| Role | Access |
|------|--------|
| `ADMIN` | Full system access, user management, audit log review |
| `INVESTIGATING_OFFICER` | Case access, dossier, graph, CDR/financial data |
| `INTELLIGENCE_ANALYST` | Read-only analytics, cross-case intelligence, reports |
| `AUDITOR` | Audit logs, evidence integrity verification only |

- JWT authentication with configurable expiry
- Argon2/bcrypt password hashing
- PII masking on sensitive fields for lower-privilege roles
- Per-endpoint authorization
- Rate limiting
- Immutable audit logs

---

## 🗂️ Project Structure

```
criminal-network-analysis/
├── backend/                    # FastAPI application
│   ├── routers/               # API endpoints (auth, cases, graph, persons,
│   │                          #   analytics, copilot, evidence, geospatial,
│   │                          #   reports, nlp, ingest, health)
│   ├── services/              # Business logic & pipeline modules
│   ├── models/                # SQLAlchemy + Pydantic models
│   ├── main.py                # App entry point
│   ├── security.py            # JWT, RBAC, PII masking
│   ├── database.py            # PostgreSQL + Neo4j connection management
│   └── requirements.txt
├── frontend/                  # React + TypeScript + Vite
│   └── src/
│       ├── components/        # Network graph, dossier, timeline, copilot,
│       │                      #   geospatial, financial, CDR, evidence, reports
│       ├── App.tsx            # Routing & layout
│       └── index.css          # Design system
├── dataset/                   # Synthetic dataset (not tracked in git — see below)
│   ├── evidence/              # All CSVs + FIR documents the app can read
│   ├── ground_truth/          # Sealed answer key — evaluation only
│   ├── neo4j/                 # Bulk-import files + import.cypher
│   └── metadata/
├── evaluation/                # Offline accuracy harness
│   ├── harness.py             # Main scorer
│   └── solver/                # Solve-mode calibration (never ships in app)
├── docker-compose.yml
├── .env.example
└── README.md
```

> **Note:** `dataset/` contains synthetic data files. The large SQLite cache (`crimenet.db`) and `ATLAS.zip` are excluded from the repository via `.gitignore`. Regenerate the dataset if needed:
> ```bash
> python generate_dataset.py   # base synthetic world (seeded)
> python export.py             # writes evidence/ + ground_truth/ + neo4j/
> python augment.py            # adds devices, CCTV/ANPR, typologies, OCR, hash-chain, benchmarks
> ```

---

## 🗺️ Development Phases

| Phase | Module | Status |
|-------|--------|--------|
| 1 | Infra: React + FastAPI + PostgreSQL + Neo4j + Docker | ✅ |
| 2 | Auth + RBAC | ✅ |
| 3 | Case management | ✅ |
| 4 | Data ingestion (FIR / CDR / bank / CCTV / vehicle / phone / device) | 🔄 |
| 5 | NLP / OCR pipeline | 🔄 |
| 6 | Entity resolution | 🔄 |
| 7 | Neo4j knowledge graph | 🔄 |
| 8 | Interactive network UI (Cytoscape.js) | 🔄 |
| 9 | Detection engine (23 detectors) | 🔄 |
| 10 | Financial + CDR analytics | 🔄 |
| 11 | Anomaly engine | 🔄 |
| 12 | Kingpin + risk engine | 🔄 |
| 13 | Cross-case / cross-jurisdiction | 📋 |
| 14 | Geospatial intelligence | 📋 |
| 15 | Women Safety module | 📋 |
| 16 | Disruption simulation | 📋 |
| 17 | AI Copilot + offline fallback | 📋 |
| 18 | Evidence integrity ledger | 📋 |
| 19 | Report generation (PDF) | 📋 |
| 20 | Evaluation harness + ablation study | 📋 |
| 21 | Final UI polish | 📋 |

✅ Done · 🔄 In Progress · 📋 Planned

---

## ⚖️ Design Principles

1. **Accuracy → Evidence → Explainability → Entity Resolution → Graph Intelligence → Investigator Workflow → Security → Performance → UI** — in that priority order
2. **The LLM is an explainer, never the source of truth.** Deterministic modules always run first; LLM only narrates findings they produce
3. **Every claim must cite evidence** — a `case_id`, `evidence_id`, `transaction_id`, or graph finding that exists in the dataset
4. **Ground-truth separation is sacred** — application code never reads `ground_truth/`; only the offline `evaluation/` harness does
5. **System works fully with the LLM off** — no degraded mode, full analytics rendered deterministically
6. **No fabricated metrics** — every accuracy number comes from actually running the evaluator

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built for the **Smart India Hackathon** challenge on AI-powered criminal network analysis.

*A decision-support tool for investigators — not an autonomous judgment system.*

</div>
