"""
NLP Entity Extraction Engine
Extracts named entities (Person, Org, Location, Phone, Bank, Vehicle, IDs)
and candidate relationships from unstructured FIR narratives and statements.
"""

import re
import hashlib
from typing import Dict, List, Any, Tuple, Optional

class EntityExtractor:
    """
    Extracts structured entities and candidate links from police FIR text and witness statements.
    """

    # Indian Vehicle Number Regex (e.g. DL 01 AB 1234, MH-12-CD-5678, HR26BC9988)
    VEHICLE_REGEX = re.compile(
        r'\b([A-Z]{2}[-\s]?[0-9]{1,2}[-\s]?[A-Z]{1,3}[-\s]?[0-9]{4})\b',
        re.IGNORECASE
    )

    # Indian Mobile Phone Regex (10 digits, optional +91 or 0 prefix)
    PHONE_REGEX = re.compile(
        r'(?:\+91[-\s]?|0)?([6-9]\d{4}[-\s]?\d{5})\b'
    )

    # Indian Bank Account Numbers (9 to 18 digits)
    BANK_ACCOUNT_REGEX = re.compile(
        r'\b(?:A/c\s*(?:no\.?)?|Account\s*(?:no\.?)?|Acc\s*#?)\s*[:.-]?\s*([0-9]{9,18})\b',
        re.IGNORECASE
    )

    # IFSC Codes (4 letters + '0' + 6 alphanumeric)
    IFSC_REGEX = re.compile(
        r'\b([A-Z]{4}0[A-Z0-9]{6})\b'
    )

    # UPI IDs (e.g. name@okhdfcbank, fraud@paytm, user@ybl)
    UPI_REGEX = re.compile(
        r'\b([a-zA-Z0-9.\-_]{3,}@(okhdfcbank|okaxis|okicici|oksbi|paytm|ybl|apl|upi|axl|ibl))\b',
        re.IGNORECASE
    )

    # Indian PAN Card (5 uppercase letters + 4 digits + 1 letter)
    PAN_REGEX = re.compile(
        r'\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b'
    )

    # Aadhaar Number (12 digits, often formatted as 4-4-4)
    AADHAAR_REGEX = re.compile(
        r'\b([2-9]{1}[0-9]{3}[-\s]?[0-9]{4}[-\s]?[0-9]{4})\b'
    )

    # Aliases Regex (e.g. Accused Rajesh Sharma @ Bunty, Vikram Singh alias Vicky, Suresh aka Bhai)
    ALIAS_REGEX = re.compile(
        r'(?:accused|suspect|named)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:@|alias|aka|known as)\s*([A-Z][a-z0-9\-_]+(?:\s+[A-Z][a-z0-9\-_]+)?)'
    )

    # Known Indian Locations & Crime Hotspots
    COMMON_LOCATIONS = [
        "Nuh", "Mewat", "Jamtara", "Gurugram", "Noida", "Sector 62", "Salt Lake", "Kolkata",
        "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Ahmedabad", "Pune", "Jaipur", "Lucknow",
        "Chandigarh", "Patna", "Indore", "Bhopal", "Bhiwadi", "Alwar", "Deoghar", "Cyber City",
        "Lajpat Nagar", "Connaught Place", "Bandra", "Andheri", "Rohini", "Dwarka"
    ]

    # Organization / Gang Identifiers
    ORG_KEYWORDS = [
        "gang", "syndicate", "cartel", "pvt ltd", "enterprises", "solutions", "foundation",
        "network", "module", "cell", "traders", "holdings", "group", "finance", "travels"
    ]

    @staticmethod
    def normalize_phone(raw_phone: str) -> str:
        """Normalizes Indian phone numbers to 10 digits."""
        digits = re.sub(r'\D', '', raw_phone)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        elif digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        return digits[-10:] if len(digits) >= 10 else digits

    @staticmethod
    def hash_pii(value: str) -> str:
        """One-way SHA-256 hash for PII protection and deterministic matching."""
        clean = "".join(filter(str.isalnum, str(value).upper()))
        return hashlib.sha256(clean.encode()).hexdigest()[:16]

    def extract(self, narrative_text: str) -> Dict[str, Any]:
        """
        Main extraction function returning normalized entities and candidate relationships.
        """
        text = narrative_text.strip()
        entities = {
            "persons": [],
            "organizations": [],
            "locations": [],
            "phones": [],
            "financial_accounts": [],
            "vehicles": [],
            "identifications": [],
            "crime_mentions": []
        }

        # 1. Extract Phone Numbers
        for match in self.PHONE_REGEX.finditer(text):
            raw_phone = match.group(0).strip()
            norm_phone = self.normalize_phone(raw_phone)
            if len(norm_phone) == 10:
                p_hash = self.hash_pii(norm_phone)
                entities["phones"].append({
                    "raw": raw_phone,
                    "normalized": norm_phone,
                    "masked": f"{norm_phone[:3]}XXXX{norm_phone[-3:]}",
                    "phone_hash": p_hash
                })

        # 2. Extract Bank Accounts & UPI IDs
        for match in self.BANK_ACCOUNT_REGEX.finditer(text):
            acc_no = match.group(1).strip()
            entities["financial_accounts"].append({
                "type": "Bank Account",
                "account_number": acc_no,
                "masked": f"AC-XXXX{acc_no[-4:]}",
                "account_hash": self.hash_pii(acc_no)
            })

        for match in self.UPI_REGEX.finditer(text):
            upi_id = match.group(1).strip().lower()
            entities["financial_accounts"].append({
                "type": "UPI ID",
                "upi_id": upi_id,
                "masked": f"{upi_id[:3]}***@{upi_id.split('@')[-1]}",
                "account_hash": self.hash_pii(upi_id)
            })

        # 3. Extract Vehicles
        for match in self.VEHICLE_REGEX.finditer(text):
            plate = match.group(1).strip().upper().replace("-", " ")
            entities["vehicles"].append({
                "registration_number": plate,
                "vehicle_hash": self.hash_pii(plate)
            })

        # 4. Extract Identity Numbers (PAN / Aadhaar)
        for match in self.PAN_REGEX.finditer(text):
            pan = match.group(1).strip().upper()
            entities["identifications"].append({
                "type": "PAN",
                "value_masked": f"{pan[:2]}XXX{pan[-2:]}",
                "id_hash": self.hash_pii(pan)
            })

        for match in self.AADHAAR_REGEX.finditer(text):
            aadhaar = re.sub(r'\D', '', match.group(1).strip())
            if len(aadhaar) == 12:
                entities["identifications"].append({
                    "type": "Aadhaar",
                    "value_masked": f"XXXX-XXXX-{aadhaar[-4:]}",
                    "id_hash": self.hash_pii(aadhaar)
                })

        # 5. Extract Locations
        for loc in self.COMMON_LOCATIONS:
            pattern = re.compile(rf'\b{re.escape(loc)}\b', re.IGNORECASE)
            if pattern.search(text):
                entities["locations"].append({
                    "name": loc,
                    "type": "City/District/Hotspot"
                })

        # 6. Extract Aliases & Suspect Names
        for match in self.ALIAS_REGEX.finditer(text):
            main_name = match.group(1).strip()
            alias = match.group(2).strip()
            # Clean common title words
            main_name = re.sub(r'^(?:accused|suspect|named)\s+', '', main_name, flags=re.IGNORECASE).strip()
            if main_name:
                existing = next((p for p in entities["persons"] if p["name"].lower() == main_name.lower()), None)
                if existing:
                    if alias and alias not in existing["aliases"]:
                        existing["aliases"].append(alias)
                else:
                    entities["persons"].append({
                        "name": main_name,
                        "aliases": [alias] if alias else []
                    })

        # Fallback regex for Indian Name patterns (e.g. Accused Sunil Kumar, Suspect Imran Khan)
        NAME_TITLE_REGEX = re.compile(
            r'\b(?:accused|suspect|arrested|identified as|named|mastermind|driver|operative|person)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b',
            re.IGNORECASE
        )
        for match in NAME_TITLE_REGEX.finditer(text):
            name = match.group(1).strip()
            # Avoid picking up locations or days
            if not any(loc.lower() in name.lower() for loc in self.COMMON_LOCATIONS):
                existing = next((p for p in entities["persons"] if p["name"].lower() in name.lower() or name.lower() in p["name"].lower()), None)
                if not existing:
                    entities["persons"].append({
                        "name": name,
                        "aliases": []
                    })

        # 7. Extract Organizations / Gangs
        for kw in self.ORG_KEYWORDS:
            pattern = re.compile(rf'([A-Za-z0-9\s\-]{{3,30}}\s+{re.escape(kw)})\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                org_name = match.group(1).strip().title()
                if not any(o["name"].lower() == org_name.lower() for o in entities["organizations"]):
                    entities["organizations"].append({
                        "name": org_name,
                        "type": "Gang/Syndicate/Front Company"
                    })

        # Deduplicate results
        entities["phones"] = list({p["normalized"]: p for p in entities["phones"]}.values())
        entities["vehicles"] = list({v["registration_number"]: v for v in entities["vehicles"]}.values())
        entities["financial_accounts"] = list({f["account_hash"]: f for f in entities["financial_accounts"]}.values())
        entities["locations"] = list({l["name"]: l for l in entities["locations"]}.values())

        return entities
