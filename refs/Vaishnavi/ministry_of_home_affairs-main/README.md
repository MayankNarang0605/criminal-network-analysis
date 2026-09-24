# AI-Powered Criminal Network Analysis System
**A Full-Stack Python Project Themed on Ministry of Home Affairs (MHA) Use Cases**

---

## 📌 Executive Summary
The **AI-Powered Criminal Network Analysis System** is a full-stack Python intelligence and investigation platform inspired by initiatives undertaken by India's **Ministry of Home Affairs (MHA)** and associated law enforcement bodies:
- **CCTNS (Crime and Criminal Tracking Network & Systems - NCRB)**: Digitisation and relational cross-linking of FIRs across 14,000+ police stations.
- **OCND (National Organised Crime Network Database - NIA & NATGRID)**: Centralised intelligence graph exposing cross-jurisdictional syndicate connections (shared phone numbers, mule accounts, vehicle plates).
- **I4C (Indian Cybercrime Coordination Centre)**: NLP-driven complaint triage, cyber fraud mule ring detection, and risk scoring.
- **SIMBA / Crime GPT**: Advanced suspect profiling, graph traversals, and multi-hop connection queries.

This system demonstrates how **multi-relational property graphs, network-science algorithms, natural language processing (NLP), and cryptographic audit logging** combine into a high-performance web application.

---

## 🚀 Key Functional Modules

### 1. Interactive Force-Directed Network Graph Explorer
- Real-time 60fps HTML5 Canvas physics simulation with zoom, pan, drag, and node pin controls.
- Distinct color-coded nodes for `Person` (Kingpin/Broker/Mule), `Case` (FIR), `Organization` (Front Company/Gang), `Location`, `Vehicle`, `FinancialAccount`, and `CommunicationRecord`.
- Directed relational edges with relation labels (`ASSOCIATE_OF`, `ACCUSED_IN`, `MEMBER_OF`, `TRANSFERRED_FUNDS`, `CONTACTED`, `OWNS_VEHICLE`).
- 1-Click **Community Gang Cluster Coloring** (Louvain Modularity).
- 1-Click **Shortest Path Route Highlighter** with glowing multi-hop chain traces.

### 2. FIR & Case Intake Studio (Real-Time NLP Workbench)
- Form intake for structured FIR metadata + free-text narrative.
- **Real-Time NLP Named Entity Recognition (NER)**: As investigators type or paste narratives, entities are highlighted with live badges (Suspect names & aliases `@ Bunty`, 10-digit Indian phone numbers, Vehicle registration plates, Bank accounts, IFSCs, UPI IDs, PAN cards, Aadhaar hashes).
- **AI Crime Category Classifier**: Automatically predicts IPC / Bharatiya Nyaya Sanhita (BNS) crime categories with confidence scoring.
- **3 One-Click Demonstration Presets**:
  1. *Mewat-Kolkata-Delhi Cyber Scam Syndicate*
  2. *Cross-Border Hawala & Zaveri Bullion Ring*
  3. *Interstate Luxury SUV Lifting Gang*

### 3. Key Players Leaderboard & Composite Risk Scoring
- **Centrality Metrics**: Degree Centrality, Betweenness Centrality (gatekeeper/broker detection), Closeness Centrality, and PageRank (kingpin identification).
- **Composite Risk Score (0–100)**: Combines network position, connected FIR severity, multi-state spread, and direct associate counts.
- **Explainable AI (XAI)**: Detailed breakdown card explaining why each suspect received their risk score.

### 4. Cross-Jurisdiction Syndicate Radar (OCND / NATGRID)
- Automatically detects and flags entities (suspects, burner phones, mule accounts, vehicles) that link multiple independent FIRs across different police stations and states.

### 5. AI / Graph-ML Link Prediction ("Missing Links")
- Discovers hidden or unrecorded criminal associates using topological proximity algorithms:
  - **Adamic-Adar Index**
  - **Jaccard Coefficient**
  - **Resource Allocation Index**
- Provides explainable evidence (e.g., *"Suspect A and Suspect B share 3 mutual associates and are co-located in Sector 62 Noida"*).

### 6. 360° Suspect Investigation Dossier & Timeline
- Complete suspect profile with aliases, operational role, associate hierarchy tree, linked assets, and a chronological forensic incident timeline.
- One-click formal intelligence dossier JSON/PDF report export.

### 7. Tamper-Evident SHA-256 Audit Trail
- Every search, dossier view, case upload, and export is recorded in an immutable ledger cryptographically chained using SHA-256 (`H(prev_hash + seq + timestamp + user + action + details)`).
- One-click **Cryptographic Verification** tool that validates the entire chain from Genesis block to ensure evidentiary integrity.

### 8. Role-Based Access Control (RBAC)
- Demonstration quick-switcher supporting 4 MHA roles:
  - `Investigating Officer`: Case intake, suspect profiling, search.
  - `Intelligence Analyst`: Graph analytics, link prediction, cluster analysis.
  - `Auditor`: Read-only audit log inspection and cryptographic validation.
  - `Admin`: Full system control and synthetic data re-seeding.

---

## 🛠️ Technology Stack

| Layer | Component | Description |
|---|---|---|
| **Backend** | Python (Starlette / ASGI + Uvicorn) | Async-first, high-throughput REST API with clean modular routing |
| **Graph Engine** | NetworkX + Custom Property Graph Engine | Multi-relational in-memory graph store with persistent JSON/SQLite syncing |
| **Relational Data** | SQLite + SQLAlchemy ORM | Users, Roles, FIR Cases, Entity Merges, and Audit Logs |
| **AI / NLP** | Rule & Pattern Extraction + Token Regex | Indian phone normalisation, PAN/Aadhaar hashing, Vehicle plate parsing, IPC/BNS classifier |
| **Graph ML** | Adamic-Adar, Jaccard, Louvain Modularity | Missing link prediction, community gang detection, centrality metrics |
| **Frontend** | Vanilla JS + HTML5 Canvas + Modern CSS | Ultra-premium Law Enforcement Dark Mode Command Dashboard (Zero npm dependencies required) |
| **Security** | JWT Tokens + PBKDF2-SHA256 + Hash-Chained Audit Trail | RBAC authorization, PII masking, cryptographic evidentiary integrity |

---

## 🏃 Quick Start Guide

### Prerequisites
- Python 3.10+ (Tested on Python 3.15)

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
python backend/tests/run_tests.py
```

### 3. Launch Application
```bash
python run.py
```
Open your browser and navigate to:
👉 **`http://127.0.0.1:8000`**

---

## 🧪 Demonstration & Viva Script

1. **Graph Exploration**:
   - Open `http://127.0.0.1:8000` to see the live Force-Directed Criminal Graph.
   - Click on **Mohammed Farhan** to view his risk score (Kingpin) and inspect his 1-hop / 2-hop neighborhood.
   - Click **"Color by Gang Cluster"** to see Louvain Community partition groups color-coded.
2. **FIR Case Intake & Real-Time NLP**:
   - Click on **"FIR & Case Intake"** in the sidebar.
   - Click the preset button **"💻 Mewat Cyber Scam"**.
   - Watch the real-time AI NLP badges extract suspects, phone numbers, vehicles, bank accounts, and classify the crime category as *Cyber Fraud & Phishing*.
   - Click **"Ingest & Link into Network Graph"** to see newly created nodes immediately linked in the graph.
3. **Cross-Jurisdiction Syndicate Radar**:
   - Click on **"Cross-Jurisdiction Radar"**.
   - Notice the multi-state alert for **Mohammed Farhan** linking FIRs across Haryana STF (Gurugram), Delhi Police Special Cell, and Kolkata CID.
4. **Missing Link Prediction**:
   - Click on **"Link Prediction"**.
   - Inspect AI-predicted hidden relationships with Adamic-Adar confidence scores and explainable evidence.
5. **Shortest Path Finder**:
   - In **"Key Players & Clusters"**, select *Suspect Alpha* and *Suspect Beta* in the path finder.
   - Click **"Find Shortest Path"** to trace the multi-hop relational chain and highlight it on the graph.
6. **Tamper-Evident Audit Trail**:
   - Click on **"Audit Trail & Integrity"**.
   - Click **"Run Cryptographic Verification"** to prove the SHA-256 blockchain-style hash chain is 100% intact.
   - Switch user role to **Compliance Auditor** or **Intelligence Analyst** to demonstrate RBAC scoping.

---

## ⚖️ Ethics & Data Minimisation Disclaimer
This software is an academic / hackathon prototype built exclusively with **synthetic, fictitious data** (generated via Faker and NetworkX scale-free models). No actual citizen or sensitive government data is used or stored.
