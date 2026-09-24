"""
CDR & Telecom Intelligence Service.
Implements deep forensic call detail record analysis answering:
"What communication patterns exist between people, devices and locations?"

Features:
- Directional analysis (incoming/outgoing), call duration, frequency, time, tower, SMS vs voice
- Frequent communication detection (A <-> B with call counts, total hours, breakdown)
- Hidden connector detection (A -> X, B -> X, C -> X bridging disconnected parties)
- Temporal communication surges (sharp escalation leading up to incident)
- Location correlation & tower co-location clustering
- Killer feature: Unified Forensic Communication Timeline (calls, movements, incident markers)
- Common numbers & multi-SIM burner devices
"""
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.models.evidence import (
    CDR, Phone, SimCard, Device, PhoneSimImeiDevice,
    Person, Location, LocationEvent, FIR, Case
)


def format_duration(seconds: int) -> str:
    """Format seconds into readable hours, minutes, seconds."""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    rem_sec = seconds % 60
    if minutes < 60:
        return f"{minutes}m {rem_sec}s" if rem_sec else f"{minutes}m"
    hours = minutes // 60
    rem_min = minutes % 60
    return f"{hours}h {rem_min}m" if rem_min else f"{hours}h"


def analyze_case_cdr(db: Session, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes complete CDR intelligence analysis for a given case (or all cases if None).
    """
    # ── 1. Load Reference Entities ───────────────────────────────────────────
    persons = {p.person_id: p for p in db.query(Person).all()}
    phones = {ph.phone_id: ph for ph in db.query(Phone).all()}
    locations = {loc.location_id: loc for loc in db.query(Location).all()}
    devices = {d.device_id: d for d in db.query(Device).all()}

    # Phone -> Person mapping
    phone_to_person = {}
    for ph in phones.values():
        if ph.person_id and ph.person_id in persons:
            phone_to_person[ph.phone_id] = persons[ph.person_id]

    def resolve_party(phone_id: str) -> Dict[str, Any]:
        ph = phones.get(phone_id)
        number = ph.number if ph else phone_id
        person = phone_to_person.get(phone_id)
        return {
            "phone_id": phone_id,
            "number": number,
            "person_id": person.person_id if person else None,
            "person_name": person.full_name if person else f"Subscriber {number}",
            "alias": person.alias if person else None,
            "label": f"{person.full_name} ({number})" if person else number,
        }

    def resolve_loc(loc_id: Optional[str]) -> Dict[str, Any]:
        if not loc_id or loc_id not in locations:
            return {"location_id": loc_id, "name": loc_id or "Unknown Tower", "area": "Unknown", "city": ""}
        loc = locations[loc_id]
        return {
            "location_id": loc_id,
            "name": loc.location_name or loc_id,
            "area": loc.area or "",
            "city": loc.city or "",
            "lat": loc.latitude,
            "lon": loc.longitude,
        }

    # ── 2. Filter CDRs and Incident Info ─────────────────────────────────────
    cdr_query = db.query(CDR)
    if case_id:
        cdr_query = cdr_query.filter(CDR.case_id == case_id)
    cdrs: List[CDR] = cdr_query.order_by(CDR.timestamp.asc()).all()

    # Case & FIR Incident info
    target_case = db.query(Case).filter(Case.case_id == case_id).first() if case_id else None
    firs = db.query(FIR).filter(FIR.case_id == case_id).all() if case_id else db.query(FIR).all()
    primary_fir = firs[0] if firs else None

    incident_timestamp = None
    if primary_fir and primary_fir.incident_date:
        incident_timestamp = primary_fir.incident_date
    elif target_case and target_case.date_range_start:
        incident_timestamp = target_case.date_range_start

    # ── 3. High-level Summary Metrics ───────────────────────────────────────
    total_calls = len(cdrs)
    total_duration_sec = sum(c.duration_seconds or 0 for c in cdrs)
    voice_calls = sum(1 for c in cdrs if (c.call_type or "").lower() == "voice")
    sms_calls = sum(1 for c in cdrs if (c.call_type or "").lower() == "sms")
    other_calls = total_calls - voice_calls - sms_calls

    outgoing_counts = defaultdict(int)
    incoming_counts = defaultdict(int)
    hourly_distribution = defaultdict(int)
    daily_distribution = defaultdict(int)
    tower_counts = defaultdict(int)

    for c in cdrs:
        outgoing_counts[c.caller_phone_id] += 1
        incoming_counts[c.receiver_phone_id] += 1
        if c.tower_location_id:
            tower_counts[c.tower_location_id] += 1

        if c.timestamp:
            try:
                dt = datetime.fromisoformat(c.timestamp.replace("Z", ""))
                hourly_distribution[dt.hour] += 1
                daily_distribution[dt.strftime("%Y-%m-%d")] += 1
            except Exception:
                pass

    top_towers = []
    for tid, count in sorted(tower_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        t_info = resolve_loc(tid)
        top_towers.append({**t_info, "call_count": count})

    # ── 4. Detector 1: Frequent Communication (A <-> B) ──────────────────────
    pair_calls = defaultdict(list)
    for c in cdrs:
        pair_key = tuple(sorted([c.caller_phone_id, c.receiver_phone_id]))
        pair_calls[pair_key].append(c)

    frequent_pairs = []
    for (p1_id, p2_id), call_list in pair_calls.items():
        call_count = len(call_list)
        total_sec = sum(c.duration_seconds or 0 for c in call_list)
        p1_to_p2 = sum(1 for c in call_list if c.caller_phone_id == p1_id)
        p2_to_p1 = sum(1 for c in call_list if c.caller_phone_id == p2_id)
        voice_cnt = sum(1 for c in call_list if (c.call_type or "").lower() == "voice")
        sms_cnt = sum(1 for c in call_list if (c.call_type or "").lower() == "sms")

        p1_info = resolve_party(p1_id)
        p2_info = resolve_party(p2_id)

        timestamps = [c.timestamp for c in call_list if c.timestamp]
        first_contact = min(timestamps) if timestamps else None
        last_contact = max(timestamps) if timestamps else None

        severity = "CRITICAL" if call_count >= 8 or total_sec >= 3600 else "HIGH" if call_count >= 4 else "MEDIUM"

        frequent_pairs.append({
            "party_a": p1_info,
            "party_b": p2_info,
            "total_calls": call_count,
            "total_duration_seconds": total_sec,
            "total_duration_formatted": format_duration(total_sec),
            "average_duration_seconds": round(total_sec / max(call_count, 1), 1),
            "a_to_b_calls": p1_to_p2,
            "b_to_a_calls": p2_to_p1,
            "voice_count": voice_cnt,
            "sms_count": sms_cnt,
            "first_contact": first_contact,
            "last_contact": last_contact,
            "severity": severity,
            "explanation": (
                f"Sustained communication channel between {p1_info['label']} and {p2_info['label']} "
                f"with {call_count} calls ({format_duration(total_sec)} total). "
                f"Directional split: {p1_to_p2} outgoing vs {p2_to_p1} incoming."
            )
        })

    frequent_pairs.sort(key=lambda x: (x["total_calls"], x["total_duration_seconds"]), reverse=True)

    # ── 5. Detector 2: Hidden Connector (A -> X, B -> X, C -> X) ─────────────
    # Build direct adjacency matrix for all phone numbers
    adjacency = defaultdict(set)
    for (p1_id, p2_id) in pair_calls.keys():
        adjacency[p1_id].add(p2_id)
        adjacency[p2_id].add(p1_id)

    hidden_connectors = []
    for node, neighbors in adjacency.items():
        if len(neighbors) >= 3:
            # Check how many pairs of neighbors do NOT communicate with each other
            neighbor_list = list(neighbors)
            disconnected_pairs = []
            connected_pairs_count = 0
            total_possible_pairs = 0

            for i in range(len(neighbor_list)):
                for j in range(i + 1, len(neighbor_list)):
                    total_possible_pairs += 1
                    na = neighbor_list[i]
                    nb = neighbor_list[j]
                    if nb in adjacency[na]:
                        connected_pairs_count += 1
                    else:
                        disconnected_pairs.append((resolve_party(na), resolve_party(nb)))

            disconnection_rate = (len(disconnected_pairs) / total_possible_pairs) if total_possible_pairs > 0 else 0

            # If neighbors mostly do not speak to each other, node is a Hidden Connector / Broker
            if disconnection_rate >= 0.50 and len(disconnected_pairs) >= 2:
                node_info = resolve_party(node)
                hidden_connectors.append({
                    "connector": node_info,
                    "connected_parties_count": len(neighbors),
                    "connected_parties": [resolve_party(n) for n in neighbor_list],
                    "disconnected_pairs_count": len(disconnected_pairs),
                    "disconnection_rate": round(disconnection_rate * 100, 1),
                    "sample_bridged_pairs": [
                        {"party_1": p[0]["label"], "party_2": p[1]["label"]}
                        for p in disconnected_pairs[:5]
                    ],
                    "severity": "CRITICAL" if len(disconnected_pairs) >= 4 else "HIGH",
                    "confidence": round(min(0.96, 0.70 + disconnection_rate * 0.25), 2),
                    "explanation": (
                        f"{node_info['label']} acts as a central hub/connector between {len(neighbors)} "
                        f"distinct parties who exhibit {round(disconnection_rate * 100)}% non-intercommunication. "
                        f"Characteristic signature of a syndicate dispatcher, coordinator, or hidden bridge."
                    )
                })

    hidden_connectors.sort(key=lambda x: x["disconnected_pairs_count"], reverse=True)

    # ── 6. Detector 3: Temporal Communication (Pre-Incident Surge) ───────────
    # Analyze call volume relative to incident date
    temporal_surges = []
    if incident_timestamp:
        try:
            inc_dt = datetime.fromisoformat(incident_timestamp.replace("Z", ""))
            inc_date_str = inc_dt.strftime("%Y-%m-%d")

            # Calculate daily rates before incident
            pre_incident_days = defaultdict(int)
            baseline_days = defaultdict(int)

            for c in cdrs:
                if not c.timestamp:
                    continue
                try:
                    c_dt = datetime.fromisoformat(c.timestamp.replace("Z", ""))
                    days_diff = (inc_dt.date() - c_dt.date()).days
                    if 0 <= days_diff <= 3:
                        pre_incident_days[c_dt.strftime("%Y-%m-%d")] += 1
                    elif days_diff > 3:
                        baseline_days[c_dt.strftime("%Y-%m-%d")] += 1
                except Exception:
                    pass

            baseline_avg = (sum(baseline_days.values()) / max(len(baseline_days), 1)) if baseline_days else 1.0
            surge_avg = (sum(pre_incident_days.values()) / max(len(pre_incident_days), 1)) if pre_incident_days else sum(daily_distribution.values()) / max(len(daily_distribution), 1)

            surge_multiplier = round(surge_avg / max(baseline_avg, 0.5), 2)
            if surge_multiplier >= 1.5 or sum(pre_incident_days.values()) >= 10:
                temporal_surges.append({
                    "detector_name": "CDR_PRE_INCIDENT_SURGE",
                    "incident_date": inc_date_str,
                    "baseline_daily_average": round(baseline_avg, 1),
                    "pre_incident_daily_average": round(surge_avg, 1),
                    "surge_multiplier": surge_multiplier,
                    "total_surge_calls": sum(pre_incident_days.values()),
                    "severity": "CRITICAL" if surge_multiplier >= 2.5 else "HIGH",
                    "confidence": round(min(0.95, 0.75 + surge_multiplier * 0.05), 2),
                    "explanation": (
                        f"Communication frequency surged by {surge_multiplier}x within the 72 hours "
                        f"immediately preceding the incident ({inc_date_str}), jumping from an average of "
                        f"{round(baseline_avg, 1)} calls/day to {round(surge_avg, 1)} calls/day. "
                        f"Strong indicator of operational mobilization."
                    ),
                    "daily_timeline": [
                        {"date": d, "calls": c} for d, c in sorted(daily_distribution.items())
                    ]
                })
        except Exception:
            pass

    # If no specific incident date, identify highest burst day
    if not temporal_surges and daily_distribution:
        max_date, max_count = max(daily_distribution.items(), key=lambda x: x[1])
        avg_calls = sum(daily_distribution.values()) / max(len(daily_distribution), 1)
        if max_count >= avg_calls * 1.5:
            temporal_surges.append({
                "detector_name": "CDR_TEMPORAL_PEAK_SPIKE",
                "incident_date": max_date,
                "baseline_daily_average": round(avg_calls, 1),
                "pre_incident_daily_average": max_count,
                "surge_multiplier": round(max_count / max(avg_calls, 1), 2),
                "total_surge_calls": max_count,
                "severity": "HIGH",
                "confidence": 0.88,
                "explanation": (
                    f"Sharp telecom burst observed on {max_date} with {max_count} calls "
                    f"({round(max_count / max(avg_calls, 1), 1)}x the daily baseline of {round(avg_calls, 1)})."
                ),
                "daily_timeline": [
                    {"date": d, "calls": c} for d, c in sorted(daily_distribution.items())
                ]
            })

    # ── 7. Detector 4: Location Correlation (Cell Tower Co-location) ─────────
    # Group calls by tower and time bucket (hourly)
    tower_time_parties = defaultdict(set)
    tower_time_calls = defaultdict(list)

    for c in cdrs:
        if c.tower_location_id and c.timestamp:
            time_bucket = c.timestamp[:13]  # YYYY-MM-DDTHH
            key = (c.tower_location_id, time_bucket)
            tower_time_parties[key].add(c.caller_phone_id)
            tower_time_parties[key].add(c.receiver_phone_id)
            tower_time_calls[key].append(c)

    # Also incorporate physical LocationEvents if available
    loc_events_query = db.query(LocationEvent)
    if case_id:
        loc_events_query = loc_events_query.filter(LocationEvent.case_id == case_id)
    for le in loc_events_query.all():
        if le.location_id and le.timestamp:
            time_bucket = le.timestamp[:13]
            key = (le.location_id, time_bucket)
            # Find phone for person if possible
            for ph_id, p in phone_to_person.items():
                if p.person_id == le.person_id:
                    tower_time_parties[key].add(ph_id)
            tower_time_calls[key].append(le)

    location_correlations = []
    for (t_id, t_bucket), p_set in tower_time_parties.items():
        if len(p_set) >= 2:
            loc_info = resolve_loc(t_id)
            parties_resolved = [resolve_party(pid) for pid in p_set]
            n_events = len(tower_time_calls[(t_id, t_bucket)])

            # Format time bucket
            display_time = t_bucket.replace("T", " ") + ":00"

            location_correlations.append({
                "tower_id": t_id,
                "tower_name": loc_info["name"],
                "area": loc_info["area"],
                "city": loc_info["city"],
                "timestamp_window": display_time,
                "distinct_entities_count": len(p_set),
                "entities": parties_resolved,
                "event_count": n_events,
                "severity": "CRITICAL" if len(p_set) >= 3 else "HIGH",
                "confidence": 0.92,
                "explanation": (
                    f"{len(p_set)} distinct phones/suspects ({', '.join(p['label'] for p in parties_resolved[:3])}) "
                    f"were concurrently active at cell tower {loc_info['name']} ({t_id}) "
                    f"around {display_time}. Highly probable physical co-location or operational meeting."
                )
            })

    location_correlations.sort(key=lambda x: (x["distinct_entities_count"], x["event_count"]), reverse=True)

    # ── 8. Killer Feature: Unified Forensic Communication Timeline ───────────
    timeline_events = []

    # A. Add CDR Call Events
    for c in cdrs:
        caller = resolve_party(c.caller_phone_id)
        receiver = resolve_party(c.receiver_phone_id)
        tower = resolve_loc(c.tower_location_id)
        dur = c.duration_seconds or 0
        call_type = (c.call_type or "voice").upper()

        narrative = (
            f"{caller['person_name']} ({caller['number']}) placed a {dur}s {call_type} call to "
            f"{receiver['person_name']} ({receiver['number']}) via {tower['name']}."
        ) if call_type != "SMS" else (
            f"{caller['person_name']} transmitted SMS message to {receiver['person_name']} via {tower['name']}."
        )

        timeline_events.append({
            "event_type": "CALL" if call_type != "SMS" else "SMS",
            "timestamp": c.timestamp,
            "party_a": caller,
            "party_b": receiver,
            "call_type": call_type,
            "duration_seconds": dur,
            "duration_formatted": format_duration(dur),
            "location": tower,
            "narrative": narrative,
            "cdr_id": c.cdr_id,
        })

    # B. Add Movement / Location Events
    for le in loc_events_query.all():
        person = persons.get(le.person_id)
        loc = resolve_loc(le.location_id)
        p_name = person.full_name if person else le.person_id
        ev_type = (le.event_type or "MOVEMENT").upper()

        timeline_events.append({
            "event_type": "MOVEMENT",
            "timestamp": le.timestamp,
            "party_a": {
                "person_id": le.person_id,
                "person_name": p_name,
                "label": f"{p_name} (Suspect)",
            },
            "location": loc,
            "narrative": f"{p_name} observed moving to {loc['name']} ({loc['area']}) — {ev_type} [{le.source or 'log'}].",
            "event_id": le.event_id,
        })

    # C. Add Incident Marker
    incident_event = None
    if primary_fir and primary_fir.incident_date:
        incident_event = {
            "event_type": "INCIDENT",
            "timestamp": f"{primary_fir.incident_date}T19:15:00" if "T" not in primary_fir.incident_date else primary_fir.incident_date,
            "is_critical_anchor": True,
            "crime_type": primary_fir.crime_type,
            "narrative": (
                f"🚨 INCIDENT OCCURS: {primary_fir.crime_type} reported at Police Station {primary_fir.police_station_id or 'Local Jurisdiction'}. "
                f"{primary_fir.summary or ''}"
            ),
            "fir_number": primary_fir.fir_number,
        }
    elif target_case and target_case.date_range_end:
        incident_event = {
            "event_type": "INCIDENT",
            "timestamp": f"{target_case.date_range_end}T19:15:00" if "T" not in target_case.date_range_end else target_case.date_range_end,
            "is_critical_anchor": True,
            "crime_type": target_case.crime_type,
            "narrative": f"🚨 INCIDENT OCCURS: {target_case.case_title} ({target_case.crime_type}).",
        }

    if incident_event:
        timeline_events.append(incident_event)

    # Sort timeline chronologically
    timeline_events.sort(key=lambda x: x.get("timestamp") or "")

    # Compute relative offsets to incident if incident timestamp is present
    anchor_timestamp = incident_event["timestamp"] if incident_event else incident_timestamp
    if anchor_timestamp:
        try:
            inc_dt = datetime.fromisoformat(anchor_timestamp.replace("Z", ""))
            for ev in timeline_events:
                if not ev.get("timestamp") or ev.get("event_type") == "INCIDENT":
                    ev["relative_time"] = "T-0 (Incident Moment)"
                    continue
                try:
                    ev_dt = datetime.fromisoformat(ev["timestamp"].replace("Z", ""))
                    diff_sec = int((ev_dt - inc_dt).total_seconds())
                    sign = "+" if diff_sec >= 0 else "-"
                    abs_sec = abs(diff_sec)
                    if abs_sec < 3600:
                        ev["relative_time"] = f"{sign}{abs_sec // 60}m"
                    elif abs_sec < 86400:
                        ev["relative_time"] = f"{sign}{abs_sec // 3600}h {(abs_sec % 3600) // 60}m"
                    else:
                        ev["relative_time"] = f"{sign}{abs_sec // 86400}d {(abs_sec % 86400) // 3600}h"
                except Exception:
                    ev["relative_time"] = None
        except Exception:
            pass

    # Select timeline events: if large, keep key events around incident or last 350
    selected_timeline = timeline_events if len(timeline_events) <= 500 else timeline_events[-500:]
    # Ensure incident event is included
    if incident_event and incident_event not in selected_timeline:
        selected_timeline.append(incident_event)
        selected_timeline.sort(key=lambda x: x.get("timestamp") or "")


    # ── 9. Common Devices & Burner Handsets ──────────────────────────────────
    # Check PhoneSimImeiDevice
    links_query = db.query(PhoneSimImeiDevice)
    all_links = links_query.all()
    device_sims = defaultdict(set)
    device_persons = defaultdict(set)
    device_phones = defaultdict(set)

    for l in all_links:
        if l.device_id:
            if l.sim_id:
                device_sims[l.device_id].add(l.sim_id)
            if l.person_id:
                device_persons[l.device_id].add(l.person_id)
            if l.phone_id:
                device_phones[l.device_id].add(l.phone_id)

    common_devices = []
    for dev_id, sims in device_sims.items():
        if len(sims) >= 2 or len(device_persons[dev_id]) >= 2:
            dev_obj = devices.get(dev_id)
            assoc_persons = [persons[pid].full_name for pid in device_persons[dev_id] if pid in persons]
            common_devices.append({
                "device_id": dev_id,
                "imei": dev_obj.imei if dev_obj else dev_id,
                "make": dev_obj.make if dev_obj else "Unknown",
                "model": dev_obj.model if dev_obj else "Handset",
                "sim_count": len(sims),
                "sim_ids": list(sims),
                "associated_persons": assoc_persons,
                "phone_ids": list(device_phones[dev_id]),
                "severity": "CRITICAL" if len(assoc_persons) > 1 else "HIGH",
                "explanation": (
                    f"Handset {dev_id} ({dev_obj.make if dev_obj else ''} {dev_obj.model if dev_obj else ''}) "
                    f"utilized across {len(sims)} SIM cards and {len(assoc_persons)} distinct suspects. "
                    f"Confirmed burner/shared device."
                )
            })

    # ── 10. Backward-compatible Legacy Anomaly Format ────────────────────────
    legacy_alerts = []
    for pair in frequent_pairs[:15]:
        legacy_alerts.append({
            "detector_name": "CDR_FREQUENT_CALLER_BURST",
            "severity": pair["severity"],
            "confidence": 0.92,
            "entities": [pair["party_a"]["phone_id"], pair["party_b"]["phone_id"]],
            "evidence": [pair["party_a"]["label"], pair["party_b"]["label"], f"{pair['total_calls']} calls", pair["total_duration_formatted"]],
            "explanation": pair["explanation"],
            "case_ids": [case_id] if case_id else [],
            "timestamps": [pair["first_contact"], pair["last_contact"]],
        })

    for conn in hidden_connectors[:10]:
        legacy_alerts.append({
            "detector_name": "TELECOM_HIDDEN_CONNECTOR_BROKER",
            "severity": conn["severity"],
            "confidence": conn["confidence"],
            "entities": [conn["connector"]["phone_id"]],
            "evidence": [p["label"] for p in conn["connected_parties"][:4]],
            "explanation": conn["explanation"],
            "case_ids": [case_id] if case_id else [],
            "timestamps": [],
        })

    for surge in temporal_surges:
        legacy_alerts.append({
            "detector_name": surge["detector_name"],
            "severity": surge["severity"],
            "confidence": surge["confidence"],
            "entities": [case_id or "CASE"],
            "evidence": [f"{surge['surge_multiplier']}x surge", f"{surge['total_surge_calls']} calls"],
            "explanation": surge["explanation"],
            "case_ids": [case_id] if case_id else [],
            "timestamps": [surge["incident_date"]],
        })

    for loc in location_correlations[:10]:
        legacy_alerts.append({
            "detector_name": "TELECOM_TOWER_CO_LOCATION",
            "severity": loc["severity"],
            "confidence": loc["confidence"],
            "entities": [p["phone_id"] for p in loc["entities"]],
            "evidence": [loc["tower_name"], loc["timestamp_window"], f"{loc['distinct_entities_count']} suspects"],
            "explanation": loc["explanation"],
            "case_ids": [case_id] if case_id else [],
            "timestamps": [loc["timestamp_window"]],
        })

    for dev in common_devices[:10]:
        legacy_alerts.append({
            "detector_name": "TELECOM_BURNER_DEVICE_MULTI_SIM",
            "severity": dev["severity"],
            "confidence": 0.94,
            "entities": [dev["device_id"]] + dev["associated_persons"],
            "evidence": [f"{dev['sim_count']} SIMs", dev["imei"]],
            "explanation": dev["explanation"],
            "case_ids": [case_id] if case_id else [],
            "timestamps": [],
        })

    return {
        "case_id": case_id,
        "case_title": target_case.case_title if target_case else "Cross-Case Syndicate Intelligence",
        "incident_timestamp": incident_timestamp,
        "summary": {
            "total_calls": total_calls,
            "total_duration_seconds": total_duration_sec,
            "total_duration_formatted": format_duration(total_duration_sec),
            "voice_calls": voice_calls,
            "sms_calls": sms_calls,
            "other_calls": other_calls,
            "distinct_callers": len(outgoing_counts),
            "distinct_receivers": len(incoming_counts),
            "top_towers": top_towers,
            "hourly_distribution": [
                {"hour": h, "calls": hourly_distribution[h]} for h in range(24)
            ],
            "daily_distribution": [
                {"date": d, "calls": c} for d, c in sorted(daily_distribution.items())
            ],
        },
        "frequent_communications": frequent_pairs,
        "hidden_connectors": hidden_connectors,
        "temporal_surges": temporal_surges,
        "location_correlations": location_correlations,
        "timeline": selected_timeline,
        "total_timeline_events": len(timeline_events),
        "common_devices": common_devices,
        "results": legacy_alerts,
    }
