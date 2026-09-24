"""
Entity extraction engine for Indian police records.

Design rationale
----------------
Generic English NER models (spaCy `en_core_web_sm`, BERT-CoNLL) score poorly on
Indian FIR text: they miss Indian personal names, mangle 10-digit mobile numbers,
never recognise RTO plates or IPC citations, and split names on honorifics. This
engine is therefore a *hybrid*:

  1. High-precision deterministic extractors for the structured identifiers that
     actually drive investigations (phone, vehicle, account, IFSC, IPC section,
     crypto wallet, email, currency amount, dates).
  2. A gazetteer + morphological recogniser for Indian person names and
     organisation forms, seeded from the structured fields of the same corpus
     (accused/complainant lists) so it self-bootstraps.
  3. Cue-phrase relation extraction over the sentence graph, which yields typed,
     directed relationships with an evidence span for every edge.

Every extraction carries `start`/`end` character offsets, so the UI can highlight
the exact sentence that justified an edge. That evidence trail is the difference
between a demo and something an investigator could defend in court.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Iterable

from app.nlp import normalize as nz

# ---------------------------------------------------------------------------
# Deterministic patterns
# ---------------------------------------------------------------------------
RE_PHONE = re.compile(r"(?<!\d)(?:\+?91[\-\s]?|0)?([6-9]\d{9})(?!\d)")
RE_VEHICLE = re.compile(
    r"\b([A-Z]{2}[\s\-]?\d{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?\d{1,4})\b"
)
RE_ACCOUNT = re.compile(
    r"(?:a/?c(?:count)?\.?\s*(?:no\.?|number)?\s*|account\s+no\.?\s*)?(?<!\d)(\d{11,18})(?!\d)",
    re.IGNORECASE,
)
RE_BANK_ACCOUNT_CUE = re.compile(
    r"\b(SBI|HDFC|ICICI|Axis|Kotak|PNB|BOI|UBI|Canara|Yes\s?Bank|IDBI|IndusInd|"
    r"Bank\s+of\s+Baroda|Union\s+Bank|Punjab\s+National\s+Bank|Paytm|PhonePe|GPay)"
    r"[^\d]{0,40}(\d{8,18})", re.IGNORECASE,
)
RE_IFSC = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
RE_EMAIL = re.compile(r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")
RE_CRYPTO = re.compile(r"\b((?:bc1|[13])[a-km-zA-HJ-NP-Z0-9]{25,39}|0x[a-fA-F0-9]{40})\b")
RE_AADHAAR = re.compile(r"(?<!\d)(\d{4}\s?\d{4}\s?\d{4})(?!\d)")
RE_PAN = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b")
RE_IMEI = re.compile(r"\bIMEI[:\s]*(\d{15})\b", re.IGNORECASE)
RE_IPC = re.compile(
    r"\b(?:u/s|under\s+section|sections?|IPC|BNS)\s*[:\-]?\s*((?:\d{1,3}[A-Z]?)(?:\s*(?:,|and|&|/)\s*\d{1,3}[A-Z]?)*)",
    re.IGNORECASE,
)
RE_MONEY = re.compile(
    r"(?:Rs\.?|INR|₹)\s?([\d,]+(?:\.\d+)?)\s*(crore[s]?|cr|lakh[s]?|lac[s]?|thousand|k)?",
    re.IGNORECASE,
)
RE_DATE = re.compile(
    r"\b(\d{1,2}[\-/](?:\d{1,2}|[A-Za-z]{3,9})[\-/]\d{2,4}|\d{4}-\d{2}-\d{2})\b"
)

MONEY_MULT = {
    "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
    "thousand": 1e3, "k": 1e3,
}

# Words that look like plates but are not (state codes only appear with digits,
# so the main false-positive source is acronym + number sequences).
VEHICLE_STOP = {"FIR", "IPC", "PS", "NDPS", "POCSO", "PMLA", "CDR", "NCRB"}

# Valid Indian RTO state codes — the single most effective plate filter.
RTO_CODES = {
    "AN","AP","AR","AS","BR","CG","CH","DD","DL","DN","GA","GJ","HP","HR","JH",
    "JK","KA","KL","LA","LD","MH","ML","MN","MP","MZ","NL","OD","OR","PB","PY",
    "RJ","SK","TN","TR","TS","UK","UA","UP","WB",
}

ORG_SUFFIXES = (
    "pvt ltd", "private limited", "ltd", "limited", "llp", "enterprises",
    "enterprise", "trading", "traders", "constructions", "construction",
    "realtors", "realty", "solutions", "technologies", "industries", "corp",
    "corporation", "company", "co", "associates", "group", "syndicate",
    "consultancy", "services", "exports", "imports", "logistics", "holdings",
    "developers", "builders", "infra", "finance", "capital", "gang",
)

# Indian first-name / surname fragments used by the morphological recogniser.
NAME_HINTS = {
    "kumar","singh","sharma","verma","gupta","patel","reddy","rao","nair","menon",
    "iyer","pillai","das","dutta","banerjee","chatterjee","mukherjee","ghosh","bose",
    "mondal","roy","sen","khan","ahmed","ali","hussain","sheikh","qureshi","ansari",
    "syed","desai","joshi","kulkarni","patil","deshmukh","shinde","jadhav","pawar",
    "mishra","tiwari","pandey","yadav","thakur","chauhan","rathore","gujjar","meena",
    "shah","mehta","bhatt","prajapati","chaudhary","saxena","srivastava","agarwal",
    "jain","bansal","goyal","malhotra","kapoor","chopra","sethi","arora","bhatia",
    "naidu","gowda","shetty","hegde","kamath","prasad","murthy","subramanian",
    "krishnan","raman","sundaram","natarajan","balaji","venkatesh","mohan","anand",
    "devi","kaur","begum","bai","amma",
}

ROLE_CUES = {
    "kingpin": ["kingpin", "mastermind", "ring leader", "ringleader", "head of the",
                "leads the", "runs the network", "runs the", "operating from",
                "prime accused", "main accused", "syndicate head", "boss"],
    "lieutenant": ["coordinator", "coordinating", "handler", "manages", "managing",
                   "second in command", "handles operations", "manages operations",
                   "co-accused", "deputy", "recruits", "supervises"],
    "operative": ["carried out", "executed", "handles", "specializes in",
                  "responsible for", "performed"],
    "courier": ["courier", "transport", "transporting", "delivered", "carrier",
                "mule", "money mule", "handles transport"],
    "financier": ["financed", "funded", "hawala", "financier", "invested",
                  "laundering", "launder"],
    "facilitator": ["forged", "forging", "document forger", "broker", "arranged",
                    "facilitated", "provided cover", "political connections"],
}

RELATION_CUES: list[tuple[str, str, float]] = [
    # (regex cue, relationship type, base confidence)
    (r"\balong\s+with\b", "ASSOCIATE_OF", 0.85),
    (r"\bassociate[s]?\b", "ASSOCIATE_OF", 0.85),
    (r"\bco[\-\s]?accused\b", "CO_ACCUSED", 0.9),
    (r"\bconspir(?:ed|acy)\s+with\b", "CONSPIRED_WITH", 0.9),
    (r"\btogether\s+with\b", "ASSOCIATE_OF", 0.8),
    (r"\bconnected\s+to\b", "LINKED_TO", 0.7),
    (r"\blinks?\s+(?:found\s+)?to\b", "LINKED_TO", 0.7),
    (r"\bworks?\s+(?:for|under)\b", "WORKS_FOR", 0.85),
    (r"\breports?\s+to\b", "REPORTS_TO", 0.9),
    (r"\bcoordinat(?:es|ing|ed)\s+through\b", "DIRECTS", 0.85),
    (r"\binstructed\b", "DIRECTS", 0.85),
    (r"\bhandles?\b", "OPERATES_FOR", 0.7),
    (r"\brecruit(?:s|ed|ing)\b", "RECRUITED_BY", 0.8),
    (r"\bpaid\b", "PAID", 0.75),
    (r"\btransferred\s+to\b", "TRANSFERRED_TO", 0.85),
    (r"\bmet\s+(?:with)?\b", "MET_WITH", 0.7),
    (r"\bharbour(?:ed|ing)\b", "HARBOURED", 0.8),
]


@dataclass
class Extraction:
    """One extracted mention with its evidence span."""
    text: str
    value: str
    type: str
    start: int
    end: int
    confidence: float
    extractor: str
    context: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractedRelation:
    source: str
    source_type: str
    target: str
    target_type: str
    rel_type: str
    confidence: float
    cue: str
    sentence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractionResult:
    entities: list[Extraction] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
    roles: dict[str, str] = field(default_factory=dict)
    amounts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "roles": self.roles,
            "amounts": self.amounts,
            "counts": self.counts(),
        }

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entities:
            out[e.type] = out.get(e.type, 0) + 1
        return out


def _context(text: str, start: int, end: int, window: int = 70) -> str:
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    return ("…" if lo > 0 else "") + nz.squash(text[lo:hi]) + ("…" if hi < len(text) else "")


def _split_sentences(text: str) -> list[tuple[str, int]]:
    """Sentence split that tolerates 'Rs.', 'No.', initials and section numbers."""
    sentences: list[tuple[str, int]] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ".!?\n":
            tail = text[max(0, i - 4):i + 1].lower()
            # Do not break on abbreviations or single initials.
            if ch == "." and re.search(r"(?:\brs|\bno|\bmr|\bsmt|\bshri|\bdr|\bu/s|\s[a-z])\.$", tail):
                i += 1
                continue
            if ch == "." and i + 1 < n and text[i + 1].isdigit():
                i += 1
                continue
            chunk = text[start:i + 1].strip()
            if chunk:
                sentences.append((chunk, start))
            start = i + 1
        i += 1
    if start < n:
        chunk = text[start:].strip()
        if chunk:
            sentences.append((chunk, start))
    return sentences


class EntityExtractor:
    """
    Hybrid extractor. `known_people` / `known_orgs` are gazetteers harvested from
    the structured portion of the corpus, which lets the recogniser reach high
    recall on Indian names without a trained model.
    """

    def __init__(
        self,
        known_people: Iterable[str] = (),
        known_orgs: Iterable[str] = (),
        known_locations: Iterable[str] = (),
    ) -> None:
        self.people = {nz.normalize_name(p): p for p in known_people if p}
        self.orgs = {nz.normalize_name(o): o for o in known_orgs if o}
        self.locations = {nz.normalize_location(l): l for l in known_locations if l}
        self._people_regex = self._build_gazetteer_regex(self.people.values())
        self._org_regex = self._build_gazetteer_regex(self.orgs.values())
        self._loc_regex = self._build_gazetteer_regex(self.locations.values())

    # -- gazetteer ---------------------------------------------------------
    @staticmethod
    def _build_gazetteer_regex(values: Iterable[str]) -> re.Pattern | None:
        terms = sorted({v.strip() for v in values if v and len(v.strip()) > 2},
                       key=len, reverse=True)
        if not terms:
            return None
        alts = "|".join(re.escape(t) for t in terms)
        return re.compile(rf"\b({alts})\b", re.IGNORECASE)

    def add_person(self, name: str) -> None:
        key = nz.normalize_name(name)
        if key and key not in self.people:
            self.people[key] = name
            self._people_regex = self._build_gazetteer_regex(self.people.values())

    # -- main entry point --------------------------------------------------
    def extract(self, text: str) -> ExtractionResult:
        text = text or ""
        result = ExtractionResult()
        seen: set[tuple[str, str, int]] = set()

        def add(ex: Extraction) -> None:
            key = (ex.type, ex.value, ex.start)
            if key in seen:
                return
            seen.add(key)
            ex.context = _context(text, ex.start, ex.end)
            result.entities.append(ex)

        # --- 1. structured identifiers ---
        for m in RE_PHONE.finditer(text):
            value = nz.normalize_phone(m.group(1))
            if value:
                add(Extraction(m.group(0), value, "Phone", m.start(), m.end(), 0.99, "regex:phone"))

        for m in RE_VEHICLE.finditer(text):
            raw = m.group(1)
            value = nz.normalize_vehicle(raw)
            if not value or value[:2] not in RTO_CODES or raw.strip().upper() in VEHICLE_STOP:
                continue
            add(Extraction(raw, value, "Vehicle", m.start(1), m.end(1), 0.95, "regex:rto-plate"))

        for m in RE_IFSC.finditer(text):
            value = nz.normalize_ifsc(m.group(1))
            if value:
                add(Extraction(m.group(1), value, "IFSC", m.start(1), m.end(1), 0.99, "regex:ifsc"))

        for m in RE_BANK_ACCOUNT_CUE.finditer(text):
            bank, acct = m.group(1), nz.normalize_account(m.group(2))
            if acct:
                # Span must cover exactly the account digits so the UI can
                # highlight the identifier itself, not the surrounding phrase.
                add(Extraction(m.group(2), acct, "BankAccount", m.start(2), m.end(2), 0.97,
                               "regex:bank-cue"))
                add(Extraction(m.group(1), nz.title_case(bank), "Bank", m.start(1), m.end(1), 0.9,
                               "regex:bank-name"))

        for m in RE_ACCOUNT.finditer(text):
            acct = nz.normalize_account(m.group(1))
            if acct and len(acct) >= 11:
                add(Extraction(m.group(1), acct, "BankAccount", m.start(1), m.end(1), 0.8,
                               "regex:account"))

        for m in RE_EMAIL.finditer(text):
            value = nz.normalize_email(m.group(1))
            if value:
                add(Extraction(m.group(1), value, "Email", m.start(1), m.end(1), 0.99, "regex:email"))

        for m in RE_CRYPTO.finditer(text):
            add(Extraction(m.group(1), m.group(1), "CryptoWallet", m.start(1), m.end(1), 0.95,
                           "regex:crypto"))

        for m in RE_PAN.finditer(text):
            add(Extraction(m.group(1), m.group(1), "PAN", m.start(1), m.end(1), 0.9, "regex:pan"))

        for m in RE_AADHAAR.finditer(text):
            digits = re.sub(r"\s", "", m.group(1))
            add(Extraction(m.group(1), digits, "Aadhaar", m.start(1), m.end(1), 0.75, "regex:aadhaar"))

        for m in RE_IMEI.finditer(text):
            add(Extraction(m.group(1), m.group(1), "IMEI", m.start(1), m.end(1), 0.95, "regex:imei"))

        for m in RE_IPC.finditer(text):
            block = m.group(1)
            block_start = m.start(1)
            # Emit one mention per section with its own offsets, so '420, 468, 471'
            # highlights three separate citations rather than one blob.
            for sm in re.finditer(r"\d{1,3}[A-Z]?", block):
                sec = sm.group(0).strip().upper()
                if sec:
                    add(Extraction(sm.group(0), sec, "LegalSection",
                                   block_start + sm.start(), block_start + sm.end(),
                                   0.9, "regex:ipc"))

        for m in RE_MONEY.finditer(text):
            raw_amount = m.group(1).replace(",", "")
            try:
                amount = float(raw_amount)
            except ValueError:
                continue
            unit = (m.group(2) or "").lower()
            amount *= MONEY_MULT.get(unit, 1.0)
            result.amounts.append({
                "text": m.group(0),
                "amount_inr": amount,
                "start": m.start(),
                "end": m.end(),
                "context": _context(text, m.start(), m.end()),
            })

        for m in RE_DATE.finditer(text):
            add(Extraction(m.group(1), m.group(1), "Date", m.start(1), m.end(1), 0.85, "regex:date"))

        # --- 2. gazetteer entities ---
        for regex, etype, extractor in (
            (self._people_regex, "Person", "gazetteer:person"),
            (self._org_regex, "Organization", "gazetteer:org"),
            (self._loc_regex, "Location", "gazetteer:location"),
        ):
            if regex is None:
                continue
            for m in regex.finditer(text):
                surface = m.group(1)
                canon = (nz.normalize_name(surface) if etype != "Location"
                         else nz.normalize_location(surface))
                add(Extraction(surface, canon, etype, m.start(1), m.end(1), 0.95, extractor))

        # --- 3. morphological person / organisation discovery ---
        for ex in self._discover_names(text):
            add(ex)

        result.entities.sort(key=lambda e: e.start)

        # --- 4. relations and roles ---
        result.relations = self._extract_relations(text, result.entities)
        result.roles = self._extract_roles(text, result.entities)
        return result

    # -- unsupervised name discovery ---------------------------------------
    def _discover_names(self, text: str) -> list[Extraction]:
        """
        Find capitalised token runs that look like Indian personal or
        organisation names, using surname hints and organisation suffixes.
        Deliberately conservative: precision matters more than recall here
        because the gazetteer already covers the structured fields.
        """
        out: list[Extraction] = []
        # Capitalised runs, allowing internal initials like 'Rajasekar M.'
        pattern = re.compile(r"\b([A-Z][a-z]{1,}(?:\s+(?:[A-Z][a-z]{1,}|[A-Z]\.))*)\b")
        for m in pattern.finditer(text):
            surface = m.group(1).strip()
            tokens = surface.replace(".", "").split()
            if len(tokens) < 2:
                continue
            lower = surface.lower()

            if any(lower.endswith(" " + suf) or f" {suf} " in f" {lower} " for suf in ORG_SUFFIXES):
                out.append(Extraction(surface, nz.normalize_name(surface), "Organization",
                                      m.start(1), m.end(1), 0.75, "morph:org-suffix"))
                continue

            if any(t.lower() in NAME_HINTS for t in tokens):
                norm = nz.normalize_name(surface)
                if norm and len(norm) > 3:
                    out.append(Extraction(surface, norm, "Person", m.start(1), m.end(1),
                                          0.72, "morph:name-hint"))
        return out

    # -- relation extraction -----------------------------------------------
    def _extract_relations(
        self, text: str, entities: list[Extraction]
    ) -> list[ExtractedRelation]:
        relations: list[ExtractedRelation] = []
        sentences = _split_sentences(text)

        for sentence, offset in sentences:
            s_end = offset + len(sentence)
            in_sentence = [e for e in entities if e.start >= offset and e.end <= s_end]
            people = [e for e in in_sentence if e.type == "Person"]
            others = [e for e in in_sentence if e.type in
                      ("Organization", "Phone", "Vehicle", "BankAccount", "Location",
                       "Email", "CryptoWallet")]

            matched_cues = [(pat, rtype, conf) for pat, rtype, conf in RELATION_CUES
                            if re.search(pat, sentence, re.IGNORECASE)]

            # Person-to-person edges.
            uniq_people: dict[str, Extraction] = {}
            for p in people:
                uniq_people.setdefault(p.value, p)
            plist = list(uniq_people.values())

            for i in range(len(plist)):
                for j in range(i + 1, len(plist)):
                    a, b = plist[i], plist[j]
                    if matched_cues:
                        # Prefer the cue lying between the two mentions.
                        best = None
                        for pat, rtype, conf in matched_cues:
                            for cm in re.finditer(pat, sentence, re.IGNORECASE):
                                abs_pos = offset + cm.start()
                                between = a.end <= abs_pos <= b.start
                                score = conf + (0.08 if between else 0.0)
                                if best is None or score > best[0]:
                                    best = (score, rtype, cm.group(0))
                        score, rtype, cue = best  # type: ignore[misc]
                        relations.append(ExtractedRelation(
                            a.value, "Person", b.value, "Person", rtype,
                            round(min(score, 0.98), 3), cue, nz.squash(sentence)))
                    else:
                        relations.append(ExtractedRelation(
                            a.value, "Person", b.value, "Person", "CO_MENTIONED",
                            0.55, "co-occurrence", nz.squash(sentence)))

            # Person-to-attribute edges (phone/vehicle/account/org/location).
            rel_for_type = {
                "Phone": "USES_PHONE",
                "Vehicle": "USES_VEHICLE",
                "BankAccount": "CONTROLS_ACCOUNT",
                "Organization": "AFFILIATED_WITH",
                "Location": "OPERATES_IN",
                "Email": "USES_EMAIL",
                "CryptoWallet": "CONTROLS_WALLET",
            }
            for p in plist:
                for o in others:
                    # Attach to the nearest person mention only.
                    nearest = min(plist, key=lambda x: min(abs(x.start - o.start),
                                                           abs(x.end - o.end)))
                    if nearest.value != p.value:
                        continue
                    distance = min(abs(p.start - o.start), abs(p.end - o.end))
                    conf = 0.85 if distance < 60 else 0.65
                    relations.append(ExtractedRelation(
                        p.value, "Person", o.value, o.type,
                        rel_for_type.get(o.type, "RELATED_TO"),
                        conf, "proximity", nz.squash(sentence)))

        # Deduplicate, keeping the highest-confidence observation.
        best: dict[tuple, ExtractedRelation] = {}
        for r in relations:
            key = (r.source, r.target, r.rel_type)
            if key not in best or r.confidence > best[key].confidence:
                best[key] = r
        return list(best.values())

    # -- role inference ----------------------------------------------------
    def _extract_roles(self, text: str, entities: list[Extraction]) -> dict[str, str]:
        """Assign a hierarchy role to persons based on nearby command cues."""
        roles: dict[str, tuple[str, int]] = {}
        people = [e for e in entities if e.type == "Person"]
        lower = text.lower()

        priority = {"kingpin": 6, "lieutenant": 5, "financier": 4,
                    "facilitator": 3, "courier": 2, "operative": 1}

        for role, cues in ROLE_CUES.items():
            for cue in cues:
                for m in re.finditer(re.escape(cue), lower):
                    pos = m.start()
                    near = [p for p in people if abs(p.start - pos) < 110]
                    if not near:
                        continue
                    target = min(near, key=lambda p: abs(p.start - pos))
                    rank = priority[role]
                    current = roles.get(target.value)
                    if current is None or rank > current[1]:
                        roles[target.value] = (role, rank)
        return {name: role for name, (role, _) in roles.items()}


def summarise(text: str, max_sentences: int = 3) -> str:
    """
    Extractive summary: rank sentences by density of investigative signal
    (identifiers, money, role cues) and return the top ones in original order.
    """
    sentences = _split_sentences(text or "")
    if not sentences:
        return ""
    scored: list[tuple[float, int, str]] = []
    for idx, (sentence, _) in enumerate(sentences):
        score = 0.0
        score += 2.0 * len(RE_PHONE.findall(sentence))
        score += 2.0 * len(RE_MONEY.findall(sentence))
        score += 1.5 * len(RE_VEHICLE.findall(sentence))
        score += 1.5 * len(RE_ACCOUNT.findall(sentence))
        low = sentence.lower()
        for cues in ROLE_CUES.values():
            score += 2.0 * sum(1 for c in cues if c in low)
        score += min(len(sentence) / 200.0, 1.0)
        scored.append((score, idx, sentence))
    top = sorted(scored, key=lambda t: -t[0])[:max_sentences]
    return " ".join(s for _, _, s in sorted(top, key=lambda t: t[1]))
