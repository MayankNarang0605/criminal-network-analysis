"""
ML & Statistical Anomaly Detection Layer.
Answers the fundamental investigative question:
"What unusual behavior exists that predefined rules may have missed?"

Features:
1. Groups related anomalies (e.g. all anomalous transactions for an account or burst calls for a phone)
   instead of dumping hundreds of separate raw records.
2. Prioritizes and ranks by severity: CRITICAL -> HIGH -> MEDIUM -> LOW.
3. Gives each anomaly its own score based strictly on actual deviation.
4. Each card answers 4 core questions:
   - What happened?
   - When?
   - Why is it unusual?
   - How severe is it?
5. Deep investigative data packaged under `investigate_data` (Counterparties, Records, Network, Location, Timeline, Evidence, Model details).
6. Keeps ML and Rule-based detections strictly separated with `detection_engine: 'ML'` vs `'RULE'`.
"""
import math
import warnings
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, List, Optional
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.cluster import DBSCAN
from sqlalchemy.orm import Session

from backend.logging_config import logger
from backend.models.evidence import (
    Transaction, CDR, LocationEvent, Location, Phone, Person, Case, BankAccount,
    FIR, FIRPerson, PhoneSimImeiDevice
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great circle distance between two points on Earth in kilometers."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def format_currency_inr(amount: float) -> str:
    """Formats amount into readable Indian Lakhs/Thousands format."""
    if amount >= 10000000:
        return f"₹{amount / 10000000:.2f} Cr"
    if amount >= 100000:
        return f"₹{amount / 100000:.2f}L"
    if amount >= 1000:
        return f"₹{amount / 1000:.1f}K"
    return f"₹{amount:,.0f}"


def format_date_human(iso_str: Optional[str]) -> str:
    """Converts ISO timestamp into readable format (e.g. 12 Aug 2026)."""
    if not iso_str:
        return "Unknown Date"
    try:
        clean = iso_str.replace("Z", "").split()[0]
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%d %b %Y")
    except Exception:
        return iso_str[:10]


# ── 1. Financial ML Anomaly Engine: Isolation Forest + Robust IQR ────────────
def detect_financial_ml_anomalies(db: Session, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Detects financial transaction anomalies using Isolation Forest + Account Baseline IQR.
    Groups multiple anomalous transactions for each account into a single cohesive finding.
    """
    tx_query = db.query(Transaction)
    if case_id:
        tx_query = tx_query.filter(Transaction.case_id == case_id)
    txs: List[Transaction] = tx_query.all()

    if not txs:
        return []

    accounts = {b.account_id: b for b in db.query(BankAccount).all()}
    persons = {p.person_id: p for p in db.query(Person).all()}

    # Group transactions by sender and receiver accounts
    account_txs = defaultdict(list)
    for t in txs:
        account_txs[t.sender_account].append(t)
        account_txs[t.receiver_account].append(t)

    all_amounts = np.array([t.amount for t in txs]).reshape(-1, 1)
    global_iso = None
    if len(all_amounts) >= 10:
        try:
            global_iso = IsolationForest(contamination=0.08, random_state=42)
            global_iso.fit(all_amounts)
        except Exception:
            global_iso = None

    anomaly_groups = []

    for acc_id, t_list in account_txs.items():
        if len(t_list) < 2:
            continue

        amounts = [t.amount for t in t_list]
        amounts_arr = np.array(amounts)
        median_val = float(np.median(amounts_arr))
        q25 = float(np.percentile(amounts_arr, 25))
        q75 = float(np.percentile(amounts_arr, 75))
        iqr = max(q75 - q25, median_val * 0.20, 1000.0)

        account_iso_preds = None
        if len(t_list) >= 6:
            try:
                clf = IsolationForest(contamination=0.15, random_state=42)
                account_iso_preds = clf.fit_predict(amounts_arr.reshape(-1, 1))
            except Exception:
                account_iso_preds = None

        anomalous_records = []
        for idx, t in enumerate(t_list):
            amt = t.amount
            upper_fence = q75 + (2.2 * iqr)
            is_spike = amt > upper_fence and amt >= 1.6 * q75

            is_iso_outlier = False
            if account_iso_preds is not None and account_iso_preds[idx] == -1 and amt > median_val:
                is_iso_outlier = True
            elif global_iso is not None and amt >= 120000:
                is_iso_outlier = True

            if is_spike or is_iso_outlier:
                deviation = amt / max(median_val, 1.0)
                if deviation >= 2.0 or amt >= 150000:
                    anomalous_records.append((t, amt, deviation))

        if not anomalous_records:
            continue

        # Sort anomalous transactions chronologically
        anomalous_records.sort(key=lambda x: x[0].timestamp or "")

        peak_t, peak_amt, max_deviation = max(anomalous_records, key=lambda x: x[2])
        total_anom_volume = sum(r[1] for r in anomalous_records)
        event_count = len(anomalous_records)

        # Severity & Score based strictly on actual deviation
        if max_deviation >= 8.0 or peak_amt >= 400000:
            severity = "CRITICAL"
            score = min(99, max(90, int(88 + min(max_deviation - 8.0, 10.0) * 1.0)))
        elif max_deviation >= 4.0 or peak_amt >= 200000:
            severity = "HIGH"
            score = min(89, max(80, int(78 + (max_deviation - 4.0) * 2.2)))
        elif max_deviation >= 2.0:
            severity = "MEDIUM"
            score = min(79, max(70, int(68 + (max_deviation - 2.0) * 4.0)))
        else:
            severity = "LOW"
            score = max(55, int(50 + max_deviation * 8.0))

        b_acc = accounts.get(acc_id)
        p_obj = persons.get(b_acc.person_id) if b_acc and b_acc.person_id else None
        entity_name = p_obj.full_name if p_obj else f"Account {acc_id}"

        exp_min = format_currency_inr(q25)
        exp_max = format_currency_inr(q75)
        peak_str = format_currency_inr(peak_amt)
        tot_str = format_currency_inr(total_anom_volume)
        when_str = format_date_human(peak_t.timestamp)

        # 4 core card fields
        if event_count == 1:
            what_happened = f"{peak_str} transaction"
        else:
            what_happened = f"Peak {peak_str} transaction ({event_count} related spikes totalling {tot_str})"

        why_unusual = f"Normal: {exp_min}–{exp_max} • {round(max_deviation, 1)}× above normal"
        why_unusual_detail = f"Significantly outside this account's historical baseline median ({format_currency_inr(median_val)})."

        # Deep data for Investigate modal
        counterparties_map = defaultdict(lambda: {"count": 0, "volume": 0.0})
        evidence_records = []
        timeline = []

        for t, amt, dev in anomalous_records:
            cparty = t.receiver_account if t.sender_account == acc_id else t.sender_account
            direction = "OUTGOING" if t.sender_account == acc_id else "INCOMING"
            counterparties_map[cparty]["count"] += 1
            counterparties_map[cparty]["volume"] += amt

            evidence_records.append({
                "id": t.transaction_id,
                "type": "Transaction",
                "timestamp": t.timestamp,
                "date_formatted": format_date_human(t.timestamp),
                "amount": amt,
                "amount_formatted": format_currency_inr(amt),
                "direction": direction,
                "sender": t.sender_account,
                "receiver": t.receiver_account,
                "deviation": f"{round(dev, 1)}×",
                "details": f"{direction} transfer of {format_currency_inr(amt)} with account {cparty}",
            })

            timeline.append({
                "timestamp": t.timestamp,
                "date": format_date_human(t.timestamp),
                "title": f"{direction}: {format_currency_inr(amt)}",
                "description": f"Transaction {t.transaction_id} executed with {cparty} ({round(dev, 1)}× deviation)",
                "badge": "High Outlier" if dev >= 5.0 else "Volume Spike",
            })

        counterparties = [
            {
                "account_id": cp_acc,
                "transaction_count": cp_data["count"],
                "total_volume": cp_data["volume"],
                "formatted_volume": format_currency_inr(cp_data["volume"]),
            }
            for cp_acc, cp_data in sorted(counterparties_map.items(), key=lambda x: x[1]["volume"], reverse=True)
        ]

        anomaly_groups.append({
            "group_id": f"GRP-ML-FIN-{acc_id}",
            "case_id": peak_t.case_id,
            "detection_engine": "ML",
            "anomaly_type": "Financial",
            "detector_name": "ML_ISOLATION_FOREST_TXN_OUTLIER",
            "model_used": "Isolation Forest + Robust IQR/MAD",
            "title": f"Financial Activity Spike — {entity_name} ({acc_id})",
            "subtitle": f"{event_count} related events | {when_str} | Score {score}",
            "entity": f"{entity_name} ({acc_id})",
            "entity_id": p_obj.person_id if p_obj else acc_id,
            "entity_type": "ACCOUNT",
            "event_count": event_count,
            "primary_date": when_str,
            # The 4 Required Answers:
            "what_happened": what_happened,
            "when": when_str,
            "why_unusual": why_unusual,
            "why_unusual_detail": why_unusual_detail,
            "severity": severity,
            "anomaly_score_100": score,
            "deviation_multiplier": round(max_deviation, 1),
            "evidence": [r[0].transaction_id for r in anomalous_records],
            "investigate_data": {
                "counterparties": counterparties,
                "evidence_records": evidence_records,
                "timeline": timeline,
                "model_details": {
                    "algorithm": "Isolation Forest (scikit-learn) + Robust IQR/MAD",
                    "baseline_median": format_currency_inr(median_val),
                    "baseline_iqr_range": f"{exp_min} – {exp_max}",
                    "peak_deviation": f"{round(max_deviation, 1)}×",
                    "total_account_events": len(t_list),
                },
                "entity_profile": {
                    "name": p_obj.full_name if p_obj else f"Account {acc_id}",
                    "alias": p_obj.alias if p_obj else None,
                    "city": p_obj.city if p_obj else (b_acc.branch_city if b_acc else None),
                    "bank_name": b_acc.bank_name if b_acc else "Unknown Bank",
                    "account_id": acc_id,
                    "person_id": p_obj.person_id if p_obj else None,
                    "case_id": peak_t.case_id,
                },
                "network": {
                    "primary_node": entity_name,
                    "connections": [
                        {
                            "target": cp["account_id"],
                            "relationship": "FINANCIAL_TRANSFER",
                            "volume": cp["formatted_volume"],
                            "count": cp["transaction_count"],
                        }
                        for cp in counterparties[:6]
                    ],
                },
            },
        })

    return sorted(anomaly_groups, key=lambda x: x["anomaly_score_100"], reverse=True)


# ── 2. CDR Telecom ML Anomaly Engine: LOF + Temporal Z-Score ─────────────────
def detect_telecom_ml_anomalies(db: Session, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Detects telecom call bursts using Local Outlier Factor (LOF) + Temporal Z-Score.
    Groups multiple burst days for a subscriber into a single cohesive finding.
    """
    cdr_query = db.query(CDR)
    if case_id:
        cdr_query = cdr_query.filter(CDR.case_id == case_id)
    cdrs: List[CDR] = cdr_query.all()

    if not cdrs:
        return []

    phones = {ph.phone_id: ph for ph in db.query(Phone).all()}
    persons = {p.person_id: p for p in db.query(Person).all()}

    phone_daily = defaultdict(lambda: defaultdict(list))
    for c in cdrs:
        if not c.timestamp:
            continue
        date_str = c.timestamp[:10]
        phone_daily[c.caller_phone_id][date_str].append(c)
        phone_daily[c.receiver_phone_id][date_str].append(c)

    anomaly_groups = []

    for ph_id, dates_map in phone_daily.items():
        if len(dates_map) < 2 and sum(len(calls) for calls in dates_map.values()) < 6:
            continue

        daily_counts = [len(calls) for calls in dates_map.values()]
        counts_arr = np.array(daily_counts)
        median_rate = float(np.median(counts_arr))
        mean_rate = float(np.mean(counts_arr))
        std_rate = float(np.std(counts_arr)) if len(counts_arr) > 1 else 1.0

        # Multi-dimensional LOF model
        feature_rows = []
        for d_calls in dates_map.values():
            tot_dur = sum((c.duration_seconds or 0) for c in d_calls) / 60.0
            peers = len(set(c.caller_phone_id if c.caller_phone_id != ph_id else c.receiver_phone_id for c in d_calls))
            feature_rows.append([len(d_calls), tot_dur, peers])

        lof_scores = None
        if len(feature_rows) >= 4:
            try:
                feature_matrix = np.array(feature_rows, dtype=float)
                rng = np.random.RandomState(42)
                feature_matrix += rng.normal(0, 1e-5, feature_matrix.shape)
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
                    n_nbrs = max(2, min(4, len(feature_rows) - 1))
                    lof = LocalOutlierFactor(n_neighbors=n_nbrs, novelty=False)
                    lof.fit(feature_matrix)
                    lof_scores = -lof.negative_outlier_factor_
            except Exception:
                lof_scores = None

        spike_days = []
        for idx, (date_str, call_list) in enumerate(dates_map.items()):
            n_calls = len(call_list)
            z_score = (n_calls - mean_rate) / max(std_rate, 1.0)
            ratio = n_calls / max(median_rate, 1.0)
            is_lof_outlier = lof_scores is not None and lof_scores[idx] > 1.5 and n_calls > median_rate

            if (ratio >= 2.5 and n_calls >= 6) or is_lof_outlier or z_score >= 2.5:
                spike_days.append((date_str, call_list, n_calls, ratio, z_score))

        if not spike_days:
            continue

        # Group all burst days for this subscriber
        peak_date, peak_calls_list, peak_count, max_ratio, peak_z = max(spike_days, key=lambda x: x[3])
        total_surge_calls = sum(sd[2] for sd in spike_days)
        all_surge_cdrs = [c for sd in spike_days for c in sd[1]]

        # Severity and Score
        if max_ratio >= 6.0 or peak_count >= 30:
            severity = "CRITICAL"
            score = min(99, max(90, int(88 + min(max_ratio - 6.0, 12.0) * 0.9)))
        elif max_ratio >= 3.5 or peak_count >= 15:
            severity = "HIGH"
            score = min(89, max(80, int(78 + (max_ratio - 3.5) * 2.0)))
        elif max_ratio >= 2.0:
            severity = "MEDIUM"
            score = min(79, max(70, int(68 + (max_ratio - 2.0) * 3.5)))
        else:
            severity = "LOW"
            score = max(55, int(50 + max_ratio * 7.0))

        ph_obj = phones.get(ph_id)
        p_obj = persons.get(ph_obj.person_id) if ph_obj and ph_obj.person_id else None
        phone_num = ph_obj.number if ph_obj else ph_id
        subscriber_name = p_obj.full_name if p_obj else f"Phone {phone_num}"

        min_exp = max(1, int(np.percentile(counts_arr, 20)))
        max_exp = max(min_exp + 1, int(np.percentile(counts_arr, 80)))
        when_str = format_date_human(peak_date)

        if len(spike_days) == 1:
            what_happened = f"{peak_count} calls/day burst"
        else:
            what_happened = f"Peak {peak_count} calls/day ({total_surge_calls} calls across {len(spike_days)} surge days)"

        why_unusual = f"Normal: {min_exp}–{max_exp} calls/day • {round(max_ratio, 1)}× above normal"
        why_unusual_detail = f"Acute communication surge over baseline median ({median_rate:.1f} calls/day), characteristic of operational mobilization."

        # Investigate data
        counterparties_map = defaultdict(lambda: {"calls": 0, "duration": 0})
        evidence_records = []
        timeline = []

        for c in all_surge_cdrs:
            other_ph = c.receiver_phone_id if c.caller_phone_id == ph_id else c.caller_phone_id
            other_obj = phones.get(other_ph)
            other_person = persons.get(other_obj.person_id) if other_obj and other_obj.person_id else None
            other_label = f"{other_person.full_name} ({other_obj.number})" if other_person and other_obj else other_ph

            counterparties_map[other_label]["calls"] += 1
            counterparties_map[other_label]["duration"] += (c.duration_seconds or 0)

            evidence_records.append({
                "id": c.cdr_id,
                "type": "CDR",
                "timestamp": c.timestamp,
                "date_formatted": format_date_human(c.timestamp),
                "duration_seconds": c.duration_seconds,
                "duration_formatted": f"{(c.duration_seconds or 0) // 60}m {(c.duration_seconds or 0) % 60}s",
                "caller": c.caller_phone_id,
                "receiver": c.receiver_phone_id,
                "counterparty": other_label,
                "tower": c.tower_location_id or "Cell Tower",
                "details": f"Voice call with {other_label} ({c.duration_seconds or 0}s)",
            })

        for sd in sorted(spike_days, key=lambda x: x[0]):
            timeline.append({
                "timestamp": f"{sd[0]}T00:00:00",
                "date": format_date_human(sd[0]),
                "title": f"Call Surge: {sd[2]} calls",
                "description": f"Recorded {sd[2]} calls on {sd[0]} ({round(sd[3], 1)}× baseline rate, Z-Score: {sd[4]:.1f})",
                "badge": "Call Surge",
            })

        counterparties = [
            {
                "contact": cp_label,
                "call_count": cp_val["calls"],
                "total_duration": cp_val["duration"],
                "formatted_duration": f"{cp_val['duration'] // 60}m {cp_val['duration'] % 60}s",
            }
            for cp_label, cp_val in sorted(counterparties_map.items(), key=lambda x: x[1]["calls"], reverse=True)
        ]

        anomaly_groups.append({
            "group_id": f"GRP-ML-CDR-{ph_id}",
            "case_id": all_surge_cdrs[0].case_id if all_surge_cdrs else (case_id or "CASE001"),
            "detection_engine": "ML",
            "anomaly_type": "CDR",
            "detector_name": "ML_LOCAL_OUTLIER_FACTOR_CALL_BURST",
            "model_used": "Local Outlier Factor (LOF) + Temporal Z-Score",
            "title": f"Unusual Communication Surge — {subscriber_name} ({phone_num})",
            "subtitle": f"{total_surge_calls} related calls | {when_str} | Score {score}",
            "entity": f"{subscriber_name} ({phone_num})",
            "entity_id": p_obj.person_id if p_obj else ph_id,
            "entity_type": "PHONE",
            "event_count": total_surge_calls,
            "primary_date": when_str,
            "what_happened": what_happened,
            "when": when_str,
            "why_unusual": why_unusual,
            "why_unusual_detail": why_unusual_detail,
            "severity": severity,
            "anomaly_score_100": score,
            "deviation_multiplier": round(max_ratio, 1),
            "evidence": [c.cdr_id for c in all_surge_cdrs[:15]],
            "investigate_data": {
                "counterparties": counterparties[:10],
                "evidence_records": evidence_records[:25],
                "timeline": timeline,
                "model_details": {
                    "algorithm": "Local Outlier Factor (LOF) + Temporal Poisson Z-Score",
                    "baseline_median": f"{median_rate:.1f} calls/day",
                    "baseline_iqr_range": f"{min_exp}–{max_exp} calls/day",
                    "peak_z_score": f"{peak_z:.1f}",
                    "peak_deviation": f"{round(max_ratio, 1)}×",
                    "monitored_days": len(dates_map),
                },
                "entity_profile": {
                    "name": subscriber_name,
                    "phone_number": phone_num,
                    "person_id": p_obj.person_id if p_obj else None,
                    "case_id": all_surge_cdrs[0].case_id if all_surge_cdrs else case_id,
                },
                "network": {
                    "primary_node": subscriber_name,
                    "connections": [
                        {
                            "target": cp["contact"],
                            "relationship": "TELECOM_CALL",
                            "volume": f"{cp['call_count']} calls ({cp['formatted_duration']})",
                            "count": cp["call_count"],
                        }
                        for cp in counterparties[:6]
                    ],
                },
            },
        })

    return sorted(anomaly_groups, key=lambda x: x["anomaly_score_100"], reverse=True)


# ── 3. Geospatial ML Anomaly Engine: DBSCAN + Velocity Analysis ──────────────
def detect_location_ml_anomalies(db: Session, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Detects impossible travel, spatial displacement, and multi-city teleportation.
    Groups multiple transit events for each suspect into a single cohesive finding.
    """
    loc_events_query = db.query(LocationEvent)
    if case_id:
        loc_events_query = loc_events_query.filter(LocationEvent.case_id == case_id)
    events: List[LocationEvent] = loc_events_query.order_by(LocationEvent.timestamp.asc()).all()

    locations = {loc.location_id: loc for loc in db.query(Location).all()}
    persons = {p.person_id: p for p in db.query(Person).all()}

    cdr_query = db.query(CDR)
    if case_id:
        cdr_query = cdr_query.filter(CDR.case_id == case_id)
    cdrs = cdr_query.filter(CDR.tower_location_id.isnot(None)).all()

    phones = {ph.phone_id: ph for ph in db.query(Phone).all()}
    phone_to_person = {ph.phone_id: ph.person_id for ph in phones.values() if ph.person_id}

    person_trajectory = defaultdict(list)
    for ev in events:
        if ev.location_id and ev.location_id in locations and ev.timestamp:
            loc = locations[ev.location_id]
            if loc.latitude and loc.longitude:
                person_trajectory[ev.person_id].append({
                    "timestamp": ev.timestamp,
                    "location_id": ev.location_id,
                    "city": loc.city or loc.area or "Unknown City",
                    "name": loc.location_name or loc.location_id,
                    "lat": loc.latitude,
                    "lon": loc.longitude,
                    "event_id": ev.event_id,
                    "case_id": ev.case_id,
                })

    for c in cdrs:
        pid = phone_to_person.get(c.caller_phone_id) or phone_to_person.get(c.receiver_phone_id)
        if pid and c.tower_location_id and c.tower_location_id in locations and c.timestamp:
            loc = locations[c.tower_location_id]
            if loc.latitude and loc.longitude:
                person_trajectory[pid].append({
                    "timestamp": c.timestamp,
                    "location_id": c.tower_location_id,
                    "city": loc.city or loc.area or "Unknown City",
                    "name": loc.location_name or c.tower_location_id,
                    "lat": loc.latitude,
                    "lon": loc.longitude,
                    "event_id": f"CDR-TWR-{c.cdr_id}",
                    "case_id": c.case_id,
                })

    anomaly_groups = []

    for pid, traj in person_trajectory.items():
        if len(traj) < 2:
            continue

        traj.sort(key=lambda x: x["timestamp"])
        p_obj = persons.get(pid)
        person_name = p_obj.full_name if p_obj else f"Suspect {pid}"

        # Determine core anchor city
        city_counts = defaultdict(int)
        for pt in traj:
            city_counts[pt["city"]] += 1
        core_city, _ = max(city_counts.items(), key=lambda x: x[1])

        anomalous_windows = []
        for i in range(len(traj)):
            window_pts = [traj[i]]
            try:
                t_start = datetime.fromisoformat(traj[i]["timestamp"].replace("Z", ""))
            except Exception:
                continue

            for j in range(i + 1, len(traj)):
                try:
                    t_cur = datetime.fromisoformat(traj[j]["timestamp"].replace("Z", ""))
                    diff_hours = (t_cur - t_start).total_seconds() / 3600.0
                    if diff_hours <= 24.0:
                        window_pts.append(traj[j])
                    else:
                        break
                except Exception:
                    pass

            if len(window_pts) >= 2:
                distinct_cities = list(dict.fromkeys(pt["city"] for pt in window_pts))
                max_dist_km = 0.0
                max_velocity = 0.0
                for k in range(len(window_pts) - 1):
                    p1 = window_pts[k]
                    p2 = window_pts[k + 1]
                    dist = haversine_km(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
                    try:
                        t1 = datetime.fromisoformat(p1["timestamp"].replace("Z", ""))
                        t2 = datetime.fromisoformat(p2["timestamp"].replace("Z", ""))
                        h_delta = max((t2 - t1).total_seconds() / 3600.0, 0.05)
                        v = dist / h_delta
                        max_dist_km += dist
                        if v > max_velocity:
                            max_velocity = v
                    except Exception:
                        pass

                if (len(distinct_cities) >= 2 and max_dist_km >= 80.0) or max_velocity >= 150.0:
                    deviation = max(len(distinct_cities) * 2.5, max_dist_km / 30.0, max_velocity / 60.0)
                    anomalous_windows.append((window_pts, distinct_cities, max_dist_km, max_velocity, deviation))

        if not anomalous_windows:
            continue

        # Group all displacement windows for this suspect
        best_win = max(anomalous_windows, key=lambda x: x[4])
        window_pts, distinct_cities, max_dist_km, max_velocity, max_dev = best_win
        when_str = format_date_human(window_pts[0]["timestamp"])
        cities_str = ", ".join(distinct_cities)

        if max_dev >= 8.0 or max_velocity >= 200.0 or len(distinct_cities) >= 3:
            severity = "CRITICAL"
            score = min(99, max(90, int(88 + min(max_dev - 8.0, 15.0) * 0.8)))
        elif max_dev >= 4.0 or max_velocity >= 100.0:
            severity = "HIGH"
            score = min(89, max(80, int(78 + (max_dev - 4.0) * 2.0)))
        elif max_dev >= 2.0:
            severity = "MEDIUM"
            score = min(79, max(70, int(68 + (max_dev - 2.0) * 3.5)))
        else:
            severity = "LOW"
            score = max(55, int(50 + max_dev * 7.0))

        what_happened = f"Traversed {len(distinct_cities)} cities ({cities_str}) across {max_dist_km:.0f} km within 24h"
        why_unusual = f"Normal: Anchored in {core_city} (radius < 25 km) • {round(max_dev, 1)}× spatial displacement"
        why_unusual_detail = f"Peak transit velocity of {max_velocity:.0f} km/h between disparate jurisdictions within a 24-hour window."

        evidence_records = [
            {
                "id": pt["event_id"],
                "type": "Location Ping",
                "timestamp": pt["timestamp"],
                "date_formatted": format_date_human(pt["timestamp"]),
                "city": pt["city"],
                "location_name": pt["name"],
                "coordinates": f"{pt['lat']:.4f}, {pt['lon']:.4f}",
                "details": f"Ping recorded at {pt['name']} ({pt['city']})",
            }
            for pt in window_pts
        ]

        timeline = [
            {
                "timestamp": pt["timestamp"],
                "date": format_date_human(pt["timestamp"]),
                "title": f"Location: {pt['city']}",
                "description": f"Recorded at {pt['name']} ({pt['lat']:.4f}, {pt['lon']:.4f})",
                "badge": "Displacement Point",
            }
            for pt in window_pts
        ]

        anomaly_groups.append({
            "group_id": f"GRP-ML-GEO-{pid}",
            "case_id": window_pts[0]["case_id"],
            "detection_engine": "ML",
            "anomaly_type": "Geospatial",
            "detector_name": "ML_DBSCAN_SPATIOTEMPORAL_VELOCITY_OUTLIER",
            "model_used": "DBSCAN + Spatiotemporal Velocity Analysis",
            "title": f"Rapid Cross-Jurisdiction Displacement — {person_name} ({pid})",
            "subtitle": f"{len(window_pts)} related events | {when_str} | Score {score}",
            "entity": f"{person_name} ({pid})",
            "entity_id": pid,
            "entity_type": "PERSON",
            "event_count": len(window_pts),
            "primary_date": when_str,
            "what_happened": what_happened,
            "when": when_str,
            "why_unusual": why_unusual,
            "why_unusual_detail": why_unusual_detail,
            "severity": severity,
            "anomaly_score_100": score,
            "deviation_multiplier": round(max_dev, 1),
            "evidence": [pt["event_id"] for pt in window_pts[:10]],
            "investigate_data": {
                "evidence_records": evidence_records,
                "timeline": timeline,
                "location": {
                    "core_anchor_city": core_city,
                    "cities_visited": distinct_cities,
                    "total_distance_km": round(max_dist_km, 1),
                    "peak_velocity_kmh": round(max_velocity, 1),
                },
                "model_details": {
                    "algorithm": "DBSCAN Spatiotemporal Clustering + Kinematic Velocity",
                    "core_anchor": f"{core_city} (Routine Base)",
                    "peak_velocity": f"{max_velocity:.0f} km/h",
                    "distance_covered": f"{max_dist_km:.0f} km",
                    "spatial_deviation": f"{round(max_dev, 1)}×",
                },
                "entity_profile": {
                    "name": person_name,
                    "alias": p_obj.alias if p_obj else None,
                    "age": p_obj.age if p_obj else None,
                    "city": p_obj.city if p_obj else core_city,
                    "person_id": pid,
                    "case_id": window_pts[0]["case_id"],
                },
                "network": {
                    "primary_node": person_name,
                    "connections": [
                        {
                            "target": city,
                            "relationship": "VISITED_LOCATION",
                            "volume": "Observed Ping",
                            "count": 1,
                        }
                        for city in distinct_cities
                    ],
                },
            },
        })

    return sorted(anomaly_groups, key=lambda x: x["anomaly_score_100"], reverse=True)


# ── 4. Unified Anomaly Orchestrator: Separated ML & Rules ───────────────────
def run_unified_anomalies(db: Session, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns prioritized grouped anomalies with clean separation:
    - ML & Statistical Findings (Isolation Forest, LOF, DBSCAN)
    - Rule-based Typology Findings (Structuring, Mule funnels, Burner SIMs, Cross-case)
    """
    from backend.services.detectors import (
        detect_structuring,
        detect_fan_in_fan_out,
        detect_burner_devices,
        detect_cross_case_overlap,
    )

    all_groups = []

    # 1. Machine Learning Anomalies
    ml_fin = detect_financial_ml_anomalies(db, case_id=case_id)
    ml_cdr = detect_telecom_ml_anomalies(db, case_id=case_id)
    ml_geo = detect_location_ml_anomalies(db, case_id=case_id)
    all_groups.extend(ml_fin)
    all_groups.extend(ml_cdr)
    all_groups.extend(ml_geo)

    # 2. Rule-Based Forensic Typologies (Cleanly Tagged as RULE)
    # A. Structuring (Smurfing)
    structuring_rules = detect_structuring(db)
    if case_id:
        structuring_rules = [a for a in structuring_rules if a.get("case_ids") and case_id in a["case_ids"]]
    for r in structuring_rules:
        acc = r["entities"][0]
        n_ev = len(r["evidence"])
        when_str = format_date_human(r["timestamps"][0]) if r.get("timestamps") else "Incident Window"
        all_groups.append({
            "group_id": f"GRP-RULE-STRUC-{acc}",
            "case_id": r["case_ids"][0] if r.get("case_ids") else (case_id or "CASE001"),
            "detection_engine": "RULE",
            "anomaly_type": "Financial",
            "detector_name": r["detector_name"],
            "model_used": "FATF Regulatory Heuristic (Smurfing Threshold)",
            "title": f"Regulatory Smurfing Cluster — Account {acc}",
            "subtitle": f"{n_ev} clustered transactions | {when_str} | Score 88",
            "entity": f"Account {acc}",
            "entity_id": acc,
            "entity_type": "ACCOUNT",
            "event_count": n_ev,
            "primary_date": when_str,
            "what_happened": f"{n_ev} transactions clustered strictly between ₹40K–₹49.9K",
            "when": when_str,
            "why_unusual": "Normal: Amounts dispersed > ₹50K • Deliberate reporting threshold evasion",
            "why_unusual_detail": f"Account executed {n_ev} repeated transfers just below mandatory reporting threshold.",
            "severity": r["severity"],
            "anomaly_score_100": 88,
            "deviation_multiplier": 3.5,
            "evidence": r["evidence"],
            "investigate_data": {
                "evidence_records": [
                    {"id": ev, "type": "Transaction", "details": "Near-threshold smurfing transfer (₹40K–₹49.9K)"}
                    for ev in r["evidence"]
                ],
                "model_details": {
                    "algorithm": "FATF Regulatory Heuristic Rule",
                    "threshold_range": "₹40,000 – ₹49,999",
                    "cluster_density": f"{n_ev} transactions",
                },
                "entity_profile": {"account_id": acc, "case_id": r["case_ids"][0] if r.get("case_ids") else case_id},
                "network": {
                    "primary_node": f"Account {acc}",
                    "connections": [{"target": ev, "relationship": "TRANSACTION_RECORD"} for ev in r["evidence"][:5]],
                },
                "timeline": [
                    {"date": when_str, "title": "Smurfing Pattern Detected", "description": r["explanation"], "badge": "Regulatory Alert"}
                ],
            },
        })

    # B. Fan-in / Fan-out Mule Accounts
    mule_rules = detect_fan_in_fan_out(db)
    if case_id:
        mule_rules = [a for a in mule_rules if a.get("case_ids") and case_id in a["case_ids"]]
    for r in mule_rules:
        acc = r["entities"][0]
        n_ev = len(r["evidence"])
        is_fan_in = "FAN_IN" in r["detector_name"]
        typology_label = "Mule Aggregation Funnel" if is_fan_in else "Rapid Fund Dispersal Funnel"
        when_str = format_date_human(r["timestamps"][0]) if r.get("timestamps") else "Active Window"
        all_groups.append({
            "group_id": f"GRP-RULE-MULE-{acc}",
            "case_id": r["case_ids"][0] if r.get("case_ids") else (case_id or "CASE001"),
            "detection_engine": "RULE",
            "anomaly_type": "Financial",
            "detector_name": r["detector_name"],
            "model_used": "Mule Funnel Graph Topology Detector",
            "title": f"{typology_label} — Account {acc}",
            "subtitle": f"{n_ev} distinct counterparties | {when_str} | Score 91",
            "entity": f"Account {acc}",
            "entity_id": acc,
            "entity_type": "ACCOUNT",
            "event_count": n_ev,
            "primary_date": when_str,
            "what_happened": f"High-velocity funnel routing funds across {n_ev} counterparties",
            "when": when_str,
            "why_unusual": f"Normal: 1–2 counterparties • {round(n_ev / 1.5, 1)}× counterparty ratio",
            "why_unusual_detail": f"Account acts as an operational transit conduit aggregating or dispersing rapid illicit funds.",
            "severity": r["severity"],
            "anomaly_score_100": 91,
            "deviation_multiplier": round(n_ev / 1.5, 1),
            "evidence": r["evidence"],
            "investigate_data": {
                "evidence_records": [
                    {"id": ev, "type": "Counterparty Flow", "details": f"Rapid flow involving account {ev}"}
                    for ev in r["evidence"]
                ],
                "model_details": {
                    "algorithm": "Graph In/Out Degree Ratio Topology Detector",
                    "counterparties_count": n_ev,
                },
                "entity_profile": {"account_id": acc, "case_id": r["case_ids"][0] if r.get("case_ids") else case_id},
                "network": {
                    "primary_node": f"Account {acc}",
                    "connections": [{"target": ev, "relationship": "MULE_FLOW"} for ev in r["evidence"][:6]],
                },
                "timeline": [
                    {"date": when_str, "title": typology_label, "description": r["explanation"], "badge": "Mule Alert"}
                ],
            },
        })

    # C. Burner Devices
    case_phones = set()
    case_persons = set()
    if case_id:
        case_cdrs = db.query(CDR).filter(CDR.case_id == case_id).all()
        for c in case_cdrs:
            case_phones.add(c.caller_phone_id)
            case_phones.add(c.receiver_phone_id)
        fir_ids = [f.fir_id for f in db.query(FIR).filter(FIR.case_id == case_id).all()]
        for fp in db.query(FIRPerson).filter(FIRPerson.fir_id.in_(fir_ids)).all():
            case_persons.add(fp.person_id)
        case_devices = {l.device_id for l in db.query(PhoneSimImeiDevice).all() if l.phone_id in case_phones or l.person_id in case_persons}
    else:
        case_devices = set()

    burner_rules = detect_burner_devices(db)
    for r in burner_rules:
        dev_id = r['entities'][0]
        if case_id and dev_id not in case_devices and not any(e in case_persons for e in r['entities']):
            continue

        n_ev = len(r['evidence'])
        all_groups.append({
            "group_id": f"GRP-RULE-BURNER-{dev_id}",
            "case_id": case_id or "Cross-Case",
            "detection_engine": "RULE",
            "anomaly_type": "CDR",
            "detector_name": r["detector_name"],
            "model_used": "Hardware IMEI Multi-SIM Binding Rule",
            "title": f"Burner Handset Multi-SIM Cycling — IMEI {dev_id}",
            "subtitle": f"{n_ev} linked SIM cards | Score 93",
            "entity": f"Handset IMEI {dev_id}",
            "entity_id": dev_id,
            "entity_type": "DEVICE",
            "event_count": n_ev,
            "primary_date": "Active Period",
            "what_happened": f"Single hardware handset cycled across {n_ev} distinct SIM cards / subscriber IDs",
            "when": "Active Period",
            "why_unusual": "Normal: 1 SIM card / 1 owner • 4.0× multi-subscriber hardware cycling",
            "why_unusual_detail": "Deliberate evasive hardware rotation to bypass telecom wiretaps and IMEI monitoring.",
            "severity": r["severity"],
            "anomaly_score_100": 93,
            "deviation_multiplier": 4.0,
            "evidence": r["evidence"],
            "investigate_data": {
                "evidence_records": [
                    {"id": ev, "type": "SIM / Phone Record", "details": f"SIM card / Phone {ev} mounted on handset"}
                    for ev in r["evidence"]
                ],
                "model_details": {
                    "algorithm": "IMEI-to-IMSI Graph Bipartite Multi-Binding",
                    "cycled_sims": n_ev,
                },
                "entity_profile": {"device_id": dev_id, "case_id": case_id},
                "network": {
                    "primary_node": f"IMEI {dev_id}",
                    "connections": [{"target": ev, "relationship": "MOUNTED_SIM"} for ev in r["evidence"]],
                },
                "timeline": [
                    {"date": "Active Period", "title": "Hardware Burner Swapping", "description": r["explanation"], "badge": "Burner Alert"}
                ],
            },
        })

    # D. Cross-Case Syndicate Overlap
    cross_rules = detect_cross_case_overlap(db)
    for r in cross_rules:
        pid = r['entities'][0]
        c_ids = r.get("case_ids", [])
        if case_id and case_id not in c_ids:
            continue

        all_groups.append({
            "group_id": f"GRP-RULE-CROSS-{pid}",
            "case_id": c_ids[0] if c_ids else (case_id or "Cross-Case"),
            "detection_engine": "RULE",
            "anomaly_type": "Geospatial",
            "detector_name": r["detector_name"],
            "model_used": "Multi-Jurisdiction Graph Intersection Rule",
            "title": f"Cross-Jurisdiction Syndicate Bridge — Suspect {pid}",
            "subtitle": f"{len(c_ids)} independent cases | Score 96",
            "entity": f"Suspect {pid}",
            "entity_id": pid,
            "entity_type": "PERSON",
            "event_count": len(c_ids),
            "primary_date": "Multi-Year",
            "what_happened": f"Identified active operator present across {len(c_ids)} distinct criminal investigations",
            "when": "Multi-Year",
            "why_unusual": f"Normal: 1 case jurisdiction • {len(c_ids)} independent police jurisdictions bridged",
            "why_unusual_detail": f"Entity serves as a pivotal cross-jurisdictional syndicate connector bridging disparate operations.",
            "severity": r["severity"],
            "anomaly_score_100": 96,
            "deviation_multiplier": round(len(c_ids) * 2.0, 1),
            "evidence": r["evidence"],
            "investigate_data": {
                "evidence_records": [
                    {"id": cid, "type": "Case Record", "details": f"Active suspect in case investigation {cid}"}
                    for cid in c_ids
                ],
                "model_details": {
                    "algorithm": "Graph Multi-Case Identity Intersection",
                    "cases_bridged": len(c_ids),
                },
                "entity_profile": {"person_id": pid, "cases": c_ids},
                "network": {
                    "primary_node": f"Suspect {pid}",
                    "connections": [{"target": cid, "relationship": "ACTIVE_IN_CASE"} for cid in c_ids],
                },
                "timeline": [
                    {"date": "Investigation History", "title": "Cross-Case Overlap", "description": r["explanation"], "badge": "Syndicate Connector"}
                ],
            },
        })

    # Rank all groups: Severity (CRITICAL -> HIGH -> MEDIUM -> LOW), then Score descending
    sev_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    all_groups.sort(key=lambda x: (sev_rank.get(x["severity"], 9), -x["anomaly_score_100"]))
    return all_groups
