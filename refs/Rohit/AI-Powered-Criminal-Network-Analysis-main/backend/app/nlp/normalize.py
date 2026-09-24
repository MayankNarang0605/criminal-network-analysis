"""
Indian law-enforcement text normalisation utilities.

Entity resolution quality depends almost entirely on normalisation quality, so
this module is deliberately explicit about Indian data conventions: 10-digit
mobile numbers with +91/0 prefixes, RTO vehicle plate spacing variants,
honorifics and initials in names, and bank account formatting.
"""
from __future__ import annotations

import re
import unicodedata

# Honorifics and rank prefixes that must not participate in name matching.
HONORIFICS = {
    "mr", "mrs", "ms", "miss", "shri", "smt", "sri", "kum", "dr", "prof",
    "md", "mohd", "sh", "late", "m/s", "messrs",
}
POLICE_RANKS = {
    "inspector", "insp", "si", "asi", "hc", "psi", "aci", "dsp", "acp", "dcp",
    "sp", "ssp", "ig", "dig", "adg", "dgp", "constable", "ct", "head",
    "sub", "assistant", "deputy", "superintendent", "commissioner", "officer",
    "cyber", "duty", "station",
}
NAME_SUFFIX_NOISE = {"alias", "aka", "a/k/a", "s/o", "d/o", "w/o", "c/o"}

# Role words that police prose prefixes onto names ("accused Vikram Desai").
# These must never become part of the identity key, or the same person splits
# into "Vikram Desai" and "Accused Vikram Desai".
ROLE_PREFIXES = {
    "accused", "coaccused", "co", "complainant", "victim", "deceased",
    "suspect", "absconding", "arrested", "informant", "witness", "petitioner",
    "respondent", "applicant", "detenue", "detainee", "juvenile",
}

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]")


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def squash(text: str) -> str:
    return _WS.sub(" ", (text or "").strip())


def normalize_phone(raw: str) -> str | None:
    """Return the canonical 10-digit Indian mobile number, or None."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    # Strip country/trunk prefixes.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 13 and digits.startswith("091"):
        digits = digits[3:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    # Landline numbers (STD code + subscriber): keep as-is if plausible.
    if 8 <= len(digits) <= 11:
        return digits
    return None


def normalize_vehicle(raw: str) -> str | None:
    """
    Canonicalise an Indian registration plate to compact uppercase form.
    'MH 02 AB 1234', 'MH02-AB-1234', 'mh02ab1234' -> 'MH02AB1234'
    """
    if not raw:
        return None
    compact = re.sub(r"[^A-Z0-9]", "", str(raw).upper())
    if re.fullmatch(r"[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}", compact):
        return compact
    return None


def normalize_account(raw: str) -> str | None:
    if not raw:
        return None
    value = str(raw).strip().upper()
    if value == "CASH":
        return "CASH"
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) >= 8 else None


def normalize_name(raw: str) -> str:
    """
    Canonical person/organisation name key.

    Drops honorifics, police ranks, punctuation and standalone initials so that
    'Inspector Rajesh Patil', 'Rajesh Patil', and 'Rajesh  Patil.' collapse to
    the same key, while 'Rajasekar M.' keeps its distinguishing token order.
    """
    if not raw:
        return ""
    text = strip_accents(str(raw)).lower()
    text = text.replace(".", " ").replace(",", " ")
    text = _NON_ALNUM.sub(" ", text)
    tokens = [t for t in squash(text).split(" ") if t]

    cleaned: list[str] = []
    for tok in tokens:
        if tok in HONORIFICS or tok in NAME_SUFFIX_NOISE:
            continue
        if tok in POLICE_RANKS and len(tokens) > 1:
            continue
        cleaned.append(tok)

    # Strip leading role words: "accused vikram desai" -> "vikram desai".
    while len(cleaned) > 1 and cleaned[0] in ROLE_PREFIXES:
        cleaned.pop(0)

    # Preserve at least one token even if everything looked like noise.
    if not cleaned:
        cleaned = tokens
    # Drop trailing single-letter initials ('rajasekar m' -> 'rajasekar')
    while len(cleaned) > 1 and len(cleaned[-1]) == 1:
        cleaned.pop()
    return " ".join(cleaned)


def normalize_location(raw: str) -> str:
    text = normalize_name(raw)
    # Common location noise words.
    for word in ("police station", "ps", "road", "rd", "nagar west", "district"):
        if text.endswith(" " + word):
            text = text[: -(len(word) + 1)]
    return squash(text)


def title_case(raw: str) -> str:
    return " ".join(w.capitalize() if w.islower() else w for w in squash(raw).split(" "))


def normalize_email(raw: str) -> str | None:
    if not raw:
        return None
    value = str(raw).strip().lower()
    return value if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", value) else None


def normalize_ifsc(raw: str) -> str | None:
    if not raw:
        return None
    value = re.sub(r"\s", "", str(raw).upper())
    return value if re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", value) else None
