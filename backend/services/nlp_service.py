"""
NLP / OCR Extraction Service (Phase 5).
- Multi-category NER extraction on documents/CASEID/FIR_*.txt and WITNESS_*.txt
- Cross-matches against persons, organizations, locations, vehicles, and FIR records
- TF-IDF + Logistic Regression crime classification
- Rich entity metadata and chronological timeline extraction
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict
import pandas as pd

from backend.logging_config import logger

DATASET_ROOT = Path("dataset")
EVIDENCE_DIR = DATASET_ROOT / "evidence"
DOCUMENTS_DIR = EVIDENCE_DIR / "documents"

# ---------- spaCy (optional) ----------
try:
    import spacy
    _nlp = None
    for model_name in ["en_core_web_sm", "en_core_web_md", "en_core_web_lg"]:
        try:
            _nlp = spacy.load(model_name)
            logger.info(f"spaCy model loaded: {model_name}")
            break
        except OSError:
            continue
    if _nlp is None:
        logger.warning("No spaCy model found; NER will use high-precision lexicon + regex engine")
except ImportError:
    _nlp = None
    logger.warning("spaCy not installed; NER will use high-precision lexicon + regex engine")

# ---------- scikit-learn (optional) ----------
try:
    from sklearn.pipeline import Pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    _sklearn_available = True
except ImportError:
    _sklearn_available = False

CRIME_TRAINING_DATA = [
    ("murder assault stabbing shot fired weapon accused killed dead body", "Violent Crime"),
    ("dacoity robbery loot armed theft stolen house raided snatched gold", "Robbery/Dacoity"),
    ("drug narcotics ganja seized contraband trafficking heroin opium brown sugar", "Narcotics"),
    ("fraud cheating embezzlement forgery fake document unauthorized transfer cyber deceit", "Financial Fraud"),
    ("rape molestation sexual harassment victim women abducted dowry section 376", "Crime Against Women"),
    ("hawala money laundering transaction cash foreign mule structuring", "Money Laundering"),
    ("extortion kidnapping ransom abduction threatening ransom call blackmail", "Extortion/Kidnapping"),
    ("cyber phishing hacking online account identity theft otp scam sim swap", "Cybercrime"),
    ("vehicle theft car stolen registration motor bike lifted", "Vehicle Theft"),
    ("smuggling border goods customs illegal contraband consignment cross-border", "Smuggling-style Network"),
    ("courier packet delivery parcel narcotics contraband parcel transit courier-based", "Courier-based Criminal Network"),
    ("organised crime syndicate network gang cross-state operative interstate kingpin", "Organized Crime"),
]

_classifier_pipeline: Optional[Any] = None

def _build_classifier():
    global _classifier_pipeline
    if _classifier_pipeline is not None or not _sklearn_available:
        return
    texts = [t for t, _ in CRIME_TRAINING_DATA]
    labels = [l for _, l in CRIME_TRAINING_DATA]
    _classifier_pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=5000, min_df=1)),
        ("clf", LogisticRegression(max_iter=500, C=5.0, random_state=42)),
    ])
    _classifier_pipeline.fit(texts, labels)


def classify_crime(text: str) -> Dict[str, Any]:
    """Classify crime type from raw text using TF-IDF + LR or keyword fallback."""
    _build_classifier()
    text_lower = text.lower()

    if _classifier_pipeline and _sklearn_available:
        try:
            pred = _classifier_pipeline.predict([text])[0]
            proba = _classifier_pipeline.predict_proba([text])[0]
            classes = _classifier_pipeline.classes_
            confidence = float(proba.max())
            top3 = sorted(zip(classes, proba), key=lambda x: -x[1])[:3]
            return {
                "predicted_crime_type": pred,
                "confidence": round(confidence, 3),
                "top_predictions": [{"label": c, "score": round(s, 3)} for c, s in top3],
                "method": "tfidf_logistic_regression",
            }
        except Exception as e:
            logger.warning(f"Classifier error: {e}")

    keyword_map = {
        "Financial Fraud": ["unauthorized transfer", "fraud", "cheating", "embezzlement", "forgery", "account", "transfer"],
        "Courier-based Criminal Network": ["courier", "parcel", "consignment", "packet", "delivery"],
        "Smuggling-style Network": ["smuggling", "contraband", "cross-border", "customs", "border"],
        "Narcotics": ["drug", "narcotics", "ganja", "heroin", "contraband", "seized"],
        "Violent Crime": ["murder", "killed", "assault", "stabbed", "shot", "weapon"],
        "Crime Against Women": ["rape", "molestation", "harassment", "victim", "dowry"],
        "Robbery/Dacoity": ["robbery", "dacoity", "loot", "armed", "stolen"],
        "Money Laundering": ["hawala", "laundering", "transaction", "cash", "mule"],
        "Organized Crime": ["syndicate", "network", "gang", "organised", "associates"],
    }
    scores = {k: sum(1 for kw in kws if kw in text_lower) for k, kws in keyword_map.items()}
    best = max(scores, key=scores.get)
    return {
        "predicted_crime_type": best if scores[best] > 0 else "Under Investigation",
        "confidence": min(scores[best] * 0.25, 0.9) if scores[best] > 0 else 0.5,
        "top_predictions": [{"label": k, "score": round(v * 0.2, 2)} for k, v in sorted(scores.items(), key=lambda x: -x[1])[:3]],
        "method": "keyword_fallback",
    }


# ----------- Lexicon Cache for Instant High-Precision Entity Linking -----------
_KNOWN_PERSONS: Dict[str, str] = {}  # full_name -> person_id
_KNOWN_ORGS: Set[str] = set()
_KNOWN_LOCS: Set[str] = set()
_KNOWN_CITIES: Set[str] = set()
_KNOWN_VEHICLES: Set[str] = set()
_ENTITIES_LOADED = False

def _ensure_lexicon():
    global _KNOWN_PERSONS, _KNOWN_ORGS, _KNOWN_LOCS, _KNOWN_CITIES, _KNOWN_VEHICLES, _ENTITIES_LOADED
    if _ENTITIES_LOADED:
        return
    try:
        if (EVIDENCE_DIR / "persons.csv").exists():
            df = pd.read_csv(EVIDENCE_DIR / "persons.csv")
            for _, r in df.iterrows():
                if pd.notna(r.get("full_name")):
                    _KNOWN_PERSONS[str(r["full_name"]).strip()] = str(r.get("person_id", ""))
        if (EVIDENCE_DIR / "organizations.csv").exists():
            df = pd.read_csv(EVIDENCE_DIR / "organizations.csv")
            _KNOWN_ORGS = set(df["organization_name"].dropna().str.strip().tolist())
        if (EVIDENCE_DIR / "locations.csv").exists():
            df = pd.read_csv(EVIDENCE_DIR / "locations.csv")
            _KNOWN_LOCS = set(df["location_name"].dropna().str.strip().tolist())
            _KNOWN_CITIES = set(df["city"].dropna().str.strip().tolist())
        if (EVIDENCE_DIR / "vehicles.csv").exists():
            df = pd.read_csv(EVIDENCE_DIR / "vehicles.csv")
            _KNOWN_VEHICLES = set(df["registration_id"].dropna().str.strip().tolist())
    except Exception as e:
        logger.warning(f"Failed to load lexicon from CSV: {e}")
    _ENTITIES_LOADED = True


# ----------- Regex Patterns -----------
PHONE_RE = re.compile(r'(?:\+91|0)?[6-9]\d{9}')
VEHICLE_RE = re.compile(r'[A-Z]{2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,3}[-\s]?\d{4}')
DATE_RE = re.compile(r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b')
AMOUNT_RE = re.compile(r'(?:Rs\.?|INR|₹)\s?[\d,]+(?:\.\d{1,2})?|\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:rupees|lakh|crore|INR)\b', re.IGNORECASE)
CASE_ID_RE = re.compile(r'\bCASE\d{3,4}\b')
FIR_RE = re.compile(r'\bFIR(?:/\d{4}/\d{3}/\d{3}|[/-]?\d+)\b')
SECTION_RE = re.compile(r'(?:Section|Sec\.|IPC|BNS)\s?(?:\d+[A-Z]?(?:/\d+[A-Z]?)*)(?:\s+IPC|\s+BNS)?', re.IGNORECASE)

OFFENCE_PATTERNS = [
    r'\bunauthorized transfer\b',
    r'\bextortion\b',
    r'\bblackmail\b',
    r'\bmoney laundering\b',
    r'\bcontraband\b',
    r'\bnarcotics\b',
    r'\bstolen\b',
    r'\bburglary\b',
    r'\brobbery\b',
    r'\bforgery\b',
    r'\bcheating\b',
    r'\bfake document\b',
    r'\bassault\b',
    r'\bkidnapping\b',
    r'\bsmuggling\b',
    r'\btransit interception\b',
]

def extract_entities_from_text(text: str, doc_id: str = "", case_id: str = "") -> Dict[str, Any]:
    """
    Extract comprehensive named entities from FIR/witness documents:
    Persons, Organizations, Locations, Vehicles, Phones, Dates, Amounts,
    Offences, Legal sections, and Case/FIR identifiers.
    """
    _ensure_lexicon()
    entities: List[Dict[str, Any]] = []

    # 1. Exact Database Person Matching
    for name, pid in _KNOWN_PERSONS.items():
        if len(name) > 3 and name in text:
            for m in re.finditer(r'\b' + re.escape(name) + r'\b', text):
                entities.append({
                    "text": m.group(),
                    "label": "PERSON",
                    "entity_id": pid,
                    "start": m.start(),
                    "end": m.end(),
                    "confidence": 0.95,
                })

    # Contextual Name pattern (e.g. 'identified as Kirti Arora', 'resembled Radha Joshi', 'Karan S.')
    context_names = re.finditer(
        r'(?:identified as|resembled|contact with|present with|along with|individual identified as|accused|complainant|witness)\s+([A-Z][a-z]+(?:\s+[A-Z]\.|\s+[A-Z][a-z]+)+)',
        text
    )
    for m in context_names:
        matched_name = m.group(1)
        entities.append({
            "text": matched_name,
            "label": "PERSON",
            "start": m.start(1),
            "end": m.end(1),
            "confidence": 0.88,
        })

    # 2. Known Organizations
    for org in _KNOWN_ORGS:
        if len(org) > 4 and org in text:
            for m in re.finditer(re.escape(org), text):
                entities.append({
                    "text": m.group(),
                    "label": "ORG",
                    "start": m.start(),
                    "end": m.end(),
                    "confidence": 0.95,
                })

    # Generic Organization pattern
    org_pattern = re.finditer(r'\b[A-Z][A-Za-z0-9\s&]{2,30}(?:Group|Transport Services|Retail Stores|Constructions|Consulting|Pvt Ltd|Bank|Enterprises)\b', text)
    for m in org_pattern:
        entities.append({
            "text": m.group(),
            "label": "ORG",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.85,
        })

    # 3. Known Locations & Establishments
    for loc in _KNOWN_LOCS:
        if len(loc) > 4 and loc in text:
            for m in re.finditer(re.escape(loc), text):
                entities.append({
                    "text": m.group(),
                    "label": "LOC",
                    "start": m.start(),
                    "end": m.end(),
                    "confidence": 0.95,
                })

    # Generic Location / Establishment pattern
    loc_pattern = re.finditer(r'\b[A-Z][A-Za-z0-9\s]{2,35}(?:Restaurant|Dhaba|Hotel|Colony|Nagar|Market|Street|Road|Bazaar|Sector\s\d+|Industrial Estate|Station|Terminal|Yard|Enclave|Vihar)\b', text)
    for m in loc_pattern:
        entities.append({
            "text": m.group(),
            "label": "LOC",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.86,
        })

    # Known Cities
    for city in _KNOWN_CITIES:
        if len(city) > 3 and city in text:
            for m in re.finditer(r'\b' + re.escape(city) + r'\b', text):
                entities.append({
                    "text": m.group(),
                    "label": "GPE",
                    "start": m.start(),
                    "end": m.end(),
                    "confidence": 0.92,
                })

    # 4. Vehicles & Plate Registrations
    for m in VEHICLE_RE.finditer(text):
        entities.append({
            "text": m.group(),
            "label": "VEHICLE",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.94,
        })

    # Mention of observed vehicle
    veh_mention = re.finditer(r'\b(?:vehicle observed|vehicle matching(?: the description of)?)\b', text, re.IGNORECASE)
    for m in veh_mention:
        entities.append({
            "text": m.group(),
            "label": "VEHICLE_MENTION",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.85,
        })

    # 5. Phone numbers
    for m in PHONE_RE.finditer(text):
        entities.append({
            "text": m.group(),
            "label": "PHONE",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.95,
        })

    # 6. Dates
    for m in DATE_RE.finditer(text):
        entities.append({
            "text": m.group(),
            "label": "DATE",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.95,
        })

    # 7. Monetary Amounts
    for m in AMOUNT_RE.finditer(text):
        entities.append({
            "text": m.group(),
            "label": "MONEY",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.90,
        })

    # 8. Case ID & FIR references
    for m in CASE_ID_RE.finditer(text):
        entities.append({
            "text": m.group(),
            "label": "CASE_ID",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.99,
        })

    for m in FIR_RE.finditer(text):
        entities.append({
            "text": m.group(),
            "label": "FIR_REF",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.99,
        })

    # 9. Legal Sections
    for m in SECTION_RE.finditer(text):
        entities.append({
            "text": m.group(),
            "label": "LEGAL_SECTION",
            "start": m.start(),
            "end": m.end(),
            "confidence": 0.95,
        })

    # 10. Modus Operandi & Crime Keywords
    for pat in OFFENCE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            entities.append({
                "text": m.group(),
                "label": "MODUS_OPERANDI",
                "start": m.start(),
                "end": m.end(),
                "confidence": 0.90,
            })

    # Deduplicate overlapping entities (prefer longer text span or higher confidence)
    entities.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    unique_entities: List[Dict[str, Any]] = []
    last_end = -1
    for ent in entities:
        # Check if already covered by exact text or span overlap
        if ent["start"] >= last_end or not any(
            e["start"] <= ent["start"] and e["end"] >= ent["end"] for e in unique_entities
        ):
            unique_entities.append(ent)
            last_end = max(last_end, ent["end"])

    # Final sort by character start
    unique_entities.sort(key=lambda x: x["start"])

    return {
        "doc_id": doc_id,
        "case_id": case_id,
        "method": "hybrid_lexicon_ner",
        "entity_count": len(unique_entities),
        "entities": unique_entities,
    }


def process_case_documents(case_id: str) -> Dict[str, Any]:
    """Process all FIR and witness documents for a case with rich structured intelligence."""
    case_doc_dir = DOCUMENTS_DIR / case_id
    results = []
    all_entities_by_type: Dict[str, List[str]] = defaultdict(list)

    # Load official FIR metadata if available in CSV
    official_fir_meta: Optional[Dict[str, Any]] = None
    try:
        fir_csv = EVIDENCE_DIR / "fir.csv"
        if fir_csv.exists():
            f_df = pd.read_csv(fir_csv)
            case_firs = f_df[f_df["case_id"] == case_id]
            if not case_firs.empty:
                r = case_firs.iloc[0]
                official_fir_meta = {
                    "fir_id": str(r.get("fir_id", "")),
                    "fir_number": str(r.get("fir_number", "")),
                    "police_station_id": str(r.get("police_station_id", "")),
                    "registration_date": str(r.get("registration_date", "")),
                    "incident_date": str(r.get("incident_date", "")),
                    "incident_city": str(r.get("incident_city", "")),
                    "incident_area": str(r.get("incident_area", "")),
                    "crime_type": str(r.get("crime_type", "")),
                    "complainant_id": str(r.get("complainant_id", "")),
                    "summary": str(r.get("summary", "")),
                    "status": str(r.get("status", "")),
                }
    except Exception as e:
        logger.warning(f"Error loading official FIR metadata: {e}")

    if not case_doc_dir.exists():
        return {
            "case_id": case_id,
            "documents_found": 0,
            "official_fir": official_fir_meta,
            "results": [],
            "entity_summary": {},
        }

    doc_files = sorted(list(case_doc_dir.glob("*.txt")))
    for doc_file in doc_files:
        try:
            text = doc_file.read_text(encoding="utf-8", errors="ignore")
            doc_id = doc_file.stem
            ner_result = extract_entities_from_text(text, doc_id=doc_id, case_id=case_id)
            crime_class = classify_crime(text)

            # Detect document type
            doc_type = "FIR" if "FIR" in doc_file.name.upper() else "Witness Statement"

            result = {
                "doc_id": doc_id,
                "filename": doc_file.name,
                "document_type": doc_type,
                "char_count": len(text),
                "ner": ner_result,
                "crime_classification": crime_class,
                "full_text": text,
                "preview": text[:300] + "..." if len(text) > 300 else text,
            }
            results.append(result)

            for ent in ner_result["entities"]:
                all_entities_by_type[ent["label"]].append(ent["text"])

        except Exception as e:
            logger.warning(f"Failed to process {doc_file}: {e}")

    return {
        "case_id": case_id,
        "documents_found": len(doc_files),
        "official_fir": official_fir_meta,
        "results": results,
        "entity_summary": {k: list(dict.fromkeys(v))[:30] for k, v in all_entities_by_type.items()},
    }


def get_available_cases_with_documents() -> List[str]:
    """List all case IDs that have document directories."""
    if not DOCUMENTS_DIR.exists():
        return []
    return sorted([d.name for d in DOCUMENTS_DIR.iterdir() if d.is_dir()])
