"""
Explainable risk scoring.

Produces a 0–100 risk score per person with a full factor breakdown. There is no
opaque model here by design: an investigator (and a court) must be able to see
why a citizen was scored 82 instead of 30. Each factor is computed from evidence
that can be traced to a source record, and the API returns the contribution of
every factor in points.

Deliberate design decision: a black-box gradient-boosted model would score
marginally better on a benchmark, but would be unusable in an evidentiary
context and unsuitable for a government deployment where every adverse
inference must be justifiable. Where non-linearity helps, it is applied as an
explicit, documented curve rather than learned weights.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, date, timezone
from typing import Any

from app import db
from app.config import settings
from app.nlp import ipc

TODAY = date.today()


def _sigmoid_scale(value: float, midpoint: float, steepness: float = 1.0) -> float:
    """Saturating 0–1 curve: the 10th association matters less than the 2nd."""
    try:
        return 1.0 / (1.0 + math.exp(-steepness * (value - midpoint)))
    except OverflowError:
        return 0.0 if value < midpoint else 1.0


class RiskScorer:
    """Computes explainable risk for every Person entity."""

    def __init__(self, graph_metrics: dict[str, dict[str, float]] | None = None) -> None:
        self.graph_metrics = graph_metrics or {}
        self.people = [dict(r) for r in db.query(
            "SELECT entity_id, name, attributes FROM entities WHERE type='Person'"
        )]
        self._load_context()

    # ------------------------------------------------------------------
    def _load_context(self) -> None:
        # Cases per entity, with sections and dates.
        self.cases_by_entity: dict[str, list[dict]] = defaultdict(list)
        for row in db.query(
            "SELECT ec.entity_id, ec.role, c.fir_id, c.ipc_sections, c.date_filed, "
            "c.crime_type, c.priority, c.status FROM entity_cases ec "
            "JOIN cases c ON c.fir_id = ec.fir_id"
        ):
            self.cases_by_entity[row["entity_id"]].append({
                "fir_id": row["fir_id"],
                "role": row["role"],
                "sections": db.jload(row["ipc_sections"], []),
                "date_filed": row["date_filed"],
                "crime_type": row["crime_type"],
                "priority": row["priority"],
                "status": row["status"],
            })

        # Pattern findings per entity (financial/communication anomalies).
        self.patterns_by_entity: dict[str, list[dict]] = defaultdict(list)
        for row in db.query("SELECT pattern_type, severity, confidence, summary, members FROM patterns"):
            for member in db.jload(row["members"], []):
                self.patterns_by_entity[member].append(dict(row))

        # Map phone/account back to owner so signals attach to the person.
        self.owned: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for row in db.query(
            "SELECT r.source_id, r.rel_type, e.name, e.type FROM relationships r "
            "JOIN entities e ON e.entity_id = r.target_id "
            "WHERE r.rel_type IN ('USES_PHONE','CONTROLS_ACCOUNT','USES_VEHICLE')"
        ):
            self.owned[row["source_id"]][row["type"]].append(row["name"])

        # Transaction totals per person via owned accounts.
        self.txn_totals: dict[str, dict[str, float]] = defaultdict(
            lambda: {"in": 0.0, "out": 0.0, "flagged": 0.0, "count": 0.0})
        account_owner: dict[str, str] = {}
        for person, kinds in self.owned.items():
            for acct in kinds.get("BankAccount", []):
                account_owner[acct] = person
        for row in db.query(
            "SELECT from_account, to_account, amount, flagged FROM transactions"
        ):
            amount = float(row["amount"] or 0)
            src, dst = account_owner.get(row["from_account"]), account_owner.get(row["to_account"])
            if src:
                self.txn_totals[src]["out"] += amount
                self.txn_totals[src]["count"] += 1
                if row["flagged"]:
                    self.txn_totals[src]["flagged"] += amount
            if dst:
                self.txn_totals[dst]["in"] += amount
                self.txn_totals[dst]["count"] += 1
                if row["flagged"]:
                    self.txn_totals[dst]["flagged"] += amount

        # Call behaviour per person via owned phones.
        self.call_stats: dict[str, dict[str, float]] = defaultdict(
            lambda: {"count": 0.0, "odd_hour": 0.0, "distinct_peers": 0.0})
        phone_owner: dict[str, str] = {}
        for person, kinds in self.owned.items():
            for phone in kinds.get("Phone", []):
                phone_owner[phone] = person
        peers: dict[str, set[str]] = defaultdict(set)
        for row in db.query("SELECT caller, callee, ts FROM cdr"):
            for number, other in ((row["caller"], row["callee"]), (row["callee"], row["caller"])):
                owner = phone_owner.get(number)
                if not owner:
                    continue
                self.call_stats[owner]["count"] += 1
                peers[owner].add(other)
                hour = _hour_of(row["ts"])
                if hour is not None and (hour < 5 or hour >= 23):
                    self.call_stats[owner]["odd_hour"] += 1
        for owner, peer_set in peers.items():
            self.call_stats[owner]["distinct_peers"] = float(len(peer_set))

    # ------------------------------------------------------------------
    # Individual factors — each returns (normalised 0..1, evidence dict)
    # ------------------------------------------------------------------
    def _criminal_history(self, entity_id: str) -> tuple[float, dict]:
        cases = self.cases_by_entity.get(entity_id, [])
        as_accused = [c for c in cases if (c["role"] or "").lower() == "accused"]
        chargesheeted = [c for c in as_accused
                         if (c["status"] or "").lower() in ("charge sheet filed", "arrested", "convicted")]
        score = (
            _sigmoid_scale(len(as_accused), midpoint=1.5, steepness=1.1) * 0.7
            + _sigmoid_scale(len(chargesheeted), midpoint=0.8, steepness=1.4) * 0.3
        )
        return min(score, 1.0), {
            "cases_as_accused": len(as_accused),
            "cases_chargesheeted_or_arrested": len(chargesheeted),
            "fir_ids": [c["fir_id"] for c in as_accused],
        }

    def _offence_severity(self, entity_id: str) -> tuple[float, dict]:
        cases = self.cases_by_entity.get(entity_id, [])
        sections = [s for c in cases if (c["role"] or "").lower() == "accused"
                    for s in c["sections"]]
        if not sections:
            return 0.0, {"max_gravity": 0, "sections": []}
        gravity = ipc.gravity_of(sections)
        described = ipc.describe(sorted(set(sections)))
        return gravity / 10.0, {
            "max_gravity": gravity,
            "sections": described,
            "domains": ipc.domains_of(sections),
            "women_safety_offence": ipc.is_women_safety(sections),
        }

    def _network_position(self, entity_id: str) -> tuple[float, dict]:
        m = self.graph_metrics.get(entity_id)
        if not m:
            return 0.0, {"available": False}
        score = (
            0.35 * min(m.get("betweenness", 0.0) * 4, 1.0)
            + 0.25 * min(m.get("eigenvector", 0.0) * 3, 1.0)
            + 0.20 * min(m.get("degree_norm", 0.0), 1.0)
            + 0.20 * min(m.get("k_core_norm", 0.0), 1.0)
        )
        if m.get("is_articulation_point"):
            score = min(score + 0.12, 1.0)
        return min(score, 1.0), {
            "available": True,
            "degree": m.get("degree"),
            "betweenness": m.get("betweenness"),
            "eigenvector": m.get("eigenvector"),
            "k_core": m.get("k_core"),
            "is_articulation_point": m.get("is_articulation_point"),
        }

    def _financial_anomaly(self, entity_id: str) -> tuple[float, dict]:
        totals = self.txn_totals.get(entity_id)
        patterns = [p for p in self.patterns_by_entity.get(entity_id, [])
                    if p["pattern_type"] in ("structuring", "layering", "circular_flow",
                                             "fan_out", "fan_in", "rapid_passthrough",
                                             "dormant_burst")]
        if not totals and not patterns:
            return 0.0, {"flagged_amount": 0.0, "patterns": []}

        flagged = totals["flagged"] if totals else 0.0
        volume = (totals["in"] + totals["out"]) if totals else 0.0
        flagged_ratio = flagged / volume if volume else 0.0
        pattern_weight = min(len(patterns) / 3.0, 1.0)
        severity_boost = 0.2 if any(p["severity"] == "critical" for p in patterns) else 0.0

        score = min(0.45 * flagged_ratio + 0.45 * pattern_weight + severity_boost, 1.0)
        return score, {
            "total_volume_inr": round(volume, 2),
            "flagged_amount_inr": round(flagged, 2),
            "flagged_ratio": round(flagged_ratio, 3),
            "transaction_count": int(totals["count"]) if totals else 0,
            "patterns": [{"type": p["pattern_type"], "severity": p["severity"],
                          "summary": p["summary"]} for p in patterns],
        }

    def _communication_pattern(self, entity_id: str) -> tuple[float, dict]:
        stats = self.call_stats.get(entity_id)
        patterns = [p for p in self.patterns_by_entity.get(entity_id, [])
                    if p["pattern_type"] in ("hub_and_spoke", "odd_hour_activity",
                                             "pre_incident_burst", "one_way_traffic",
                                             "co_location")]
        if not stats and not patterns:
            return 0.0, {"call_count": 0, "patterns": []}

        count = stats["count"] if stats else 0.0
        odd_ratio = (stats["odd_hour"] / count) if stats and count else 0.0
        peers = stats["distinct_peers"] if stats else 0.0

        score = min(
            0.30 * _sigmoid_scale(count, midpoint=6, steepness=0.35)
            + 0.30 * min(odd_ratio * 2.5, 1.0)
            + 0.20 * _sigmoid_scale(peers, midpoint=3, steepness=0.8)
            + 0.20 * min(len(patterns) / 2.0, 1.0),
            1.0,
        )
        return score, {
            "call_count": int(count),
            "distinct_peers": int(peers),
            "odd_hour_ratio": round(odd_ratio, 3),
            "patterns": [{"type": p["pattern_type"], "summary": p["summary"]} for p in patterns],
        }

    def _recency(self, entity_id: str) -> tuple[float, dict]:
        cases = self.cases_by_entity.get(entity_id, [])
        dates = []
        for c in cases:
            parsed = _parse_date(c["date_filed"])
            if parsed:
                dates.append(parsed)
        if not dates:
            return 0.0, {"latest_case": None, "days_since": None}
        latest = max(dates)
        days = (TODAY - latest).days
        # Exponential decay with a 2-year half-life.
        score = math.exp(-days / 730.0)
        return min(score, 1.0), {"latest_case": latest.isoformat(), "days_since": days}

    # ------------------------------------------------------------------
    def score_entity(self, entity_id: str, name: str = "") -> dict:
        factors = {
            "criminal_history": self._criminal_history(entity_id),
            "network_position": self._network_position(entity_id),
            "financial_anomaly": self._financial_anomaly(entity_id),
            "communication_pattern": self._communication_pattern(entity_id),
            "offence_severity": self._offence_severity(entity_id),
            "recency": self._recency(entity_id),
        }
        weights = settings.RISK_WEIGHTS
        breakdown: list[dict] = []
        total = 0.0
        for key, (normalised, evidence) in factors.items():
            points = round(weights[key] * normalised * 100, 2)
            total += points
            breakdown.append({
                "factor": key,
                "label": _FACTOR_LABELS[key],
                "weight": weights[key],
                "normalised_value": round(normalised, 4),
                "points_contributed": points,
                "max_points": round(weights[key] * 100, 2),
                "evidence": evidence,
                "explanation": _FACTOR_EXPLAIN[key](normalised, evidence),
            })

        score = round(min(total, 100.0), 2)
        breakdown.sort(key=lambda b: -b["points_contributed"])
        return {
            "entity_id": entity_id,
            "name": name,
            "risk_score": score,
            "risk_band": risk_band(score),
            "factors": breakdown,
            "top_drivers": [b["factor"] for b in breakdown[:3] if b["points_contributed"] > 0],
            "narrative": _narrative(name or entity_id, score, breakdown),
            "computed_at": datetime.now(timezone.utc).replace(tzinfo=None)
                           .isoformat(timespec="seconds") + "Z",
        }

    def score_all(self, persist: bool = True) -> list[dict]:
        results = [self.score_entity(p["entity_id"], p["name"]) for p in self.people]
        if persist:
            db.executemany(
                "UPDATE entities SET risk_score=?, risk_factors=? WHERE entity_id=?",
                [(r["risk_score"], db.jdump(r["factors"]), r["entity_id"]) for r in results],
            )
        results.sort(key=lambda r: -r["risk_score"])
        return results


# ---------------------------------------------------------------------------
_FACTOR_LABELS = {
    "criminal_history": "Criminal History",
    "network_position": "Network Position",
    "financial_anomaly": "Financial Anomaly",
    "communication_pattern": "Communication Behaviour",
    "offence_severity": "Offence Severity",
    "recency": "Recency of Activity",
}


def _explain_history(v: float, e: dict) -> str:
    n = e.get("cases_as_accused", 0)
    if not n:
        return "No FIR records name this person as accused."
    return (f"Named as accused in {n} FIR(s), of which "
            f"{e.get('cases_chargesheeted_or_arrested', 0)} progressed to arrest or charge sheet.")


def _explain_network(v: float, e: dict) -> str:
    if not e.get("available"):
        return "Not present in the relationship graph."
    parts = [f"{e.get('degree', 0)} direct associations",
             f"betweenness {e.get('betweenness', 0):.4f}",
             f"k-core {e.get('k_core', 0)}"]
    text = "Occupies a position with " + ", ".join(parts) + "."
    if e.get("is_articulation_point"):
        text += " Acts as an articulation point holding subgroups together."
    return text


def _explain_financial(v: float, e: dict) -> str:
    if not e.get("total_volume_inr") and not e.get("patterns"):
        return "No linked financial activity in the ingested ledger."
    return (f"Rs {e.get('flagged_amount_inr', 0):,.0f} of Rs {e.get('total_volume_inr', 0):,.0f} "
            f"traced volume is flagged ({e.get('flagged_ratio', 0)*100:.0f}%), with "
            f"{len(e.get('patterns', []))} laundering typology match(es).")


def _explain_comms(v: float, e: dict) -> str:
    if not e.get("call_count"):
        return "No call detail records linked to this person."
    return (f"{e.get('call_count')} calls across {e.get('distinct_peers')} distinct peers, "
            f"{e.get('odd_hour_ratio', 0)*100:.0f}% during 23:00–05:00, with "
            f"{len(e.get('patterns', []))} behavioural pattern match(es).")


def _explain_severity(v: float, e: dict) -> str:
    if not e.get("max_gravity"):
        return "No charged sections recorded."
    domains = ", ".join(e.get("domains", []) or ["Unclassified"])
    text = (f"Gravest charged offence rates {e.get('max_gravity')}/10 "
            f"across domain(s): {domains}.")
    if e.get("women_safety_offence"):
        text += " Includes an offence within the Women Safety Division mandate."
    return text


def _explain_recency(v: float, e: dict) -> str:
    if not e.get("latest_case"):
        return "No dated case activity."
    return (f"Most recent recorded case activity {e.get('days_since')} days ago "
            f"({e.get('latest_case')}).")


_FACTOR_EXPLAIN = {
    "criminal_history": _explain_history,
    "network_position": _explain_network,
    "financial_anomaly": _explain_financial,
    "communication_pattern": _explain_comms,
    "offence_severity": _explain_severity,
    "recency": _explain_recency,
}


def risk_band(score: float) -> str:
    if score >= 75:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 35:
        return "Moderate"
    if score >= 15:
        return "Low"
    return "Minimal"


def _narrative(name: str, score: float, breakdown: list[dict]) -> str:
    drivers = [b for b in breakdown if b["points_contributed"] > 0][:3]
    if not drivers:
        return f"{name} carries a minimal risk score of {score}: no corroborating signals in the ingested data."
    driver_text = "; ".join(
        f"{b['label']} contributing {b['points_contributed']} of {b['max_points']} points"
        for b in drivers
    )
    return (f"{name} is assessed at {score}/100 ({risk_band(score)}). "
            f"The score is driven primarily by {driver_text}. "
            f"Every component is traceable to source records and can be independently verified.")


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "")[:10]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _hour_of(value: Any) -> int | None:
    text = str(value or "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).hour
        except ValueError:
            continue
    return None
