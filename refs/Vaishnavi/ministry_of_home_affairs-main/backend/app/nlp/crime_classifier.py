"""
Crime Classification & Legal Section Mapping Module
Classifies case narratives into IPC / Bharatiya Nyaya Sanhita (BNS) crime categories
inspired by the I4C CyberGuard AI hackathon benchmarks.
"""

from typing import Dict, List, Any
import re

class CrimeClassifier:
    """
    Classifies FIR narratives into standardized crime categories and flags applicable legal sections.
    """

    CRIME_PROFILES = {
        "Cyber Fraud & Phishing": {
            "keywords": [
                "phishing", "cyber", "otp", "apk", "upi", "credit card", "bank fraud",
                "call center", "remote access", "anydesk", "teamviewer", "telegram scam",
                "part-time job", "investment fraud", "digital arrest", "fedex scam", "mewat", "jamtara"
            ],
            "ipc_sections": ["Sec 420 IPC (Cheating)", "Sec 419 IPC (Impersonation)", "Sec 66C/66D IT Act"],
            "bns_sections": ["Sec 318 BNS (Cheating)", "Sec 319 BNS (Cheating by Personation)"]
        },
        "Hawala & Terror Financing": {
            "keywords": [
                "hawala", "terror funding", "money laundering", "shell company", "cash courier",
                "unaccounted cash", "angadia", "cross-border", "dubai transfer", "crypto laundering",
                "fake invoices", "benami", "illicit money", "counterfeit"
            ],
            "ipc_sections": ["Sec 120B IPC (Criminal Conspiracy)", "Sec 121A IPC", "PMLA Act", "UAPA Sec 17/40"],
            "bns_sections": ["Sec 61 BNS (Criminal Conspiracy)", "Sec 147 BNS (Terrorist Acts)"]
        },
        "Organized Crime & Extortion": {
            "keywords": [
                "extortion", "ransom", "gangster", "threat call", "syndicate", "protection money",
                "mafia", "contract killing", "supari", "d-company", "lawrence", "bambiha", "shooter"
            ],
            "ipc_sections": ["Sec 384/386 IPC (Extortion)", "Sec 307 IPC (Attempt to Murder)", "MCOCA / GCTOC"],
            "bns_sections": ["Sec 308 BNS (Extortion)", "Sec 111 BNS (Organized Crime)"]
        },
        "Interstate Vehicle Theft": {
            "keywords": [
                "vehicle theft", "car lifting", "chassis number", "engine number", "fake rc",
                "stolen car", "chop shop", "interstate gang", "gps jammer", "scorpio", "creta", "fortuner"
            ],
            "ipc_sections": ["Sec 379 IPC (Theft)", "Sec 411 IPC (Dishonestly receiving stolen property)", "Sec 468 IPC (Forgery)"],
            "bns_sections": ["Sec 303 BNS (Theft)", "Sec 317 BNS (Stolen Property)", "Sec 336 BNS (Forgery)"]
        },
        "Narcotics & Drug Trafficking": {
            "keywords": [
                "narcotics", "contraband", "heroin", "mdma", "cocaine", "ganja", "charas",
                "mephedrone", "peddler", "courier", "consignment", "darknet drugs", "rave party"
            ],
            "ipc_sections": ["NDPS Act Sec 8/20/21/29 (Narcotic Drugs and Psychotropic Substances)"],
            "bns_sections": ["NDPS Act Provisions"]
        },
        "Fake Indian Currency Notes (FICN)": {
            "keywords": [
                "fake currency", "counterfeit notes", "ficn", "high quality fake notes", "printing press",
                "fake 500 notes", "cross-border smuggling", "courier network"
            ],
            "ipc_sections": ["Sec 489A/489B/489C IPC (Counterfeiting Currency Notes)"],
            "bns_sections": ["Sec 178/179/180 BNS (Counterfeiting)"]
        }
    }

    def classify(self, text: str) -> Dict[str, Any]:
        """
        Classify narrative text into the best-matching crime category.
        """
        lower_text = text.lower()
        best_category = "General IPC Crime"
        highest_score = 0
        applicable_sections = []
        matched_keywords = []

        for category, data in self.CRIME_PROFILES.items():
            score = 0
            curr_matched = []
            for kw in data["keywords"]:
                if re.search(rf'\b{re.escape(kw)}\b', lower_text):
                    score += 1
                    curr_matched.append(kw)

            if score > highest_score:
                highest_score = score
                best_category = category
                applicable_sections = data["ipc_sections"] + data["bns_sections"]
                matched_keywords = curr_matched

        confidence = min(round((highest_score / 4.0) * 100, 1), 98.0) if highest_score > 0 else 40.0

        return {
            "predicted_category": best_category if highest_score > 0 else "Cyber Fraud & Phishing",
            "confidence_percentage": confidence,
            "matched_keywords": matched_keywords,
            "applicable_legal_sections": applicable_sections
        }
