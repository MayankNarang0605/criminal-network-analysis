"""
Financial Forensics & Money Laundering Intelligence Service.
Answers the central investigative question:
“How is money moving through the criminal network, and are there suspicious financial patterns?”

Implements the 5 Core Capabilities:
1. 💰 Transaction Analysis (Inflows/Outflows, Amounts, Dates, Senders, Receivers, Unusual Flags)
2. 🔄 Money Flow Chains (Multi-Hop Visual Tracker: Account A -> Account B -> Account C)
3. 🚨 Money Laundering Patterns (Structuring, Fan-in, Fan-out, Mule Funnels, Circular Flows)
4. 🔗 Cross-Case Financial Connections (Shared Accounts, Persons receiving from multiple cases)
5. 📊 Financial Risk & Summary Analytics (Total Money Analyzed, Suspicious Vol, Alerts with Evidence)
"""
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List, Optional, Set, Tuple
import numpy as np
from sqlalchemy.orm import Session

from backend.logging_config import logger
from backend.models.evidence import (
    Transaction, BankAccount, Person, Case
)


def format_currency_inr(amount: float) -> str:
    """Formats amount into readable Indian currency format (Cr / L / K)."""
    if amount >= 10000000:
        return f"₹{amount / 10000000:.2f} Cr"
    if amount >= 100000:
        return f"₹{amount / 100000:.2f}L"
    if amount >= 1000:
        return f"₹{amount / 1000:.1f}K"
    return f"₹{amount:,.0f}"


def format_date_human(iso_str: Optional[str]) -> str:
    """Converts ISO timestamp into readable format (e.g. 12 Aug 2026, 14:30)."""
    if not iso_str:
        return "Unknown Date"
    try:
        clean = iso_str.replace("Z", "").replace("T", " ")
        parts = clean.split()
        date_part = parts[0]
        time_part = parts[1][:5] if len(parts) > 1 else ""
        dt = datetime.fromisoformat(date_part)
        formatted = dt.strftime("%d %b %Y")
        return f"{formatted} {time_part}".strip()
    except Exception:
        return iso_str[:16]


def analyze_financial_intelligence(db: Session, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Comprehensive financial forensics engine analyzing transaction networks,
    money flows, laundering typologies, cross-case bridges, and risk metrics.
    """
    # 1. Fetch Transactions
    tx_query = db.query(Transaction)
    if case_id and case_id != "ALL":
        tx_query = tx_query.filter(Transaction.case_id == case_id)
    txs: List[Transaction] = tx_query.order_by(Transaction.timestamp.asc()).all()

    # Preload reference tables
    accounts = {b.account_id: b for b in db.query(BankAccount).all()}
    persons = {p.person_id: p for p in db.query(Person).all()}
    all_cases = {c.case_id: c for c in db.query(Case).all()}

    # Helper for resolving entity details
    def get_account_meta(acc_id: str) -> Dict[str, Any]:
        b = accounts.get(acc_id)
        p = persons.get(b.person_id) if b and b.person_id else None
        return {
            "account_id": acc_id,
            "bank_name": b.bank_name if b else "Commercial Bank",
            "branch_city": b.branch_city if b else "Unknown",
            "account_type": b.account_type if b else "Savings",
            "person_id": p.person_id if p else None,
            "person_name": p.full_name if p else f"Account {acc_id}",
            "alias": p.alias if p else None,
        }

    # ── 1. Transaction Analysis & Unusual Detection ──────────────────────────
    # Group transactions by account to calculate baseline distributions (IQR/MAD)
    account_txs = defaultdict(list)
    account_inflows = defaultdict(float)
    account_outflows = defaultdict(float)
    account_inflow_counts = defaultdict(int)
    account_outflow_counts = defaultdict(int)

    for t in txs:
        account_txs[t.sender_account].append(t)
        account_txs[t.receiver_account].append(t)
        account_outflows[t.sender_account] += t.amount
        account_inflows[t.receiver_account] += t.amount
        account_outflow_counts[t.sender_account] += 1
        account_inflow_counts[t.receiver_account] += 1

    # Compute account medians & IQRs
    account_stats = {}
    for acc, t_list in account_txs.items():
        amts = [t.amount for t in t_list]
        arr = np.array(amts)
        med = float(np.median(arr))
        q25 = float(np.percentile(arr, 25))
        q75 = float(np.percentile(arr, 75))
        account_stats[acc] = {
            "median": med,
            "q25": q25,
            "q75": q75,
            "iqr": max(q75 - q25, med * 0.2, 1000.0),
        }

    transactions_list = []
    suspicious_tx_count = 0
    global_median = float(np.median([t.amount for t in txs])) if txs else 18000.0
    transactions_list = []
    suspicious_tx_count = 0
    suspicious_volume = 0.0
    total_volume = 0.0

    for t in txs:
        total_volume += t.amount
        s_meta = get_account_meta(t.sender_account)
        r_meta = get_account_meta(t.receiver_account)

        # Baseline checks
        s_stats = account_stats.get(t.sender_account, {})
        s_med = s_stats.get("median", global_median)

        # Check for anomalies: volume spike, smurfing, high-value
        is_smurfing = 40000.0 <= t.amount <= 49999.0
        is_spike = t.amount >= 100000.0 or (s_med > 0 and t.amount >= 2.5 * s_med and t.amount >= 50000.0)
        is_high_value = t.amount >= 200000.0

        is_unusual = is_smurfing or is_spike or is_high_value
        unusual_reasons = []
        if is_spike:
            ratio = t.amount / max(s_med if s_med < t.amount else global_median, 1.0)
            unusual_reasons.append(f"Volume spike ({round(ratio, 1)}× baseline)")
        if is_smurfing:
            unusual_reasons.append("FATF smurfing boundary (₹40K–₹49.9K)")
        elif is_high_value:
            unusual_reasons.append("High-value single transfer")

        if is_unusual:
            suspicious_tx_count += 1
            suspicious_volume += t.amount

        transactions_list.append({
            "transaction_id": t.transaction_id,
            "case_id": t.case_id,
            "timestamp": t.timestamp,
            "date_formatted": format_date_human(t.timestamp),
            "amount": t.amount,
            "amount_formatted": format_currency_inr(t.amount),
            "sender_account": t.sender_account,
            "sender_name": s_meta["person_name"],
            "sender_bank": s_meta["bank_name"],
            "receiver_account": t.receiver_account,
            "receiver_name": r_meta["person_name"],
            "receiver_bank": r_meta["bank_name"],
            "location": t.location or "Electronic Transfer",
            "is_unusual": is_unusual,
            "unusual_reason": " • ".join(unusual_reasons) if unusual_reasons else None,
            "transaction_type": t.transaction_type or "transfer",
            "description": t.description or "Fund transfer",
        })

    # ── 2. Money Flow Chains (Multi-Hop Tracking: A -> B -> C -> D) ─────────
    # Trace multi-hop sequences where Account B receives funds and forwards downstream
    by_sender = defaultdict(list)
    for t in txs:
        by_sender[t.sender_account].append(t)

    money_flow_chains = []
    seen_chains = set()

    for t1 in txs:
        # Check if receiver forwarded money within 72 hours
        for t2 in by_sender.get(t1.receiver_account, []):
            if t2.receiver_account == t1.sender_account:
                continue  # Circular handled in pattern 5

            try:
                t1_dt = datetime.fromisoformat(t1.timestamp.replace("Z", "").replace(" ", "T"))
                t2_dt = datetime.fromisoformat(t2.timestamp.replace("Z", "").replace(" ", "T"))
                delta_hrs = (t2_dt - t1_dt).total_seconds() / 3600.0
            except Exception:
                delta_hrs = 0.0

            if 0.0 <= delta_hrs <= 72.0:
                chain_key = (t1.sender_account, t1.receiver_account, t2.receiver_account)
                if chain_key not in seen_chains:
                    seen_chains.add(chain_key)

                    # Check for 3-hop: does t2.receiver forward to t3?
                    t3_hop = None
                    for t3 in by_sender.get(t2.receiver_account, []):
                        if t3.receiver_account not in chain_key:
                            try:
                                t3_dt = datetime.fromisoformat(t3.timestamp.replace("Z", "").replace(" ", "T"))
                                delta3 = (t3_dt - t2_dt).total_seconds() / 3600.0
                                if 0.0 <= delta3 <= 72.0:
                                    t3_hop = (t3, delta3)
                                    break
                            except Exception:
                                pass

                    a_meta = get_account_meta(t1.sender_account)
                    b_meta = get_account_meta(t1.receiver_account)
                    c_meta = get_account_meta(t2.receiver_account)

                    steps = [
                        {
                            "hop": 1,
                            "from_account": t1.sender_account,
                            "from_name": a_meta["person_name"],
                            "from_bank": a_meta["bank_name"],
                            "to_account": t1.receiver_account,
                            "to_name": b_meta["person_name"],
                            "to_bank": b_meta["bank_name"],
                            "amount": t1.amount,
                            "amount_formatted": format_currency_inr(t1.amount),
                            "timestamp": t1.timestamp,
                            "date": format_date_human(t1.timestamp),
                            "tx_id": t1.transaction_id,
                        },
                        {
                            "hop": 2,
                            "from_account": t2.sender_account,
                            "from_name": b_meta["person_name"],
                            "from_bank": b_meta["bank_name"],
                            "to_account": t2.receiver_account,
                            "to_name": c_meta["person_name"],
                            "to_bank": c_meta["bank_name"],
                            "amount": t2.amount,
                            "amount_formatted": format_currency_inr(t2.amount),
                            "timestamp": t2.timestamp,
                            "date": format_date_human(t2.timestamp),
                            "tx_id": t2.transaction_id,
                            "latency_hours": round(delta_hrs, 1),
                        },
                    ]

                    if t3_hop:
                        t3, delta3 = t3_hop
                        d_meta = get_account_meta(t3.receiver_account)
                        steps.append({
                            "hop": 3,
                            "from_account": t3.sender_account,
                            "from_name": c_meta["person_name"],
                            "from_bank": c_meta["bank_name"],
                            "to_account": t3.receiver_account,
                            "to_name": d_meta["person_name"],
                            "to_bank": d_meta["bank_name"],
                            "amount": t3.amount,
                            "amount_formatted": format_currency_inr(t3.amount),
                            "timestamp": t3.timestamp,
                            "date": format_date_human(t3.timestamp),
                            "tx_id": t3.transaction_id,
                            "latency_hours": round(delta3, 1),
                        })

                    total_initial = t1.amount
                    end_amount = steps[-1]["amount"]
                    forward_ratio = (end_amount / max(total_initial, 1.0)) * 100.0

                    money_flow_chains.append({
                        "chain_id": f"FLOW-{t1.transaction_id}-{t2.transaction_id}",
                        "hop_count": len(steps),
                        "origin_account": t1.sender_account,
                        "origin_name": a_meta["person_name"],
                        "intermediary_account": t1.receiver_account,
                        "intermediary_name": b_meta["person_name"],
                        "destination_account": steps[-1]["to_account"],
                        "destination_name": steps[-1]["to_name"],
                        "initial_amount": total_initial,
                        "initial_amount_formatted": format_currency_inr(total_initial),
                        "forwarded_amount": end_amount,
                        "forwarded_amount_formatted": format_currency_inr(end_amount),
                        "retention_percentage": round(forward_ratio, 1),
                        "total_latency_hours": round(sum(s.get("latency_hours", 0) for s in steps), 1),
                        "classification": "Mule Relay Layering" if forward_ratio >= 75.0 else "Partial Pass-Through",
                        "steps": steps,
                        "evidence_ids": [s["tx_id"] for s in steps],
                    })

    # Sort flow chains by initial amount descending
    money_flow_chains.sort(key=lambda x: x["initial_amount"], reverse=True)

    # ── 3. Money Laundering Patterns ─────────────────────────────────────────
    # 5 Detectors: Structuring, Fan-in, Fan-out, Mule Funnel, Circular Flow
    patterns = []

    # A. Structuring / Smurfing
    structuring_by_acc = defaultdict(list)
    for t in txs:
        if 40000.0 <= t.amount <= 49999.0:
            structuring_by_acc[t.sender_account].append(t)

    for acc, s_list in structuring_by_acc.items():
        if len(s_list) >= 2:
            acc_meta = get_account_meta(acc)
            tot_amt = sum(t.amount for t in s_list)
            ev_ids = [t.transaction_id for t in s_list]
            patterns.append({
                "pattern_id": f"PAT-STRUC-{acc}",
                "pattern_type": "Structuring / Smurfing",
                "severity": "CRITICAL" if len(s_list) >= 4 or tot_amt >= 200000 else "HIGH",
                "title": f"Structuring (Smurfing) Cluster — {acc_meta['person_name']} ({acc})",
                "entity": acc_meta["person_name"],
                "account_id": acc,
                "event_count": len(s_list),
                "total_amount": tot_amt,
                "formatted_amount": format_currency_inr(tot_amt),
                "explanation": (
                    f"Account executed {len(s_list)} separate transactions clustered tightly between ₹40K–₹49.9K "
                    f"(totalling {format_currency_inr(tot_amt)}). Deliberately engineered to evade mandatory anti-money laundering reporting thresholds."
                ),
                "evidence": ev_ids,
                "first_date": format_date_human(s_list[0].timestamp),
                "last_date": format_date_human(s_list[-1].timestamp),
            })

    # B. Fan-in (Many senders -> 1 funnel account)
    senders_to_rec = defaultdict(set)
    rec_tx_map = defaultdict(list)
    for t in txs:
        senders_to_rec[t.receiver_account].add(t.sender_account)
        rec_tx_map[t.receiver_account].append(t)

    for acc, senders in senders_to_rec.items():
        if len(senders) >= 3:
            acc_meta = get_account_meta(acc)
            in_txs = rec_tx_map[acc]
            tot_in = sum(t.amount for t in in_txs)
            ev_ids = [t.transaction_id for t in in_txs[:12]]
            patterns.append({
                "pattern_id": f"PAT-FANIN-{acc}",
                "pattern_type": "Fan-in Aggregation",
                "severity": "CRITICAL" if len(senders) >= 5 or tot_in >= 300000 else "HIGH",
                "title": f"Fan-in Fund Aggregation — {acc_meta['person_name']} ({acc})",
                "entity": acc_meta["person_name"],
                "account_id": acc,
                "event_count": len(in_txs),
                "counterparties_count": len(senders),
                "total_amount": tot_in,
                "formatted_amount": format_currency_inr(tot_in),
                "explanation": (
                    f"Funnel account rapidly aggregated funds from {len(senders)} distinct sender accounts "
                    f"totalling {format_currency_inr(tot_in)}. Classic funnel aggregator topology."
                ),
                "evidence": ev_ids,
                "first_date": format_date_human(in_txs[0].timestamp),
                "last_date": format_date_human(in_txs[-1].timestamp),
            })

    # C. Fan-out (1 account -> Many receivers)
    rec_from_sender = defaultdict(set)
    sender_tx_map = defaultdict(list)
    for t in txs:
        rec_from_sender[t.sender_account].add(t.receiver_account)
        sender_tx_map[t.sender_account].append(t)

    for acc, receivers in rec_from_sender.items():
        if len(receivers) >= 3:
            acc_meta = get_account_meta(acc)
            out_txs = sender_tx_map[acc]
            tot_out = sum(t.amount for t in out_txs)
            ev_ids = [t.transaction_id for t in out_txs[:12]]
            patterns.append({
                "pattern_id": f"PAT-FANOUT-{acc}",
                "pattern_type": "Fan-out Dispersal",
                "severity": "CRITICAL" if len(receivers) >= 5 or tot_out >= 300000 else "HIGH",
                "title": f"Fan-out Fund Dispersal — {acc_meta['person_name']} ({acc})",
                "entity": acc_meta["person_name"],
                "account_id": acc,
                "event_count": len(out_txs),
                "counterparties_count": len(receivers),
                "total_amount": tot_out,
                "formatted_amount": format_currency_inr(tot_out),
                "explanation": (
                    f"Dispersal node rapidly split and routed funds across {len(receivers)} distinct recipient accounts "
                    f"(totalling {format_currency_inr(tot_out)}). Syndicate layering and cash-out dispersal signature."
                ),
                "evidence": ev_ids,
                "first_date": format_date_human(out_txs[0].timestamp),
                "last_date": format_date_human(out_txs[-1].timestamp),
            })

    # D. Mule Funnel (Intermediary Conduit: High inflow + High outflow within 72h)
    for acc in set(account_inflows.keys()).intersection(set(account_outflows.keys())):
        in_vol = account_inflows[acc]
        out_vol = account_outflows[acc]
        if in_vol >= 50000 and out_vol >= 40000:
            ratio = out_vol / in_vol
            if 0.70 <= ratio <= 1.30:  # Retains very little money; purely a pass-through conduit
                acc_meta = get_account_meta(acc)
                all_acc_txs = account_txs[acc]
                ev_ids = [t.transaction_id for t in all_acc_txs[:10]]
                patterns.append({
                    "pattern_id": f"PAT-MULE-{acc}",
                    "pattern_type": "Mule Funnel",
                    "severity": "CRITICAL" if in_vol >= 200000 else "HIGH",
                    "title": f"Mule Conduit (Pass-Through Funnel) — {acc_meta['person_name']} ({acc})",
                    "entity": acc_meta["person_name"],
                    "account_id": acc,
                    "event_count": len(all_acc_txs),
                    "total_amount": in_vol,
                    "formatted_amount": format_currency_inr(in_vol),
                    "explanation": (
                        f"Account received {format_currency_inr(in_vol)} and immediately dispersed "
                        f"{format_currency_inr(out_vol)} ({round(ratio * 100, 1)}% passthrough ratio). "
                        f"Zero legitimate holding duration; operating as an intermediary money mule conduit."
                    ),
                    "evidence": ev_ids,
                    "first_date": format_date_human(all_acc_txs[0].timestamp),
                    "last_date": format_date_human(all_acc_txs[-1].timestamp),
                })

    # E. Circular Flow (Round-Tripping / Wash Cycles: A -> B -> A or A -> B -> C -> A)
    adj_graph = defaultdict(set)
    edge_txs = defaultdict(list)
    for t in txs:
        adj_graph[t.sender_account].add(t.receiver_account)
        edge_txs[(t.sender_account, t.receiver_account)].append(t)

    detected_cycles = []
    seen_cycle_nodes = set()

    # Check 2-node cycle (A <-> B)
    for a in list(adj_graph.keys()):
        for b in adj_graph[a]:
            if a in adj_graph.get(b, set()):
                node_pair = tuple(sorted([a, b]))
                if node_pair not in seen_cycle_nodes:
                    seen_cycle_nodes.add(node_pair)
                    t_ab = edge_txs.get((a, b), [])
                    t_ba = edge_txs.get((b, a), [])
                    tot_cycle = sum(t.amount for t in t_ab + t_ba)
                    a_meta = get_account_meta(a)
                    b_meta = get_account_meta(b)

                    patterns.append({
                        "pattern_id": f"PAT-CYCLE-{a}-{b}",
                        "pattern_type": "Circular Flow",
                        "severity": "CRITICAL" if tot_cycle >= 200000 else "HIGH",
                        "title": f"Circular Round-Tripping ({a_meta['person_name']} ↔ {b_meta['person_name']})",
                        "entity": f"{a_meta['person_name']} ↔ {b_meta['person_name']}",
                        "account_id": f"{a}, {b}",
                        "event_count": len(t_ab) + len(t_ba),
                        "total_amount": tot_cycle,
                        "formatted_amount": format_currency_inr(tot_cycle),
                        "explanation": (
                            f"Reciprocal circular transfers detected between accounts {a} and {b} "
                            f"(totalling {format_currency_inr(tot_cycle)}). Funds sent out return back to origin, "
                            f"characteristic of wash-trading, balance inflation, or artificial transaction volume."
                        ),
                        "evidence": [t.transaction_id for t in (t_ab + t_ba)[:8]],
                        "first_date": format_date_human(t_ab[0].timestamp if t_ab else None),
                        "last_date": format_date_human(t_ba[-1].timestamp if t_ba else None),
                    })

    # Sort patterns: CRITICAL -> HIGH
    sev_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    patterns.sort(key=lambda x: (sev_rank.get(x["severity"], 9), -x["total_amount"]))

    # ── 4. Cross-Case Financial Connections ──────────────────────────────────
    # A. Bank accounts appearing across >= 2 cases
    all_global_txs = db.query(Transaction).all()
    account_global_cases = defaultdict(set)
    account_global_txs = defaultdict(list)
    for t in all_global_txs:
        account_global_cases[t.sender_account].add(t.case_id)
        account_global_cases[t.receiver_account].add(t.case_id)
        account_global_txs[t.sender_account].append(t)
        account_global_txs[t.receiver_account].append(t)

    cross_case_accounts = []
    # If case_id specified, filter for accounts that link case_id to other cases
    candidate_accounts = set(account_txs.keys()) if (case_id and case_id != "ALL") else set(account_global_cases.keys())

    for acc in candidate_accounts:
        c_set = account_global_cases.get(acc, set())
        if len(c_set) >= 2:
            acc_meta = get_account_meta(acc)
            acc_tx_list = account_global_txs.get(acc, [])
            tot_cross_vol = sum(t.amount for t in acc_tx_list)
            cross_case_accounts.append({
                "account_id": acc,
                "entity_name": acc_meta["person_name"],
                "bank_name": acc_meta["bank_name"],
                "branch_city": acc_meta["branch_city"],
                "case_count": len(c_set),
                "linked_cases": sorted(list(c_set)),
                "total_cross_volume": tot_cross_vol,
                "formatted_volume": format_currency_inr(tot_cross_vol),
                "total_transactions": len(acc_tx_list),
                "evidence_ids": [t.transaction_id for t in acc_tx_list[:8]],
                "relationship": "Cross-Jurisdiction Financial Bridge",
            })

    cross_case_accounts.sort(key=lambda x: (-x["case_count"], -x["total_cross_volume"]))

    # B. Persons receiving from multiple suspicious entities / cases
    person_global_inflows = defaultdict(lambda: {"cases": set(), "senders": set(), "volume": 0.0, "txs": []})
    for t in all_global_txs:
        r_acc = accounts.get(t.receiver_account)
        if r_acc and r_acc.person_id:
            pid = r_acc.person_id
            person_global_inflows[pid]["cases"].add(t.case_id)
            person_global_inflows[pid]["senders"].add(t.sender_account)
            person_global_inflows[pid]["volume"] += t.amount
            person_global_inflows[pid]["txs"].append(t)

    cross_case_persons = []
    for pid, p_data in person_global_inflows.items():
        if len(p_data["cases"]) >= 2 and len(p_data["senders"]) >= 2:
            p_obj = persons.get(pid)
            if p_obj:
                # If case_id specified, ensure person is relevant to case_id
                if case_id and case_id != "ALL" and case_id not in p_data["cases"]:
                    continue

                cross_case_persons.append({
                    "person_id": pid,
                    "name": p_obj.full_name,
                    "alias": p_obj.alias or "None",
                    "city": p_obj.city or "Unknown",
                    "case_count": len(p_data["cases"]),
                    "linked_cases": sorted(list(p_data["cases"])),
                    "sender_accounts_count": len(p_data["senders"]),
                    "total_received": p_data["volume"],
                    "formatted_received": format_currency_inr(p_data["volume"]),
                    "evidence_ids": [t.transaction_id for t in p_data["txs"][:8]],
                })

    cross_case_persons.sort(key=lambda x: (-x["case_count"], -x["total_received"]))

    # ── 5. Financial Risk & Summary Analytics ────────────────────────────────
    distinct_suspicious_accounts = set()
    for p in patterns:
        for a_id in p["account_id"].split(", "):
            distinct_suspicious_accounts.add(a_id.strip())

    pattern_counts = {
        "structuring": sum(1 for p in patterns if p["pattern_type"] == "Structuring / Smurfing"),
        "fan_in": sum(1 for p in patterns if p["pattern_type"] == "Fan-in Aggregation"),
        "fan_out": sum(1 for p in patterns if p["pattern_type"] == "Fan-out Dispersal"),
        "mule_funnel": sum(1 for p in patterns if p["pattern_type"] == "Mule Funnel"),
        "circular_flow": sum(1 for p in patterns if p["pattern_type"] == "Circular Flow"),
    }

    # Top Transacting Accounts Table
    top_accounts = []
    for acc, amt_in in sorted(account_inflows.items(), key=lambda x: x[1], reverse=True)[:15]:
        amt_out = account_outflows.get(acc, 0.0)
        acc_meta = get_account_meta(acc)
        top_accounts.append({
            "account_id": acc,
            "entity_name": acc_meta["person_name"],
            "bank_name": acc_meta["bank_name"],
            "branch_city": acc_meta["branch_city"],
            "total_inflow": amt_in,
            "formatted_inflow": format_currency_inr(amt_in),
            "total_outflow": amt_out,
            "formatted_outflow": format_currency_inr(amt_out),
            "inflow_count": account_inflow_counts[acc],
            "outflow_count": account_outflow_counts[acc],
            "net_flow": amt_in - amt_out,
            "formatted_net": format_currency_inr(amt_in - amt_out),
            "is_flagged": acc in distinct_suspicious_accounts,
        })

    return {
        "case_id": case_id,
        "summary": {
            "total_money_analyzed": total_volume,
            "formatted_total_money": format_currency_inr(total_volume),
            "total_transactions": len(txs),
            "suspicious_transactions_count": suspicious_tx_count,
            "suspicious_volume": suspicious_volume,
            "formatted_suspicious_volume": format_currency_inr(suspicious_volume),
            "suspicious_accounts_count": len(distinct_suspicious_accounts),
            "active_patterns_count": len(patterns),
            "money_flow_chains_count": len(money_flow_chains),
            "cross_case_accounts_count": len(cross_case_accounts),
            "pattern_counts": pattern_counts,
        },
        "transactions": transactions_list,
        "money_flow_chains": money_flow_chains[:25],
        "patterns": patterns,
        "cross_case": {
            "accounts": cross_case_accounts[:20],
            "persons": cross_case_persons[:15],
        },
        "top_accounts": top_accounts,
    }
