"""
Entity Normalization & Resolution Engine (Phase 6).
Implements Indian law-enforcement normalization rules:
- Phones: +91 / 0 / 10-digit mobile normalization
- Vehicles: RTO plate canonicalization (e.g. 'HR 26 AB 1234' -> 'HR26AB1234')
- Names: Strip honorifics (Shri, Smt, Mohd, Dr), police ranks (SI, Insp), and suffixes (alias, s/o)
- Matching: Exact ID matching + RapidFuzz (Jaro-Winkler/Token Sort) + Contextual graph scoring
- Confidence bucketing: HIGH (>= 0.85), REVIEW (0.60 - 0.84), LOW (< 0.60)
"""
import re
import unicodedata
from typing import Optional, List, Dict, Any, Tuple
from rapidfuzz import fuzz, distance
from sqlalchemy.orm import Session

from backend.logging_config import logger
from backend.models.evidence import Person, Phone, Vehicle

# Law-enforcement noise words and prefixes
HONORIFICS = {
    "mr", "mrs", "ms", "miss", "shri", "smt", "sri", "kum", "dr", "prof",
    "md", "mohd", "mohammed", "mohammad", "sh", "late", "m/s", "messrs"
}

POLICE_RANKS = {
    "inspector", "insp", "si", "asi", "hc", "psi", "dsp", "acp", "dcp",
    "sp", "ssp", "ig", "dig", "constable", "ct", "sub", "officer"
}

ROLE_WORDS = {
    "accused", "coaccused", "suspect", "witness", "complainant", "victim", "informant"
}


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """Normalize Indian phone number to 10-digit canonical string."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 13 and digits.startswith("091"):
        digits = digits[3:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    if 8 <= len(digits) <= 11:
        return digits
    return None


def normalize_vehicle(raw: Optional[str]) -> Optional[str]:
    """Normalize Indian vehicle registration number (e.g. 'DL-01-AB-1234' -> 'DL01AB1234')."""
    if not raw:
        return None
    clean = re.sub(r"[^A-Za-z0-9]", "", str(raw)).upper()
    if re.fullmatch(r"[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}", clean):
        return clean
    return clean if len(clean) >= 6 else None


def normalize_name(raw: Optional[str]) -> str:
    """Normalize Indian name by removing titles, ranks, and noise."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKD", str(raw)).encode("ascii", "ignore").decode("utf-8").lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    filtered = [t for t in tokens if t not in HONORIFICS and t not in POLICE_RANKS and t not in ROLE_WORDS]
    return " ".join(filtered)


def calculate_match_score(
    p1: Dict[str, Any],
    p2: Dict[str, Any],
) -> Tuple[float, str, List[str]]:
    """
    Calculate confidence-weighted entity match score between two person profiles.
    Returns: (score, bucket, reasons)
    """
    reasons = []
    
    # Check exact phone match
    phones1 = {str(ph) for ph in p1.get("phones", []) if ph}
    phones2 = {str(ph) for ph in p2.get("phones", []) if ph}
    shared_phones = phones1.intersection(phones2)
    if shared_phones:
        reasons.append(f"Shared phone numbers: {', '.join(shared_phones)}")
        return 0.98, "HIGH", reasons

    # Check exact vehicle match
    veh1 = {str(v) for v in p1.get("vehicles", []) if v}
    veh2 = {str(v) for v in p2.get("vehicles", []) if v}
    shared_veh = veh1.intersection(veh2)
    if shared_veh:
        reasons.append(f"Shared vehicle registrations: {', '.join(shared_veh)}")
        return 0.95, "HIGH", reasons

    # Name similarity
    n1 = normalize_name(p1.get("full_name", ""))
    n2 = normalize_name(p2.get("full_name", ""))
    
    if not n1 or not n2:
        return 0.0, "LOW", []

    # Check alias match
    a1 = normalize_name(p1.get("alias", ""))
    a2 = normalize_name(p2.get("alias", ""))
    if (a1 and (a1 == n2 or a1 == a2)) or (a2 and (a2 == n1)):
        reasons.append("Exact alias alignment")
        base_score = 0.90
    else:
        # RapidFuzz token sort ratio & Jaro-Winkler
        token_score = fuzz.token_sort_ratio(n1, n2) / 100.0
        jw_score = distance.JaroWinkler.similarity(n1, n2)
        base_score = max(token_score, jw_score)

    # City & Contextual reinforcement
    city1 = (p1.get("city") or "").strip().lower()
    city2 = (p2.get("city") or "").strip().lower()
    
    if city1 and city2 and city1 == city2:
        base_score = min(1.0, base_score + 0.05)
        reasons.append(f"Common jurisdiction: {p1.get('city')}")

    # Age proximity
    age1 = p1.get("age")
    age2 = p2.get("age")
    if age1 and age2 and abs(age1 - age2) <= 2:
        base_score = min(1.0, base_score + 0.03)

    # Organization sharing
    orgs1 = set(filter(None, (p1.get("organization_ids") or "").split("|")))
    orgs2 = set(filter(None, (p2.get("organization_ids") or "").split("|")))
    shared_orgs = orgs1.intersection(orgs2)
    if shared_orgs:
        base_score = min(1.0, base_score + 0.10)
        reasons.append(f"Associated organization: {', '.join(shared_orgs)}")

    # Assign confidence bucket
    if base_score >= 0.85:
        bucket = "HIGH"
    elif base_score >= 0.60:
        bucket = "REVIEW"
    else:
        bucket = "LOW"

    return round(base_score, 3), bucket, reasons


def resolve_candidate_pairs(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """Scan persons and identify duplicate identities across cases."""
    persons = db.query(Person).all()
    profiles = []
    for p in persons:
        profiles.append({
            "person_id": p.person_id,
            "full_name": p.full_name,
            "alias": p.alias,
            "city": p.city,
            "age": p.age,
            "phones": [normalize_phone(ph) for ph in (p.phone_ids or "").split("|") if ph],
            "vehicles": [normalize_vehicle(v) for v in (p.vehicle_ids or "").split("|") if v],
            "organization_ids": p.organization_ids,
        })

    matches = []
    # Blocking by city or first initial for computational efficiency
    for i in range(len(profiles)):
        p1 = profiles[i]
        for j in range(i + 1, min(i + 40, len(profiles))):
            p2 = profiles[j]
            score, bucket, reasons = calculate_match_score(p1, p2)
            if bucket in ("HIGH", "REVIEW"):
                matches.append({
                    "entity_a_id": p1["person_id"],
                    "entity_a_name": p1["full_name"],
                    "entity_b_id": p2["person_id"],
                    "entity_b_name": p2["full_name"],
                    "match_score": score,
                    "confidence_bucket": bucket,
                    "evidence_reasons": reasons,
                })
                if len(matches) >= limit:
                    return matches
    return matches


def score_entity_pair(mention_a: str, mention_b: str) -> Dict[str, Any]:
    """
    Score a pair of entity name/mention strings for resolution.
    Used for benchmark evaluation and ad-hoc resolution checks.
    """
    reasons = []
    # Clean quotes and whitespace
    clean_a = re.sub(r'["\']', '', str(mention_a or "")).strip()
    clean_b = re.sub(r'["\']', '', str(mention_b or "")).strip()
    
    if not clean_a or not clean_b:
        return {"score": 0.0, "bucket": "LOW", "reasons": ["Empty mention"]}

    norm_a = normalize_name(clean_a)
    norm_b = normalize_name(clean_b)

    if norm_a == norm_b and norm_a:
        return {"score": 1.0, "bucket": "HIGH", "reasons": ["Exact normalized name match"]}

    # Initial + Last name match (e.g., "R. Mishra" and "Ritu Mishra", or "Tarun Malhotra" and "Tarun M.")
    toks_a = norm_a.split()
    toks_b = norm_b.split()
    
    initial_match = False
    if len(toks_a) == 2 and len(toks_b) == 2:
        # First word initial or second word initial
        if toks_a[1] == toks_b[1] and (toks_a[0].startswith(toks_b[0][0]) or toks_b[0].startswith(toks_a[0][0])):
            initial_match = True
            reasons.append("Initial and surname concordance")
        elif toks_a[0] == toks_b[0] and (toks_a[1].startswith(toks_b[1][0]) or toks_b[1].startswith(toks_a[1][0])):
            initial_match = True
            reasons.append("Given name and initial concordance")
    elif (len(toks_a) == 1 and len(toks_b) >= 2) or (len(toks_b) == 1 and len(toks_a) >= 2):
        # Nickname / alias prefix (e.g. "Bhau" / "Bhavna", "Vidu" / "Vidya")
        short_t = toks_a[0] if len(toks_a) == 1 else toks_b[0]
        long_toks = toks_b if len(toks_a) == 1 else toks_a
        for lt in long_toks:
            if len(short_t) >= 3 and (lt.startswith(short_t[:3]) or short_t.startswith(lt[:3])):
                initial_match = True
                reasons.append(f"Informal alias stem matching '{short_t}'")
                break

    # RapidFuzz similarity
    token_score = fuzz.token_sort_ratio(norm_a, norm_b) / 100.0
    jw_score = distance.JaroWinkler.similarity(norm_a, norm_b)
    best_sim = max(token_score, jw_score)

    if initial_match:
        best_sim = max(best_sim, 0.88)

    if best_sim >= 0.82:
        bucket = "HIGH"
        reasons.append(f"High phonetic/lexical similarity ({best_sim:.2f})")
    elif best_sim >= 0.60:
        bucket = "REVIEW"
        reasons.append(f"Moderate lexical similarity ({best_sim:.2f})")
    else:
        bucket = "LOW"

    return {"score": round(best_sim, 3), "bucket": bucket, "reasons": reasons}


# Alias for backward compatibility
resolve_entities = resolve_candidate_pairs

