# AI-Powered Criminal Network Analysis System

**Smart India Hackathon · Blockchain & Cybersecurity**
Ministry of Home Affairs · National Crime Records Bureau · Women Safety Division

An investigative intelligence platform that ingests fragmented crime data (FIR
narratives, Call Detail Records, financial ledgers), resolves entities across
sources, builds the relationship graph, identifies who actually *commands* a
criminal network, detects laundering and communication typologies, and records
every access in a tamper-evident ledger.

---

## Run it

```powershell
.\run.ps1          # Windows
```

```bash
./run.sh           # Linux / macOS
```

Then open **http://localhost:8000/app** and sign in as `investigator` /
`invest123!`.

First start installs dependencies, ingests the corpus and runs the full
analytics pipeline. Total time is about 30 seconds; subsequent starts are
instant.

No Docker, database server, search cluster or message broker is required.

<details>
<summary>Other commands</summary>

```powershell
.\run.ps1 -Dev     # hot-reload dev mode (UI on :5173)
.\run.ps1 -Test    # run the 85-test suite
.\run.ps1 -Reset   # discard the database and re-ingest
```

```bash
docker build -t ncrb-cnas . && docker run -p 8000:8000 ncrb-cnas
```
</details>

---

## The central problem, and what this does about it

The problem statement asks the system to *"identify key individuals who play
influential roles within criminal networks."* Nearly every implementation
answers this with degree centrality or call volume.

**That answer is wrong, and provably so.** In a real syndicate the courier makes
the most calls and the mule moves the most money. The person in command talks to
three people and touches nothing. Rank by connection count and you arrest the
courier.

This system introduces an **insulation index**: for each actor, the fraction of
its neighbourhood that carries operational evidence (vehicles, seizures,
locations, physical presence) while the actor itself does not. Command shows up
as high reach combined with low operational contact. That signal is combined
with brokerage, elite adjacency, flow control, multi-domain span, and measured
network damage on removal into a single explainable score.

### Measured, not asserted

The corpus generator plants a **known hierarchy** — kingpin, lieutenants,
operatives, couriers, mules — then emits only the artefacts an investigator
would actually receive. Kingpins are deliberately given *low* degree and *low*
call volume; couriers are given high volume as decoys. The true roles are never
exposed to the analytics pipeline.

Result on the default 6-network corpus (`/api/v1/ml/evaluation`, visible in the
UI under **Model Evaluation** — deterministic with `PYTHONHASHSEED=0`):

| Method | MAP | Precision@3 |
|---|---|---|
| **Composite score (this system)** | **0.569** | **0.667** |
| Betweenness only | 0.321 | 0.333 |
| Eigenvector only | 0.154 | 0.333 |
| Degree centrality | 0.108 | 0.000 |
| PageRank only | 0.105 | 0.000 |
| Raw call volume | 0.066 | 0.000 |

The planted kingpin is recovered in the top 3 of their own network in **6 of 6
networks**, at rank 1 in 4, with mean reciprocal rank 1.0. Mean influence score
by true role separates down the hierarchy:

| True role | Count | Mean score |
|---|---|---|
| kingpin | 6 | **47.7** |
| courier | 5 | 23.9 |
| mule | 10 | 21.5 |
| lieutenant | 15 | 21.4 |
| operative | 30 | 17.8 |

Raw call volume scores 0.066 and picks no kingpin in its top 3. That is the
failure mode this system is built to avoid, demonstrated on the same data.

---

## What it does

**Multi-source ingestion.** FIR JSON, CDR CSV and bank ledgers are loaded,
parsed and fused. The pipeline is one synchronous pass and completes in ~9
seconds on the demo corpus, so a new CDR dump yields refreshed intelligence
immediately rather than queueing.

**Entity extraction tuned for Indian records.** Generic English NER fails on FIR
text: it misses Indian names, mangles 10-digit mobile numbers, and has never
seen an RTO plate or an IPC citation. This uses deterministic high-precision
extractors for the identifiers that drive investigations (mobile with +91/0
prefix handling, RTO plates validated against real state codes, bank accounts,
IFSC, PAN, Aadhaar, IMEI, crypto wallets, IPC/BNS sections, currency with
lakh/crore scaling) plus a corpus-seeded gazetteer and a morphological
Indian-name recogniser. **Every mention carries character offsets**, so the UI
highlights the exact text that justified each extraction.

**Entity resolution.** The same person appears as "Vikram Desai", "Shri Vikram
Desai", "V. Desai" and "VIKRAM DESAI." across stations, plus as a phone number
in a CDR and an account holder in a bank dump. Resolution is union-find over
hard identifiers (transitive) and blocked fuzzy name matching requiring
corroboration, with a phonetic key tuned for Indian transliteration variance
(Mohd/Mohammed, Shaikh/Sheikh, v/w). Every merge records the rule and score, so
a wrong link is reversible.

**Graph intelligence.** Weighted centrality, Louvain community detection
(modularity ~0.79 on the demo corpus), k-shortest weighted paths with per-hop
confidence, articulation-point detection, and link prediction ensembling
Adamic-Adar, Jaccard, preferential attachment and community co-membership. Each
predicted link lists the shared associates that justify it.

**Disruption planning.** `POST /graph/simulate-disruption` answers the question a
commander actually asks: if we arrest these people, what breaks? It reports
fragmentation, isolated actors, and the likely successor — because removing
leadership without preparing for succession produces temporary disruption only.
`GET /graph/optimal-disruption` greedily selects the highest-impact arrest set
for a given budget.

**Pattern detection mapped to real typologies.** Financial detectors implement
FATF/FIU-IND typologies — structuring below the ₹10 lakh CTR threshold, layering
chains, fan-out/fan-in mule networks, circular round-tripping, rapid
pass-through, dormant-then-burst. Communication detectors find command
topologies (hub-and-spoke with low inter-peer density), pre-offence call surges
anchored to FIR dates, tower co-location, and burner-handset signatures.
Anomaly detection uses median/MAD robust z-scores rather than mean/stdev,
because criminal data is skewed and a few extreme actors would otherwise mask
everyone else. Every finding names its typology and its recommended
investigative action.

**Explainable risk scoring.** Six weighted factors producing 0–100, with the
points contributed by each factor and the evidence behind it returned in the
API. There is no black-box model, deliberately: a gradient-boosted model might
score marginally better on a benchmark but would be unusable in an evidentiary
context where every adverse inference must be justifiable.

**Blockchain, applied honestly.** Case data is *not* put on a chain — that would
be a privacy catastrophe. What is chained is the **audit ledger**: an
append-only SHA-256 hash chain of who accessed which citizen's record, with
per-block Merkle commitments and inclusion proofs. `GET /audit/verify` reports
the exact block height where tampering occurred. `POST /audit/tamper-demo`
modifies a block, verifies detection, and restores it — so the guarantee is
demonstrable rather than asserted. This closes a real accountability gap: an
officer cannot quietly delete the record of an unauthorised lookup.

**Women Safety Division module.** The problem statement is owned by a specific
department, so generic network analysis leaves its mandate unaddressed. This adds
mandate-case isolation across IPC/BNS/POCSO/IT Act, cross-jurisdictional repeat
offender detection (the pattern no single police station can see), an offence
escalation ladder identifying the preventive-intervention window, trafficking
corridor inference, and a district hotspot index for resource allocation.

**Security.** PBKDF2-HMAC-SHA256 password hashing, stdlib HS256 JWT (no
third-party crypto dependency to audit), four-level RBAC enforced by dependency
injection, and role-based PII masking — investigators see full identifiers,
analysts and viewers see masked ones, satisfying purpose limitation under the
DPDP Act 2023.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  React + Cytoscape dashboard (Live Investigation: add case │ 
│  from browser, additive ingest, no file editing)             │
├──────────────────────────────────────────────────────────────┤
│  FastAPI · 51 routes · JWT + RBAC · audit interception        │
├────────┬─────────┬──────────┬──────────┬─────────┬──────────┤
│ Ingest │  NLP    │  Graph   │ Patterns │  Risk   │  Ledger  │
│  ETL   │ extract │ NetworkX │  FATF    │ scoring │ SHA-256  │
│        │ resolve │ Louvain  │  typol.  │ explain │  Merkle  │
├────────┴─────────┴──────────┴──────────┴─────────┴──────────┤
│  SQLite + FTS5 (BM25)  ·  single file  ·  zero external deps  │
└──────────────────────────────────────────────────────────────┘
```

**Why embedded rather than Neo4j + Postgres + Elasticsearch:** at the volumes an
investigating unit handles per case cluster (10³–10⁵ entities), in-process
NetworkX is faster than a Bolt round trip, and it removes the single largest
deployment obstacle in a police network. SQLite FTS5 uses BM25 — the same
ranking family as Elasticsearch. Every storage access sits behind an adapter
(`app/db.py`, `GraphEngine.load()`), so a production deployment can point at
server backends by configuration alone. This is an engineering decision, not a
shortcut: the demo boots in seconds on any laptop and cannot fail because a
container did not come up.

---

## Project layout

```
backend/app/
  db.py                  SQLite schema + storage adapter (+ incremental Live mode)
  config.py              settings, scoring weights
  nlp/
    normalize.py         Indian phone/plate/name/account canonicalisation
    extractor.py         hybrid entity + relation extraction with offsets
    resolver.py          union-find entity resolution
    ipc.py               IPC/BNS/POCSO/NDPS knowledge base
  graph/engine.py        centrality, Louvain, paths, link prediction,
                         insulation index, disruption simulation
  analytics/
    patterns.py          FATF financial + CDR behavioural + anomaly detectors
    evaluate.py          ground-truth evaluation vs naive baselines
  ml/risk.py             explainable six-factor risk scoring
  etl/
    generator.py         labelled synthetic corpus generator
    pipeline.py          end-to-end ingest → analytics orchestration
  blockchain/ledger.py   hash chain, Merkle proofs, tamper detection
  women_safety/service.py  division-specific analysis
  auth/security.py       PBKDF2, JWT, RBAC, PII masking
  search/engine.py       FTS5 BM25 + fuzzy fallback
   api/routes.py          REST surface (54 routes: + /data/case, /data/cdr/batch, /data/transactions/batch)
   main.py                app assembly, first-boot ingestion
tests/test_system.py     85 tests
frontend/src/            React dashboard (14 views incl. Live Investigation)
frontend/src/pages/LiveInvestigation.jsx  live investigation form (FIR/CDR/Ledger, preview extraction)
data/                    sample FIR / CDR / transaction + sample_case_template.json
```

---

## Demo walkthrough

Five minutes demo:

1. **Overview** — the consolidated picture. Point out that the top-ranked actor
   is not the highest-degree node.
2. **Model Evaluation** — lead with this. Composite MAP 0.569 against
   degree centrality's 0.108. This slide separates you from every other graph-analytics entry.
3. **Live Investigation** — paste narrative → **Preview Extraction** (yellow highlights on unseen text) → **Add FIR to Graph** → graph/risk/audit update in <3s (additive, no wipe). Prove entity resolution by using existing phone `9234567891` (Priya Nair) — merges.
4. **Key Actors** — open new actor, show six-factor attribution, *Recommend arrest set* → fragmentation + successor.
5. **Case Register** → open any FIR — narrative highlights + PII masking by role.
6. **Audit Ledger** → `admin` tamper demo → `BROKEN at 1` → `VERIFIED`.

---

## Testing

```powershell
.\run.ps1 -Test
```

85 tests: identifier extraction across Indian formats, evidence-span accuracy,
resolution merge and non-merge behaviour, graph analytics invariants, risk
factor summation, ledger tamper detection (content modification *and* block
deletion), Merkle proof round-trip, RBAC enforcement, FTS5 injection safety, and
API contract stability.

---

## Credentials

| Role | Username | Password | Access |
|---|---|---|---|
| Administrator | `admin` | `admin123!` | everything, including the tamper demo |
| Investigator | `investigator` | `invest123!` | unmasked PII, disruption simulation |
| Analyst | `analyst` | `analyst123!` | analysis, PII masked |
| Viewer | `viewer` | `viewer123!` | read-only, PII masked |
