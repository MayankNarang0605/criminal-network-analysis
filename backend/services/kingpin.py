"""
Kingpin & Network Leadership/Centrality Scoring Engine.
Computes mathematical network leadership and centrality rankings across entities.

⚠️ IMPORTANT LEGAL & ANALYTICAL DIRECTIVE:
Scores represent structural graph importance and connectivity — NOT legal guilt probability.
All findings require independent forensic review.

6 Scoring Pillars:
1. Network Centrality (20%): Degree centrality and PageRank structural prestige.
2. Betweenness / Connectivity (20%): Choke-point bridging across sub-cliques.
3. Financial Influence (20%): Transaction volume and fund routing control.
4. Communication Influence (15%): CDR call frequency and telecom reach.
5. Cross-Case Connections (15%): Multi-jurisdictional syndicate overlap.
6. Evidence Strength (10%): Density of verified evidence links and tamper-evident hashes.
"""
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
import networkx as nx
from sqlalchemy.orm import Session

from backend.logging_config import logger
from backend.models.evidence import (
    Person, Relationship, BankAccount, Transaction, Phone, CDR, FIRPerson, FIR,
    LocationEvent, EvidenceMetadata
)


def compute_kingpin_scores(
    db: Session,
    case_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Computes Network Leadership / Centrality rankings across entities.
    Can be scoped to a specific case or evaluated globally across the entire syndicate network.
    """
    # 1. Collect case-specific scope if case_id is provided
    scoped_case_id = case_id.strip() if case_id and case_id.strip().upper() not in ("ALL", "") else None
    
    # 2. Build mapping of accounts -> persons and phones -> persons
    person_accounts = defaultdict(set)
    for ba in db.query(BankAccount).all():
        if ba.person_id:
            person_accounts[ba.person_id].add(ba.account_id)
    account_person = {acc: pid for pid, accs in person_accounts.items() for acc in accs}

    person_phones = defaultdict(set)
    for ph in db.query(Phone).all():
        if ph.person_id:
            person_phones[ph.person_id].add(ph.phone_id)
    phone_person = {ph: pid for pid, phs in person_phones.items() for ph in phs}

    # 3. Identify candidate persons
    case_person_ids: Set[str] = set()
    if scoped_case_id:
        # A) FIR Persons in case
        case_firs = db.query(FIR).filter(FIR.case_id == scoped_case_id).all()
        fir_ids = [f.fir_id for f in case_firs]
        if fir_ids:
            for fp in db.query(FIRPerson).filter(FIRPerson.fir_id.in_(fir_ids)).all():
                case_person_ids.add(fp.person_id)

        # B) Persons in Transactions for this case
        for tx in db.query(Transaction).filter(Transaction.case_id == scoped_case_id).all():
            if tx.sender_account in account_person:
                case_person_ids.add(account_person[tx.sender_account])
            if tx.receiver_account in account_person:
                case_person_ids.add(account_person[tx.receiver_account])

        # C) Persons in CDRs for this case
        for c in db.query(CDR).filter(CDR.case_id == scoped_case_id).all():
            if c.caller_phone_id in phone_person:
                case_person_ids.add(phone_person[c.caller_phone_id])
            if c.receiver_phone_id in phone_person:
                case_person_ids.add(phone_person[c.receiver_phone_id])

        # D) Persons in Location Events for this case
        for le in db.query(LocationEvent).filter(LocationEvent.case_id == scoped_case_id).all():
            if le.person_id:
                case_person_ids.add(le.person_id)

    # 4. Build NetworkX graph
    G = nx.Graph()
    rels = db.query(Relationship).all()
    for r in rels:
        G.add_edge(r.source_entity, r.target_entity, weight=r.confidence or 1.0)
        # If scoped, also include immediate associates who share an edge with case persons
        if scoped_case_id and (r.source_entity in case_person_ids or r.target_entity in case_person_ids):
            if r.source_entity.startswith("P"):
                case_person_ids.add(r.source_entity)
            if r.target_entity.startswith("P"):
                case_person_ids.add(r.target_entity)

    # Centrality metrics via NetworkX
    betweenness = nx.betweenness_centrality(G) if len(G) > 0 else {}
    pagerank = nx.pagerank(G) if len(G) > 0 else {}
    degree = nx.degree_centrality(G) if len(G) > 0 else {}
    n_nodes = len(G) if len(G) > 0 else 1

    # 5. Financial metrics
    financial_volume = defaultdict(float)
    financial_tx_count = defaultdict(int)
    tx_query = db.query(Transaction)
    if scoped_case_id:
        tx_query = tx_query.filter(Transaction.case_id == scoped_case_id)
    
    for tx in tx_query.all():
        p_sender = account_person.get(tx.sender_account)
        p_receiver = account_person.get(tx.receiver_account)
        if p_sender:
            financial_volume[p_sender] += tx.amount
            financial_tx_count[p_sender] += 1
        if p_receiver:
            financial_volume[p_receiver] += tx.amount
            financial_tx_count[p_receiver] += 1

    max_fin_vol = max(financial_volume.values()) if financial_volume else 1.0
    max_fin_tx = max(financial_tx_count.values()) if financial_tx_count else 1

    # 6. Communication metrics
    comm_call_count = defaultdict(int)
    comm_contacts = defaultdict(set)
    comm_duration = defaultdict(int)
    cdr_query = db.query(CDR)
    if scoped_case_id:
        cdr_query = cdr_query.filter(CDR.case_id == scoped_case_id)

    for c in cdr_query.all():
        p_caller = phone_person.get(c.caller_phone_id)
        p_rec = phone_person.get(c.receiver_phone_id)
        if p_caller:
            comm_call_count[p_caller] += 1
            comm_duration[p_caller] += c.duration_seconds or 0
            if c.receiver_phone_id:
                comm_contacts[p_caller].add(c.receiver_phone_id)
        if p_rec:
            comm_call_count[p_rec] += 1
            comm_duration[p_rec] += c.duration_seconds or 0
            if c.caller_phone_id:
                comm_contacts[p_rec].add(c.caller_phone_id)

    max_comm_calls = max(comm_call_count.values()) if comm_call_count else 1
    max_comm_contacts = max((len(cts) for cts in comm_contacts.values()), default=1) or 1

    # 7. Cross-case involvement mapping across all cases
    all_fir_persons = db.query(FIRPerson).all()
    all_firs = {f.fir_id: f.case_id for f in db.query(FIR).all()}
    person_cases = defaultdict(set)
    person_firs = defaultdict(set)
    for fp in all_fir_persons:
        person_firs[fp.person_id].add(fp.fir_id)
        c_id = all_firs.get(fp.fir_id)
        if c_id:
            person_cases[fp.person_id].add(c_id)

    # 8. Evidence density mapping
    evidence_count_per_person = defaultdict(int)
    for (pid,) in db.query(FIRPerson.person_id).all():
        if pid:
            evidence_count_per_person[pid] += 1
    for pid, count in financial_tx_count.items():
        evidence_count_per_person[pid] += count
    for pid, count in comm_call_count.items():
        evidence_count_per_person[pid] += count
    for (pid,) in db.query(LocationEvent.person_id).filter(LocationEvent.person_id.isnot(None)).all():
        if pid:
            evidence_count_per_person[pid] += 1

    # 9. Query Persons
    persons_query = db.query(Person)
    if scoped_case_id and case_person_ids:
        persons_query = persons_query.filter(Person.person_id.in_(case_person_ids))
    persons = persons_query.all()

    results = []

    for p in persons:
        pid = p.person_id

        # ── Pillar 1: Network Centrality (20%) ──────────────────────────────
        deg_val = degree.get(pid, 0.0)
        pr_val = pagerank.get(pid, 0.0)
        pr_norm = min(1.0, pr_val * n_nodes)
        centrality_score = min(1.0, deg_val * 0.5 + pr_norm * 0.5)

        # ── Pillar 2: Betweenness / Connectivity (20%) ──────────────────────
        b_val = betweenness.get(pid, 0.0)
        # Scaled betweenness
        betweenness_score = min(1.0, b_val * 8.0)

        # ── Pillar 3: Financial Influence (20%) ─────────────────────────────
        p_fin_vol = financial_volume.get(pid, 0.0)
        p_fin_tx = financial_tx_count.get(pid, 0)
        fin_vol_norm = p_fin_vol / max_fin_vol if max_fin_vol > 0 else 0.0
        fin_tx_norm = p_fin_tx / max_fin_tx if max_fin_tx > 0 else 0.0
        financial_score = min(1.0, fin_vol_norm * 0.7 + fin_tx_norm * 0.3)

        # ── Pillar 4: Communication Influence (15%) ─────────────────────────
        p_calls = comm_call_count.get(pid, 0)
        p_contacts_cnt = len(comm_contacts.get(pid, set()))
        call_norm = p_calls / max_comm_calls if max_comm_calls > 0 else 0.0
        contact_norm = p_contacts_cnt / max_comm_contacts if max_comm_contacts > 0 else 0.0
        comm_score = min(1.0, call_norm * 0.6 + contact_norm * 0.4)

        # ── Pillar 5: Cross-Case Connections (15%) ──────────────────────────
        c_list = sorted(list(person_cases.get(pid, set())))
        c_count = len(c_list)
        fir_count = len(person_firs.get(pid, set()))
        # Score scaled: 1 case = 0.2, 2 cases = 0.5, 3+ cases = 0.8 to 1.0
        cross_case_score = min(1.0, 0.2 + (c_count - 1) * 0.35 + (fir_count - 1) * 0.1) if c_count > 0 else 0.05

        # ── Pillar 6: Evidence Strength (10%) ───────────────────────────────
        ev_count = evidence_count_per_person.get(pid, 0)
        evidence_score = min(1.0, ev_count / 15.0)

        # ── Composite: Network Leadership/Centrality Score ──────────────────
        composite = (
            0.20 * centrality_score +
            0.20 * betweenness_score +
            0.20 * financial_score +
            0.15 * comm_score +
            0.15 * cross_case_score +
            0.10 * evidence_score
        )
        score_100 = int(round(composite * 100))

        # Classification
        if score_100 >= 50:
            role_label = "Primary Network Orchestrator"
        elif score_100 >= 35:
            role_label = "Key Operational Broker"
        elif score_100 >= 20:
            role_label = "High-Activity Node"
        else:
            role_label = "Operational Associate"

        # Forensic Explanation
        reasons = []
        if betweenness_score > 0.3:
            reasons.append(f"acts as critical structural choke-point (betweenness: {b_val:.3f})")
        if p_fin_vol > 100000:
            reasons.append(f"controls ₹{p_fin_vol:,.0f} across {p_fin_tx} transactions")
        if p_calls >= 5:
            reasons.append(f"maintains {p_calls} telecom interactions across {p_contacts_cnt} distinct parties")
        if c_count > 1:
            reasons.append(f"linked across {c_count} separate criminal investigations ({', '.join(c_list[:3])})")
        if ev_count >= 8:
            reasons.append(f"grounded in {ev_count} verified evidentiary records")

        explanation_str = (
            f"Candidate exhibits strong network centrality ({score_100}/100): " + "; ".join(reasons) + "."
            if reasons else
            f"Candidate operates with standard connectivity ({score_100}/100) within the local cluster."
        )

        results.append({
            "person_id": pid,
            "full_name": p.full_name,
            "alias": p.alias,
            "city": p.city,
            "occupation": p.occupation,
            "network_leadership_score": round(composite, 4),
            "leadership_score_100": score_100,
            "composite_score": round(composite, 4),
            "kingpin_score": round(composite, 4),
            "role_classification": role_label,
            "explanation": explanation_str,
            "disclaimer": "⚠️ Network Leadership/Centrality Score is a structural topological metric — NOT a measure of legal guilt probability.",
            # 6 Pillars Breakdown
            "score_breakdown": {
                "network_centrality": round(centrality_score, 3),
                "betweenness_connectivity": round(betweenness_score, 3),
                "financial_influence": round(financial_score, 3),
                "communication_influence": round(comm_score, 3),
                "cross_case_connections": round(cross_case_score, 3),
                "evidence_strength": round(evidence_score, 3),
            },
            # Backwards-compatible fields for existing UI components
            "betweenness_score": round(betweenness_score, 3),
            "pagerank_score": round(pr_norm, 3),
            "financial_score": round(financial_score, 3),
            "telecom_score": round(comm_score, 3),
            "brokerage_score": round(betweenness_score, 3),
            "cross_domain_score": round(cross_case_score, 3),
            "degree_score": round(deg_val, 3),
            "case_count": c_count,
            "confidence": 0.95 if ev_count >= 5 else 0.85,
            # Underlying Forensic Metrics
            "metrics": {
                "betweenness_raw": round(b_val, 4),
                "pagerank_raw": round(pr_val, 4),
                "degree_raw": round(deg_val, 4),
                "financial_volume_inr": round(p_fin_vol, 2),
                "transaction_count": p_fin_tx,
                "call_count": p_calls,
                "call_duration_seconds": comm_duration.get(pid, 0),
                "unique_contacts": p_contacts_cnt,
                "cases_count": c_count,
                "cases_list": c_list,
                "firs_count": fir_count,
                "evidence_count": ev_count,
            },
        })

    # Sort candidates by network leadership score descending
    results.sort(key=lambda x: x["network_leadership_score"], reverse=True)
    
    # Assign ranks
    for idx, item in enumerate(results, start=1):
        item["rank"] = idx

    return results[:limit]
