"""
Suspicious pattern detection.

Three independent detectors, each mapped to a recognised typology so findings are
defensible rather than "the model said so":

1. `FinancialPatternDetector` — FATF/FIU-IND money-laundering typologies:
   structuring below the CTR threshold, layering chains, fan-out/fan-in mule
   networks, circular round-tripping, rapid pass-through, and dormant-then-burst
   accounts.
2. `CommunicationPatternDetector` — CDR behavioural signatures: burst activity
   before an incident, odd-hour coordination, hub-and-spoke command patterns,
   one-way broadcast trees, co-location at cell towers, and burner-phone handoff.
3. `AnomalyDetector` — unsupervised outlier scoring (robust z-score + IQR +
   Mahalanobis-style multivariate distance) over per-entity behavioural features.
"""
from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Sequence

from app import db

# Indian regulatory thresholds that criminals structure around.
CTR_THRESHOLD = 1_000_000.0      # Rs 10 lakh cash transaction reporting trigger
STR_WATCH = 5_000_000.0          # Rs 50 lakh — routinely reported as suspicious
STRUCTURING_BAND = 0.92          # transactions at >=92% of threshold are suspicious


@dataclass
class Finding:
    pattern_type: str
    typology: str
    severity: str            # critical | high | medium | low
    confidence: float
    summary: str
    members: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ===========================================================================
# Financial
# ===========================================================================
class FinancialPatternDetector:
    """Money-laundering typology detection over the transaction ledger."""

    def __init__(self) -> None:
        self.txns = [dict(r) for r in db.query(
            "SELECT txn_id, ts, from_account, from_bank, from_name, to_account, "
            "to_bank, to_name, amount, txn_type, description, flagged "
            "FROM transactions ORDER BY ts"
        )]

    def run(self) -> list[Finding]:
        if not self.txns:
            return []
        findings: list[Finding] = []
        findings += self.detect_structuring()
        findings += self.detect_layering_chains()
        findings += self.detect_fan_patterns()
        findings += self.detect_circular_flows()
        findings += self.detect_rapid_passthrough()
        findings += self.detect_dormant_burst()
        return findings

    # -- 1. structuring / smurfing ---------------------------------------
    def detect_structuring(self) -> list[Finding]:
        """
        Multiple transfers deliberately sized just under the Rs 10 lakh CTR
        threshold within a short window — the classic smurfing signature.
        """
        by_account: dict[str, list[dict]] = defaultdict(list)
        for t in self.txns:
            by_account[t["from_account"]].append(t)

        findings: list[Finding] = []
        for account, txns in by_account.items():
            near = [t for t in txns
                    if CTR_THRESHOLD * STRUCTURING_BAND <= t["amount"] < CTR_THRESHOLD]
            if len(near) < 2:
                continue
            window = _time_span_days(near)
            total = sum(t["amount"] for t in near)
            # Tighter window + more slices = stronger evidence.
            confidence = min(0.55 + 0.12 * len(near) + (0.15 if window <= 7 else 0.0), 0.97)
            findings.append(Finding(
                pattern_type="structuring",
                typology="FATF: Structuring / Smurfing below CTR threshold",
                severity="high" if len(near) >= 3 else "medium",
                confidence=round(confidence, 3),
                summary=(
                    f"Account {account} made {len(near)} transfers totalling "
                    f"Rs {total:,.0f} each sized just below the Rs 10,00,000 CTR "
                    f"reporting threshold within {window} day(s)."
                ),
                members=[account] + sorted({t["to_account"] for t in near}),
                detail={
                    "account": account,
                    "holder": near[0].get("from_name"),
                    "transaction_count": len(near),
                    "total_amount": total,
                    "window_days": window,
                    "amounts": [t["amount"] for t in near],
                    "threshold": CTR_THRESHOLD,
                    "transaction_ids": [t["txn_id"] for t in near],
                },
                recommendation=(
                    "Request full statement from the bank under Section 91 CrPC and "
                    "cross-check against FIU-IND CTR filings for the same period."
                ),
            ))
        return findings

    # -- 2. layering chains ----------------------------------------------
    def detect_layering_chains(self, min_depth: int = 3) -> list[Finding]:
        """
        Follow money forward in time through successive accounts. A chain of
        A→B→C→D where each hop retains most of the value and occurs soon after
        the previous one is layering, not ordinary commerce.
        """
        outgoing: dict[str, list[dict]] = defaultdict(list)
        for t in self.txns:
            outgoing[t["from_account"]].append(t)

        findings: list[Finding] = []
        seen_chains: set[tuple] = set()

        def walk(chain: list[dict], visited: set[str]) -> None:
            last = chain[-1]
            nexts = [
                n for n in outgoing.get(last["to_account"], [])
                if n["to_account"] not in visited
                and _parse_ts(n["ts"]) >= _parse_ts(last["ts"])
                and (_parse_ts(n["ts"]) - _parse_ts(last["ts"])).days <= 30
                and n["amount"] >= last["amount"] * 0.25
            ]
            if not nexts:
                if len(chain) >= min_depth:
                    key = tuple([chain[0]["from_account"]] + [c["to_account"] for c in chain])
                    if key not in seen_chains:
                        seen_chains.add(key)
                        findings.append(self._chain_finding(chain))
                return
            for n in nexts[:3]:
                walk(chain + [n], visited | {n["to_account"]})

        for account, txns in outgoing.items():
            for t in txns:
                walk([t], {account, t["to_account"]})
        return findings[:25]

    def _chain_finding(self, chain: list[dict]) -> Finding:
        accounts = [chain[0]["from_account"]] + [c["to_account"] for c in chain]
        names = [chain[0].get("from_name") or chain[0]["from_account"]] + \
                [c.get("to_name") or c["to_account"] for c in chain]
        initial, final = chain[0]["amount"], chain[-1]["amount"]
        retention = final / initial if initial else 0.0
        span = (_parse_ts(chain[-1]["ts"]) - _parse_ts(chain[0]["ts"])).days
        confidence = min(0.5 + 0.1 * len(chain) + (0.2 if span <= 10 else 0.05), 0.95)
        terminal_cash = accounts[-1] == "CASH"
        return Finding(
            pattern_type="layering",
            typology="FATF: Layering through successive account transfers",
            severity="critical" if len(chain) >= 4 or terminal_cash else "high",
            confidence=round(confidence, 3),
            summary=(
                f"Funds of Rs {initial:,.0f} moved through {len(chain)} hops "
                f"({' → '.join(names)}) over {span} day(s), retaining "
                f"{retention*100:.0f}% of value"
                + (" and terminating in cash withdrawal." if terminal_cash
                   else ", consistent with layering to obscure origin.")
            ),
            members=accounts,
            detail={
                "hops": [
                    {
                        "txn_id": c["txn_id"], "from": c["from_account"],
                        "from_name": c.get("from_name"), "to": c["to_account"],
                        "to_name": c.get("to_name"), "amount": c["amount"],
                        "date": c["ts"], "type": c["txn_type"],
                    } for c in chain
                ],
                "depth": len(chain),
                "initial_amount": initial,
                "final_amount": final,
                "value_retention": round(retention, 3),
                "span_days": span,
                "terminates_in_cash": terminal_cash,
            },
            recommendation=(
                "Trace beneficial ownership of each intermediate account. "
                "Consider attachment proceedings under PMLA Section 5 if the "
                "layering chain is corroborated."
            ),
        )

    # -- 3. fan-out / fan-in (mule networks) -----------------------------
    def detect_fan_patterns(self) -> list[Finding]:
        out_deg: dict[str, set[str]] = defaultdict(set)
        in_deg: dict[str, set[str]] = defaultdict(set)
        out_amt: dict[str, float] = defaultdict(float)
        in_amt: dict[str, float] = defaultdict(float)
        for t in self.txns:
            out_deg[t["from_account"]].add(t["to_account"])
            in_deg[t["to_account"]].add(t["from_account"])
            out_amt[t["from_account"]] += t["amount"]
            in_amt[t["to_account"]] += t["amount"]

        findings: list[Finding] = []
        for account, targets in out_deg.items():
            if len(targets) >= 4:
                findings.append(Finding(
                    pattern_type="fan_out",
                    typology="FATF: Fan-out distribution to money mules",
                    severity="high" if len(targets) >= 6 else "medium",
                    confidence=round(min(0.55 + 0.07 * len(targets), 0.95), 3),
                    summary=(
                        f"Account {account} dispersed Rs {out_amt[account]:,.0f} across "
                        f"{len(targets)} distinct beneficiary accounts — a distribution "
                        f"pattern typical of mule-network payouts."
                    ),
                    members=[account] + sorted(targets),
                    detail={"account": account, "beneficiary_count": len(targets),
                            "total_dispersed": out_amt[account],
                            "beneficiaries": sorted(targets)},
                    recommendation="Freeze beneficiary accounts and obtain KYC for mule identification.",
                ))
        for account, sources in in_deg.items():
            if len(sources) >= 4:
                findings.append(Finding(
                    pattern_type="fan_in",
                    typology="FATF: Fan-in consolidation into collection account",
                    severity="high" if len(sources) >= 6 else "medium",
                    confidence=round(min(0.55 + 0.07 * len(sources), 0.95), 3),
                    summary=(
                        f"Account {account} aggregated Rs {in_amt[account]:,.0f} from "
                        f"{len(sources)} distinct source accounts — consolidation "
                        f"consistent with a collection/settlement account."
                    ),
                    members=[account] + sorted(sources),
                    detail={"account": account, "source_count": len(sources),
                            "total_collected": in_amt[account], "sources": sorted(sources)},
                    recommendation="Identify the controlling person of the collection account; likely a financier node.",
                ))
        return findings

    # -- 4. circular flows -----------------------------------------------
    def detect_circular_flows(self) -> list[Finding]:
        """Round-tripping: value returns to origin after passing through others."""
        edges: dict[str, list[dict]] = defaultdict(list)
        for t in self.txns:
            edges[t["from_account"]].append(t)

        findings: list[Finding] = []
        seen: set[frozenset] = set()

        def dfs(start: str, current: str, path: list[dict], depth: int) -> None:
            if depth > 4:
                return
            for t in edges.get(current, []):
                if t["to_account"] == start and len(path) >= 2:
                    cycle = frozenset([start] + [p["to_account"] for p in path])
                    if cycle in seen:
                        continue
                    seen.add(cycle)
                    full = path + [t]
                    accounts = [start] + [p["to_account"] for p in full]
                    findings.append(Finding(
                        pattern_type="circular_flow",
                        typology="FATF: Round-tripping / circular fund movement",
                        severity="critical",
                        confidence=0.9,
                        summary=(
                            f"Circular fund movement detected: "
                            f"{' → '.join(accounts)}. Money returns to its origin "
                            f"after {len(full)} hops, with no discernible economic purpose."
                        ),
                        members=accounts[:-1],
                        detail={
                            "cycle": accounts,
                            "hop_count": len(full),
                            "total_moved": sum(p["amount"] for p in full),
                            "transaction_ids": [p["txn_id"] for p in full],
                        },
                        recommendation=(
                            "Round-tripping with no commercial rationale is prima facie "
                            "evidence under PMLA. Escalate to the Enforcement Directorate."
                        ),
                    ))
                elif t["to_account"] not in [p["to_account"] for p in path] and t["to_account"] != start:
                    dfs(start, t["to_account"], path + [t], depth + 1)

        for account in list(edges.keys()):
            dfs(account, account, [], 1)
        return findings[:15]

    # -- 5. rapid pass-through -------------------------------------------
    def detect_rapid_passthrough(self, hours: int = 48) -> list[Finding]:
        """Money in, money out within hours: account used purely as a conduit."""
        incoming: dict[str, list[dict]] = defaultdict(list)
        outgoing: dict[str, list[dict]] = defaultdict(list)
        for t in self.txns:
            incoming[t["to_account"]].append(t)
            outgoing[t["from_account"]].append(t)

        findings: list[Finding] = []
        for account in set(incoming) & set(outgoing):
            if account == "CASH":
                continue
            pairs = []
            for i in incoming[account]:
                ti = _parse_ts(i["ts"])
                for o in outgoing[account]:
                    to = _parse_ts(o["ts"])
                    delta = (to - ti).total_seconds() / 3600.0
                    if 0 <= delta <= hours and o["amount"] >= i["amount"] * 0.7:
                        pairs.append({
                            "in_txn": i["txn_id"], "out_txn": o["txn_id"],
                            "in_amount": i["amount"], "out_amount": o["amount"],
                            "hold_hours": round(delta, 1),
                            "source": i["from_account"], "destination": o["to_account"],
                        })
            if len(pairs) >= 2:
                avg_hold = statistics.mean(p["hold_hours"] for p in pairs)
                findings.append(Finding(
                    pattern_type="rapid_passthrough",
                    typology="FATF: Pass-through / conduit account",
                    severity="high",
                    confidence=round(min(0.6 + 0.08 * len(pairs), 0.95), 3),
                    summary=(
                        f"Account {account} functioned as a conduit in {len(pairs)} "
                        f"instances, forwarding funds within an average of "
                        f"{avg_hold:.1f} hours of receipt while retaining almost no balance."
                    ),
                    members=[account],
                    detail={"account": account, "instances": pairs,
                            "avg_hold_hours": round(avg_hold, 2)},
                    recommendation="Treat the account holder as a probable mule rather than a principal.",
                ))
        return findings

    # -- 6. dormant then burst -------------------------------------------
    def detect_dormant_burst(self) -> list[Finding]:
        by_account: dict[str, list[dict]] = defaultdict(list)
        for t in self.txns:
            by_account[t["from_account"]].append(t)

        findings: list[Finding] = []
        for account, txns in by_account.items():
            if len(txns) < 4 or account == "CASH":
                continue
            times = sorted(_parse_ts(t["ts"]) for t in txns)
            gaps = [(b - a).days for a, b in zip(times, times[1:])]
            if not gaps:
                continue
            max_gap = max(gaps)
            idx = gaps.index(max_gap)
            after = times[idx + 1:]
            if max_gap >= 30 and len(after) >= 3:
                burst_days = (after[-1] - after[0]).days + 1
                if burst_days <= 14:
                    findings.append(Finding(
                        pattern_type="dormant_burst",
                        typology="FIU-IND: Dormant account reactivated with sudden high activity",
                        severity="high",
                        confidence=0.82,
                        summary=(
                            f"Account {account} was dormant for {max_gap} days, then "
                            f"executed {len(after)} transactions within {burst_days} day(s) "
                            f"totalling Rs {sum(t['amount'] for t in txns[idx+1:]):,.0f}."
                        ),
                        members=[account],
                        detail={"account": account, "dormancy_days": max_gap,
                                "burst_transactions": len(after),
                                "burst_window_days": burst_days},
                        recommendation="Verify whether account control changed during dormancy (mule takeover).",
                    ))
        return findings


# ===========================================================================
# Communication
# ===========================================================================
class CommunicationPatternDetector:
    """Behavioural signatures in Call Detail Records."""

    def __init__(self) -> None:
        self.calls = [dict(r) for r in db.query(
            "SELECT call_id, caller, callee, ts, duration, call_type, tower_id, "
            "tower_name, lat, lon FROM cdr ORDER BY ts"
        )]

    def run(self) -> list[Finding]:
        if not self.calls:
            return []
        findings: list[Finding] = []
        findings += self.detect_hub_spoke()
        findings += self.detect_odd_hour_coordination()
        findings += self.detect_burst_before_incident()
        findings += self.detect_co_location()
        findings += self.detect_one_way_broadcast()
        return findings

    # -- hub and spoke ----------------------------------------------------
    def detect_hub_spoke(self) -> list[Finding]:
        """
        A number that talks to many peers who do not talk to each other is a
        command hub. This is the CDR fingerprint of a controller who keeps his
        subordinates compartmentalised.
        """
        contacts: dict[str, set[str]] = defaultdict(set)
        for c in self.calls:
            contacts[c["caller"]].add(c["callee"])
            contacts[c["callee"]].add(c["caller"])

        pair_exists = {(c["caller"], c["callee"]) for c in self.calls}
        pair_exists |= {(b, a) for a, b in pair_exists}

        findings: list[Finding] = []
        for number, peers in contacts.items():
            if len(peers) < 3:
                continue
            peers_list = sorted(peers)
            interconnections = sum(
                1 for i in range(len(peers_list)) for j in range(i + 1, len(peers_list))
                if (peers_list[i], peers_list[j]) in pair_exists
            )
            possible = len(peers_list) * (len(peers_list) - 1) / 2
            density = interconnections / possible if possible else 0.0
            if density <= 0.2:
                findings.append(Finding(
                    pattern_type="hub_and_spoke",
                    typology="Command-and-control communication topology",
                    severity="high" if len(peers) >= 5 else "medium",
                    confidence=round(min(0.6 + 0.07 * len(peers) + (0.15 if density == 0 else 0), 0.95), 3),
                    summary=(
                        f"Number {number} is in contact with {len(peers)} peers who have "
                        f"almost no contact with each other (inter-peer density "
                        f"{density:.0%}) — a compartmentalised command topology."
                    ),
                    members=[number] + peers_list,
                    detail={"hub": number, "spoke_count": len(peers),
                            "spokes": peers_list, "inter_peer_density": round(density, 3)},
                    recommendation="Prioritise this number for lawful interception; likely controller.",
                ))
        return findings

    # -- odd-hour coordination -------------------------------------------
    def detect_odd_hour_coordination(self) -> list[Finding]:
        odd: list[dict] = []
        for c in self.calls:
            ts = _parse_ts(c["ts"])
            if ts.hour < 5 or ts.hour >= 23:
                odd.append(c)
        if len(odd) < 2:
            return []
        by_pair: dict[tuple, list[dict]] = defaultdict(list)
        for c in odd:
            by_pair[tuple(sorted((c["caller"], c["callee"])))].append(c)

        findings: list[Finding] = []
        for (a, b), calls in by_pair.items():
            if len(calls) < 2:
                continue
            findings.append(Finding(
                pattern_type="odd_hour_activity",
                typology="Nocturnal coordination pattern",
                severity="medium",
                confidence=round(min(0.55 + 0.1 * len(calls), 0.9), 3),
                summary=(
                    f"{a} and {b} exchanged {len(calls)} call(s) between 23:00 and 05:00 "
                    f"— hours inconsistent with legitimate business contact."
                ),
                members=[a, b],
                detail={"pair": [a, b], "odd_hour_calls": len(calls),
                        "timestamps": [c["ts"] for c in calls],
                        "total_duration_sec": sum(c["duration"] or 0 for c in calls)},
                recommendation="Correlate call timings with incident timelines in linked FIRs.",
            ))
        return findings

    # -- burst before incident -------------------------------------------
    def detect_burst_before_incident(self, window_hours: int = 72) -> list[Finding]:
        """
        Communication spike in the hours preceding a registered offence — the
        planning signature. Anchored on FIR dates so it is evidence-linked.
        """
        cases = [dict(r) for r in db.query(
            "SELECT fir_id, date_filed, title, crime_type, state FROM cases "
            "WHERE date_filed IS NOT NULL"
        )]
        if not cases or not self.calls:
            return []

        baseline = _calls_per_day(self.calls)
        findings: list[Finding] = []
        for case in cases:
            try:
                incident = datetime.fromisoformat(str(case["date_filed"])[:10])
            except ValueError:
                continue
            lo = incident - timedelta(hours=window_hours)
            window = [c for c in self.calls if lo <= _parse_ts(c["ts"]) <= incident]
            if len(window) < 3:
                continue
            days = max(window_hours / 24.0, 1.0)
            rate = len(window) / days
            if baseline > 0 and rate >= baseline * 2.0:
                participants = sorted({c["caller"] for c in window} | {c["callee"] for c in window})
                findings.append(Finding(
                    pattern_type="pre_incident_burst",
                    typology="Pre-offence communication surge (planning indicator)",
                    severity="high",
                    confidence=round(min(0.55 + 0.1 * (rate / max(baseline, 0.01)), 0.93), 3),
                    summary=(
                        f"Call volume in the {window_hours}h before {case['fir_id']} was "
                        f"{rate/max(baseline,0.01):.1f}x the corpus baseline "
                        f"({len(window)} calls among {len(participants)} numbers), "
                        f"indicating coordinated planning."
                    ),
                    members=participants,
                    detail={"fir_id": case["fir_id"], "crime_type": case["crime_type"],
                            "window_hours": window_hours, "calls_in_window": len(window),
                            "rate_per_day": round(rate, 2),
                            "baseline_per_day": round(baseline, 2),
                            "participants": participants},
                    recommendation="Attach this call cluster as circumstantial evidence of conspiracy (IPC 120B).",
                ))
        return findings

    # -- co-location ------------------------------------------------------
    def detect_co_location(self, minutes: int = 90) -> list[Finding]:
        """Two numbers on the same cell tower in the same window = physical meeting."""
        by_tower: dict[str, list[dict]] = defaultdict(list)
        for c in self.calls:
            if c["tower_id"]:
                by_tower[c["tower_id"]].append(c)

        findings: list[Finding] = []
        for tower, calls in by_tower.items():
            calls.sort(key=lambda c: _parse_ts(c["ts"]))
            for i, a in enumerate(calls):
                ta = _parse_ts(a["ts"])
                for b in calls[i + 1:]:
                    tb = _parse_ts(b["ts"])
                    if (tb - ta).total_seconds() / 60.0 > minutes:
                        break
                    parties_a = {a["caller"], a["callee"]}
                    parties_b = {b["caller"], b["callee"]}
                    distinct = parties_a ^ parties_b
                    if len(distinct) >= 2 and not (parties_a & parties_b):
                        findings.append(Finding(
                            pattern_type="co_location",
                            typology="Tower-dump co-location (probable physical meeting)",
                            severity="medium",
                            confidence=0.72,
                            summary=(
                                f"Numbers {sorted(parties_a)} and {sorted(parties_b)} were "
                                f"active on tower {tower} ({a['tower_name']}) within "
                                f"{int((tb-ta).total_seconds()//60)} minutes of each other."
                            ),
                            members=sorted(parties_a | parties_b),
                            detail={"tower_id": tower, "tower_name": a["tower_name"],
                                    "lat": a["lat"], "lon": a["lon"],
                                    "time_a": a["ts"], "time_b": b["ts"]},
                            recommendation="Request a full tower dump for this window to identify other attendees.",
                        ))
        # Deduplicate by member set + tower.
        unique: dict[tuple, Finding] = {}
        for f in findings:
            key = (tuple(f.members), f.detail.get("tower_id"))
            unique.setdefault(key, f)
        return list(unique.values())[:20]

    # -- one-way broadcast ------------------------------------------------
    def detect_one_way_broadcast(self) -> list[Finding]:
        out_c: Counter = Counter()
        in_c: Counter = Counter()
        for c in self.calls:
            out_c[c["caller"]] += 1
            in_c[c["callee"]] += 1
        findings: list[Finding] = []
        for number in set(out_c) | set(in_c):
            o, i = out_c[number], in_c[number]
            total = o + i
            if total >= 4 and (o == 0 or i == 0):
                direction = "only makes outgoing calls" if i == 0 else "only receives calls"
                findings.append(Finding(
                    pattern_type="one_way_traffic",
                    typology="Unidirectional call pattern (burner / broadcast handset)",
                    severity="medium",
                    confidence=0.75,
                    summary=(
                        f"Number {number} {direction} ({total} calls). Unidirectional "
                        f"traffic is characteristic of a dedicated instruction handset "
                        f"or a burner used for a single operational purpose."
                    ),
                    members=[number],
                    detail={"number": number, "outgoing": o, "incoming": i},
                    recommendation="Check subscriber KYC; burners typically carry false or reused documents.",
                ))
        return findings


# ===========================================================================
# Anomalies
# ===========================================================================
class AnomalyDetector:
    """
    Unsupervised outlier detection over per-entity behavioural features.

    Uses robust statistics (median/MAD) instead of mean/stdev because criminal
    datasets are heavily skewed and a few extreme actors would otherwise inflate
    the standard deviation and mask everyone else.
    """

    FEATURES = ("degree", "call_volume", "total_amount", "case_count",
                "odd_hour_ratio", "avg_call_duration")

    def __init__(self) -> None:
        self.features = self._build_features()

    def _build_features(self) -> dict[str, dict[str, float]]:
        feats: dict[str, dict[str, float]] = defaultdict(lambda: {k: 0.0 for k in self.FEATURES})

        for row in db.query(
            "SELECT e.entity_id, e.name, "
            "(SELECT COUNT(*) FROM relationships r WHERE r.source_id=e.entity_id "
            " OR r.target_id=e.entity_id) AS deg, "
            "(SELECT COUNT(*) FROM entity_cases ec WHERE ec.entity_id=e.entity_id) AS cases "
            "FROM entities e WHERE e.type='Person'"
        ):
            feats[row["entity_id"]]["degree"] = float(row["deg"] or 0)
            feats[row["entity_id"]]["case_count"] = float(row["cases"] or 0)

        # Phone-linked behaviour attributed back to the controlling person.
        phone_owner: dict[str, str] = {}
        for row in db.query(
            "SELECT r.source_id, e.name AS phone FROM relationships r "
            "JOIN entities e ON e.entity_id = r.target_id "
            "WHERE r.rel_type='USES_PHONE' AND e.type='Phone'"
        ):
            phone_owner[row["phone"]] = row["source_id"]

        call_stats: dict[str, list[dict]] = defaultdict(list)
        for row in db.query("SELECT caller, callee, ts, duration FROM cdr"):
            for number in (row["caller"], row["callee"]):
                owner = phone_owner.get(number)
                if owner:
                    call_stats[owner].append(dict(row))

        for owner, calls in call_stats.items():
            durations = [c["duration"] or 0 for c in calls]
            odd = sum(1 for c in calls
                      if _parse_ts(c["ts"]).hour < 5 or _parse_ts(c["ts"]).hour >= 23)
            feats[owner]["call_volume"] = float(len(calls))
            feats[owner]["avg_call_duration"] = float(statistics.mean(durations)) if durations else 0.0
            feats[owner]["odd_hour_ratio"] = odd / len(calls) if calls else 0.0

        account_owner: dict[str, str] = {}
        for row in db.query(
            "SELECT r.source_id, e.name AS acct FROM relationships r "
            "JOIN entities e ON e.entity_id = r.target_id "
            "WHERE r.rel_type='CONTROLS_ACCOUNT' AND e.type='BankAccount'"
        ):
            account_owner[row["acct"]] = row["source_id"]

        for row in db.query(
            "SELECT from_account, to_account, amount FROM transactions"
        ):
            for acct in (row["from_account"], row["to_account"]):
                owner = account_owner.get(acct)
                if owner:
                    feats[owner]["total_amount"] += float(row["amount"] or 0)

        return dict(feats)

    def run(self, z_threshold: float = 3.0) -> list[Finding]:
        if len(self.features) < 4:
            return []

        stats: dict[str, tuple[float, float]] = {}
        for feature in self.FEATURES:
            values = [v[feature] for v in self.features.values()]
            median = statistics.median(values)
            mad = statistics.median([abs(v - median) for v in values]) or 1e-9
            stats[feature] = (median, mad)

        findings: list[Finding] = []
        names = {r["entity_id"]: r["name"] for r in db.query("SELECT entity_id, name FROM entities")}

        for entity_id, values in self.features.items():
            deviations: dict[str, float] = {}
            for feature in self.FEATURES:
                median, mad = stats[feature]
                # 0.6745 scales MAD to be comparable with a standard deviation.
                z = 0.6745 * (values[feature] - median) / mad
                if abs(z) >= z_threshold:
                    deviations[feature] = round(z, 2)
            if not deviations:
                continue
            severity = "high" if max(abs(v) for v in deviations.values()) > 5 else "medium"
            worst = max(deviations.items(), key=lambda kv: abs(kv[1]))
            findings.append(Finding(
                pattern_type="behavioural_anomaly",
                typology="Robust multivariate outlier (median/MAD z-score)",
                severity=severity,
                confidence=round(min(0.5 + 0.08 * max(abs(v) for v in deviations.values()), 0.95), 3),
                summary=(
                    f"{names.get(entity_id, entity_id)} deviates sharply from corpus norms on "
                    f"{len(deviations)} behavioural feature(s); most extreme is "
                    f"'{worst[0]}' at {worst[1]:+.1f} robust standard deviations."
                ),
                members=[entity_id],
                detail={"entity_id": entity_id, "deviations": deviations,
                        "observed": {k: round(v, 2) for k, v in values.items()},
                        "corpus_median": {k: round(stats[k][0], 2) for k in self.FEATURES}},
                recommendation="Statistical outlier — verify manually before acting; may be a data artefact.",
            ))
        findings.sort(key=lambda f: -f.confidence)
        return findings


# ===========================================================================
# Orchestration
# ===========================================================================
def _resolve_member_to_entity_id(raw: str) -> str:
    """Map a raw account/phone/person string to its canonical entity_id if present."""
    from app.nlp import normalize as nz  # local import to avoid cycle
    # Try BankAccount, Phone, Vehicle, then generic fallback
    for typ, fn in (
        ("BankAccount", nz.normalize_account),
        ("Phone", nz.normalize_phone),
        ("Vehicle", nz.normalize_vehicle),
    ):
        try:
            norm = fn(raw) if fn else raw
        except Exception:
            norm = raw
        if not norm:
            continue
        row = db.query_one("SELECT entity_id FROM entities WHERE type=? AND normalized=?", (typ, norm))
        if row:
            return row["entity_id"]
    # Person fallback via normalized name
    try:
        norm = nz.normalize_name(raw) if raw else raw
        row = db.query_one("SELECT entity_id FROM entities WHERE type='Person' AND normalized=?", (norm,))
        if row:
            return row["entity_id"]
    except Exception:
        pass
    # Last resort: any entity with this normalized value
    row = db.query_one("SELECT entity_id FROM entities WHERE normalized=?", (str(raw).strip().upper(),))
    return row["entity_id"] if row else raw


def run_all_detectors(persist: bool = True) -> dict[str, Any]:
    findings: list[Finding] = []
    findings += FinancialPatternDetector().run()
    findings += CommunicationPatternDetector().run()
    findings += AnomalyDetector().run()

    # Resolve raw members (e.g. "30142567890") to canonical entity_ids (e.g. "ACC-00012")
    # so alerts and UI navigation use entity_id not raw account strings.
    for f in findings:
        if f.members:
            resolved = []
            for m in f.members:
                resolved.append(_resolve_member_to_entity_id(str(m)))
            # Keep raw for display/debug while members becomes entity_ids
            if raw_members := [m for m in f.members if m not in resolved]:
                f.detail.setdefault("raw_members", f.members)
            f.members = resolved

    if persist:
        db.execute("DELETE FROM patterns")
        db.executemany(
            "INSERT INTO patterns (pattern_type, typology, severity, confidence, "
            "summary, members, detail) VALUES (?,?,?,?,?,?,?)",
            [
                (f.pattern_type, f.typology, f.severity, f.confidence, f.summary,
                 db.jdump(f.members), db.jdump({**f.detail, "recommendation": f.recommendation}))
                for f in findings
            ],
        )

    by_type = Counter(f.pattern_type for f in findings)
    by_sev = Counter(f.severity for f in findings)
    return {
        "total": len(findings),
        "by_type": dict(by_type),
        "by_severity": dict(by_sev),
        "findings": [f.to_dict() for f in findings],
    }


# ---------------------------------------------------------------------------
def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:len("2024-01-01T00:00:00")], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime(1970, 1, 1)


def _time_span_days(txns: Sequence[dict]) -> int:
    times = sorted(_parse_ts(t["ts"]) for t in txns)
    return (times[-1] - times[0]).days if len(times) > 1 else 0


def _calls_per_day(calls: Iterable[dict]) -> float:
    calls = list(calls)
    if not calls:
        return 0.0
    times = sorted(_parse_ts(c["ts"]) for c in calls)
    span = max((times[-1] - times[0]).days, 1)
    return len(calls) / span
