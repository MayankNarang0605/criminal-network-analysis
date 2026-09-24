"""
Women Safety Division module.

The problem statement is owned by NCRB's Women Safety Division specifically, so
generic criminal-network analysis leaves the department's actual mandate
unaddressed. This module adds the analysis that division needs:

  * Isolation of cases within the women-safety legal mandate (IPC/BNS/POCSO/IT Act)
  * Repeat-offender detection across jurisdictions — the pattern that matters most
    for stalking and harassment, where each individual FIR looks minor but the
    aggregate is a serial offender
  * Trafficking corridor inference from co-occurring locations across FIRs
  * Escalation-risk scoring: harassment/stalking histories that statistically
    precede grave offences, which is where early intervention is possible
  * District-level hotspot aggregation for resource allocation
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app import db
from app.nlp import ipc

# Offences whose presence in a person's history indicates escalation risk toward
# a graver offence. Ordered by position on the escalation ladder.
ESCALATION_LADDER = [
    ("509", 1), ("354A", 2), ("354D", 3), ("354", 4), ("354B", 5),
    ("506", 5), ("326A", 8), ("376", 9), ("304B", 9), ("302", 10),
]
TRAFFICKING_SECTIONS = {"370", "370A", "366", "366A", "366B", "363", "372", "373"}


def _women_safety_cases() -> list[dict]:
    out: list[dict] = []
    for row in db.query(
        "SELECT fir_id, title, description, station, district, state, ipc_sections, "
        "crime_type, status, priority, date_filed FROM cases"
    ):
        sections = db.jload(row["ipc_sections"], [])
        if not ipc.is_women_safety(sections):
            continue
        item = dict(row)
        item["ipc_sections"] = sections
        item["section_detail"] = ipc.describe(sections)
        item["max_gravity"] = ipc.gravity_of(sections)
        out.append(item)
    return out


def overview() -> dict[str, Any]:
    cases = _women_safety_cases()
    total_cases = db.scalar("SELECT COUNT(*) FROM cases")

    by_state = Counter(c["state"] for c in cases if c["state"])
    by_district = Counter(c["district"] for c in cases if c["district"])
    by_domain: Counter = Counter()
    for c in cases:
        for d in ipc.domains_of(c["ipc_sections"]):
            by_domain[d] += 1
    by_status = Counter(c["status"] for c in cases if c["status"])

    trafficking = [c for c in cases
                   if set(c["ipc_sections"]) & TRAFFICKING_SECTIONS]

    return {
        "mandate": "NCRB Women Safety Division",
        "cases_in_mandate": len(cases),
        "total_cases_in_system": total_cases,
        "mandate_share_pct": round(len(cases) / total_cases * 100, 2) if total_cases else 0.0,
        "trafficking_cases": len(trafficking),
        "grave_cases": len([c for c in cases if c["max_gravity"] >= 9]),
        "pending_investigation": by_status.get("Under Investigation", 0),
        "by_state": dict(by_state.most_common()),
        "by_district": dict(by_district.most_common(15)),
        "by_offence_domain": dict(by_domain.most_common()),
        "by_status": dict(by_status),
        "cases": [
            {
                "fir_id": c["fir_id"], "district": c["district"], "state": c["state"],
                "date_filed": c["date_filed"], "status": c["status"],
                "priority": c["priority"], "max_gravity": c["max_gravity"],
                "sections": c["ipc_sections"],
                "offences": [s["description"] for s in c["section_detail"]
                             if s["women_safety"]],
            }
            for c in sorted(cases, key=lambda x: -x["max_gravity"])
        ],
    }


def repeat_offenders(min_cases: int = 2) -> list[dict]:
    """
    Persons named as accused in multiple women-safety FIRs. Cross-jurisdictional
    repetition is flagged separately because that is precisely the case that a
    single police station cannot see on its own.
    """
    ws_case_ids = {c["fir_id"] for c in _women_safety_cases()}
    if not ws_case_ids:
        return []

    per_person: dict[str, dict] = defaultdict(
        lambda: {"cases": [], "states": set(), "districts": set(), "sections": set()})

    placeholders = ",".join("?" * len(ws_case_ids))
    for row in db.query(
        f"SELECT ec.entity_id, e.name, e.risk_score, e.kingpin_score, c.fir_id, "
        f"c.state, c.district, c.ipc_sections, c.date_filed, c.status "
        f"FROM entity_cases ec "
        f"JOIN entities e ON e.entity_id = ec.entity_id "
        f"JOIN cases c ON c.fir_id = ec.fir_id "
        f"WHERE ec.role = 'accused' AND e.type='Person' AND c.fir_id IN ({placeholders})",
        list(ws_case_ids),
    ):
        item = per_person[row["entity_id"]]
        item["name"] = row["name"]
        item["risk_score"] = row["risk_score"]
        item["kingpin_score"] = row["kingpin_score"]
        item["cases"].append({
            "fir_id": row["fir_id"], "state": row["state"], "district": row["district"],
            "date_filed": row["date_filed"], "status": row["status"],
            "sections": db.jload(row["ipc_sections"], []),
        })
        if row["state"]:
            item["states"].add(row["state"])
        if row["district"]:
            item["districts"].add(row["district"])
        item["sections"] |= set(db.jload(row["ipc_sections"], []))

    out: list[dict] = []
    for entity_id, data in per_person.items():
        if len(data["cases"]) < min_cases:
            continue
        gravity = ipc.gravity_of(sorted(data["sections"]))
        cross = len(data["states"]) > 1
        out.append({
            "entity_id": entity_id,
            "name": data.get("name"),
            "risk_score": data.get("risk_score"),
            "kingpin_score": data.get("kingpin_score"),
            "case_count": len(data["cases"]),
            "states": sorted(data["states"]),
            "districts": sorted(data["districts"]),
            "cross_jurisdictional": cross,
            "max_gravity": gravity,
            "sections_involved": sorted(data["sections"]),
            "cases": sorted(data["cases"], key=lambda c: str(c["date_filed"])),
            "priority": ("critical" if cross and gravity >= 8 else
                         "high" if cross or gravity >= 8 else "medium"),
            "assessment": (
                f"{data.get('name')} is named as accused in {len(data['cases'])} "
                f"women-safety cases across {len(data['states'])} state(s). "
                + ("Cross-jurisdictional repetition means no single police station "
                   "sees the full pattern; recommend consolidated investigation. "
                   if cross else "")
                + f"Gravest section carries gravity {gravity}/10."
            ),
        })
    out.sort(key=lambda r: (-r["case_count"], -r["max_gravity"]))
    return out


def escalation_risk() -> list[dict]:
    """
    Identify persons whose recorded offence history sits on the escalation ladder
    below a graver offence. The purpose is preventive: an actor with repeated
    stalking and intimidation entries but no grave offence yet is exactly where
    intervention changes the outcome.
    """
    ladder = dict(ESCALATION_LADDER)
    per_person: dict[str, dict] = defaultdict(
        lambda: {"sections": set(), "cases": [], "name": None})

    for row in db.query(
        "SELECT ec.entity_id, e.name, c.fir_id, c.ipc_sections, c.date_filed "
        "FROM entity_cases ec "
        "JOIN entities e ON e.entity_id = ec.entity_id "
        "JOIN cases c ON c.fir_id = ec.fir_id "
        "WHERE ec.role='accused' AND e.type='Person'"
    ):
        sections = db.jload(row["ipc_sections"], [])
        relevant = [s for s in sections if s in ladder]
        if not relevant:
            continue
        item = per_person[row["entity_id"]]
        item["name"] = row["name"]
        item["sections"] |= set(relevant)
        item["cases"].append({"fir_id": row["fir_id"], "date_filed": row["date_filed"],
                              "sections": relevant})

    out: list[dict] = []
    for entity_id, data in per_person.items():
        rungs = sorted((ladder[s], s) for s in data["sections"])
        if not rungs:
            continue
        current = rungs[-1][0]
        precursors = [s for level, s in rungs if level <= 5]
        # Risk is highest where there are multiple low-rung offences but no grave
        # offence yet: the pattern is established, the escalation has not happened.
        if current >= 8:
            band, score = "already_grave", 95.0
        elif len(precursors) >= 2:
            band, score = "high_escalation_risk", 60.0 + 10.0 * min(len(precursors), 3)
        else:
            band, score = "monitor", 30.0 + 5.0 * current

        out.append({
            "entity_id": entity_id,
            "name": data["name"],
            "current_ladder_position": current,
            "sections_recorded": sorted(data["sections"]),
            "precursor_offences": precursors,
            "case_count": len(data["cases"]),
            "escalation_band": band,
            "escalation_score": round(min(score, 100.0), 1),
            "cases": data["cases"],
            "recommendation": (
                "Grave offence already recorded — prioritise prosecution support."
                if band == "already_grave" else
                ("Multiple precursor offences recorded without escalation to a grave "
                 "offence. Statistically this is the intervention window: recommend "
                 "preventive action under Section 126 BNSS and victim protection review.")
                if band == "high_escalation_risk" else
                "Single recorded precursor offence — routine monitoring."
            ),
        })
    out.sort(key=lambda r: -r["escalation_score"])
    return out


def trafficking_corridors(min_shared: int = 2) -> list[dict]:
    """
    Infer trafficking corridors: pairs of locations that recur together across
    trafficking FIRs. A corridor is operationally actionable in a way that
    individual case locations are not.
    """
    cases = [c for c in _women_safety_cases()
             if set(c["ipc_sections"]) & TRAFFICKING_SECTIONS]
    if not cases:
        return []

    corridor: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"cases": [], "states": set()})

    for case in cases:
        raw = db.query_one("SELECT raw FROM cases WHERE fir_id=?", (case["fir_id"],))
        payload = db.jload(raw["raw"] if raw else "{}", {})
        locations = sorted({str(l) for l in (payload.get("locations_mentioned") or [])})
        locations = locations or ([case["district"]] if case["district"] else [])
        for i in range(len(locations)):
            for j in range(i + 1, len(locations)):
                key = (locations[i], locations[j])
                corridor[key]["cases"].append(case["fir_id"])
                if case["state"]:
                    corridor[key]["states"].add(case["state"])

    out = []
    for (a, b), data in corridor.items():
        if len(data["cases"]) < min_shared:
            continue
        out.append({
            "origin": a,
            "destination": b,
            "case_count": len(data["cases"]),
            "fir_ids": sorted(set(data["cases"])),
            "states": sorted(data["states"]),
            "interstate": len(data["states"]) > 1,
            "assessment": (
                f"{a} and {b} co-occur in {len(data['cases'])} trafficking case(s)"
                + (", spanning multiple states — recommend coordinated interception "
                   "and AHTU briefing." if len(data["states"]) > 1
                   else " — recommend local source/destination verification.")
            ),
        })
    out.sort(key=lambda c: -c["case_count"])
    return out


def hotspots() -> list[dict]:
    """District-level aggregation for resource allocation."""
    cases = _women_safety_cases()
    per_district: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"cases": 0, "gravity_sum": 0, "grave": 0, "sections": Counter(),
                 "pending": 0})
    for c in cases:
        key = (c["district"] or "Unknown", c["state"] or "Unknown")
        item = per_district[key]
        item["cases"] += 1
        item["gravity_sum"] += c["max_gravity"]
        if c["max_gravity"] >= 9:
            item["grave"] += 1
        if (c["status"] or "") == "Under Investigation":
            item["pending"] += 1
        for s in c["ipc_sections"]:
            item["sections"][s] += 1

    out = []
    for (district, state), item in per_district.items():
        avg_gravity = item["gravity_sum"] / item["cases"]
        # Composite hotspot index: volume, severity and backlog together.
        index = min(item["cases"] * 8 + avg_gravity * 4 + item["grave"] * 10 +
                    item["pending"] * 3, 100.0)
        out.append({
            "district": district,
            "state": state,
            "case_count": item["cases"],
            "grave_case_count": item["grave"],
            "pending_investigation": item["pending"],
            "avg_gravity": round(avg_gravity, 2),
            "hotspot_index": round(index, 1),
            "top_sections": [s for s, _ in item["sections"].most_common(4)],
            "band": ("critical" if index >= 70 else "high" if index >= 45
                     else "moderate" if index >= 25 else "low"),
        })
    out.sort(key=lambda h: -h["hotspot_index"])
    return out


def dashboard() -> dict[str, Any]:
    repeats = repeat_offenders()
    escalation = escalation_risk()
    return {
        "overview": overview(),
        "repeat_offenders": repeats[:20],
        "repeat_offender_count": len(repeats),
        "cross_jurisdictional_offenders": len([r for r in repeats if r["cross_jurisdictional"]]),
        "escalation_watchlist": [e for e in escalation
                                 if e["escalation_band"] == "high_escalation_risk"][:20],
        "trafficking_corridors": trafficking_corridors(),
        "hotspots": hotspots()[:15],
    }
