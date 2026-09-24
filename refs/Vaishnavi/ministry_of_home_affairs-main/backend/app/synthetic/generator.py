"""
Synthetic Criminal Dataset Generator
Generates realistic Indian law-enforcement cases, suspects, bank accounts,
vehicles, phone records, and multi-jurisdictional syndicate graphs.
"""

from typing import Dict, List, Any
import random
from datetime import datetime, timedelta, timezone
from faker import Faker

from backend.app.graph.engine import CriminalGraphEngine
from backend.app.database.connection import SessionLocal
from backend.app.database.models import CaseRecord
from backend.app.nlp.entity_extractor import EntityExtractor

fake = Faker('en_IN')

class SyntheticDataGenerator:
    """
    Generates interconnected, multi-jurisdiction criminal networks for testing and demonstration.
    """
    def __init__(self, engine: CriminalGraphEngine):
        self.engine = engine
        self.extractor = EntityExtractor()

    def generate_all_scenarios(self, reset_first: bool = True) -> Dict[str, Any]:
        """Populates the database and graph with 3 rich, realistic Indian crime syndicates."""
        if reset_first:
            self.engine.clear()

        db = SessionLocal()
        try:
            if reset_first:
                db.query(CaseRecord).delete()
                db.commit()

            c1 = self._build_cyber_fraud_syndicate(db)
            c2 = self._build_hawala_narco_syndicate(db)
            c3 = self._build_vehicle_theft_syndicate(db)

            # Persist graph to disk
            self.engine.save_to_disk()

            stats = self.engine.get_stats()
            return {
                "success": True,
                "message": "Successfully initialized synthetic criminal networks.",
                "total_cases_seeded": 9,
                "graph_stats": stats
            }
        finally:
            db.close()

    def _build_cyber_fraud_syndicate(self, db) -> List[str]:
        """Syndicate 1: Mewat-Kolkata-Delhi Interstate Phishing & Investment Scam Ring."""
        # 1. Nodes - Masterminds & Operatives
        p_farhan = self.engine.add_node("P_FARHAN_01", "Person", "Mohammed Farhan", {
            "aliases": ["Doctor", "Farhan Mewati"],
            "gender": "Male",
            "phone": "9810188234",
            "phone_hash": self.extractor.hash_pii("9810188234"),
            "national_id_hash": self.extractor.hash_pii("ABCDE1234F"),
            "status": "Wanted / Kingpin",
            "state_origin": "Haryana"
        })

        p_aftab = self.engine.add_node("P_AFTAB_02", "Person", "Aftab Alam", {
            "aliases": ["Prince", "Tech Head"],
            "gender": "Male",
            "phone": "9871144210",
            "phone_hash": self.extractor.hash_pii("9871144210"),
            "status": "Arrested",
            "state_origin": "Jharkhand"
        })

        p_rohan = self.engine.add_node("P_ROHAN_03", "Person", "Rohan Mukherjee", {
            "aliases": ["Kolkata Caller"],
            "gender": "Male",
            "phone": "9830155981",
            "phone_hash": self.extractor.hash_pii("9830155981"),
            "status": "Arrested",
            "state_origin": "West Bengal"
        })

        p_kavita = self.engine.add_node("P_KAVITA_04", "Person", "Kavita Sen", {
            "aliases": ["Mule Manager"],
            "gender": "Female",
            "phone": "9820011922",
            "phone_hash": self.extractor.hash_pii("9820011922"),
            "status": "Under Surveillance",
            "state_origin": "Maharashtra"
        })

        p_amit = self.engine.add_node("P_AMIT_05", "Person", "Amit Sharma", {
            "aliases": ["SIM Provider"],
            "gender": "Male",
            "phone": "9818833119",
            "phone_hash": self.extractor.hash_pii("9818833119"),
            "status": "Arrested",
            "state_origin": "Delhi"
        })

        # 2. Front Organization
        org_apex = self.engine.add_node("ORG_APEX_CYBER", "Organization", "Apex Global Cyber Tech Solutions", {
            "type": "Shell BPO / Fake Call Center",
            "registration_id": "ROC-DL-2024-8849"
        })

        # 3. Locations
        loc_nuh = self.engine.add_node("LOC_NUH", "Location", "Nuh, Mewat Hotspot", {"type": "Crime Base", "state": "Haryana"})
        loc_saltlake = self.engine.add_node("LOC_SALTLAKE", "Location", "Sector V, Salt Lake", {"type": "Call Center Base", "state": "West Bengal"})
        loc_delhi = self.engine.add_node("LOC_DELHI_SPL", "Location", "Special Cell Lodhi Colony", {"type": "Police Station", "state": "Delhi"})

        # 4. Financial Accounts
        acc_hdfc = self.engine.add_node("ACC_HDFC_9921", "FinancialAccount", "HDFC Mule Current Account", {
            "account_number": "50200088192341",
            "bank": "HDFC Bank",
            "ifsc": "HDFC0001234",
            "account_hash": self.extractor.hash_pii("50200088192341")
        })

        acc_upi = self.engine.add_node("ACC_UPI_MULE", "FinancialAccount", "farhan.mewat@okhdfcbank", {
            "type": "UPI Handle",
            "account_hash": self.extractor.hash_pii("farhan.mewat@okhdfcbank")
        })

        # 5. Vehicle
        veh_creta = self.engine.add_node("VEH_CRETA_9988", "Vehicle", "Hyundai Creta (HR 26 BC 9988)", {
            "registration_number": "HR 26 BC 9988",
            "model": "Creta SX",
            "color": "White"
        })

        # 6. Edges
        self.engine.add_edge("P_FARHAN_01", "P_AFTAB_02", "ASSOCIATE_OF", {"role": "Technical Handler", "weight": 2.5})
        self.engine.add_edge("P_FARHAN_01", "P_ROHAN_03", "ASSOCIATE_OF", {"role": "Call Center Coordinator", "weight": 2.0})
        self.engine.add_edge("P_FARHAN_01", "ORG_APEX_CYBER", "MEMBER_OF", {"role": "Beneficial Owner", "weight": 3.0})
        self.engine.add_edge("P_ROHAN_03", "ORG_APEX_CYBER", "MEMBER_OF", {"role": "Shift Lead", "weight": 1.5})
        self.engine.add_edge("P_FARHAN_01", "VEH_CRETA_9988", "OWNS_VEHICLE", {"weight": 1.0})
        self.engine.add_edge("P_KAVITA_04", "ACC_HDFC_9921", "TRANSFERRED_FUNDS", {"amount_inr": "₹45,00,000", "weight": 2.8})
        self.engine.add_edge("P_FARHAN_01", "ACC_UPI_MULE", "TRANSFERRED_FUNDS", {"amount_inr": "₹12,50,000", "weight": 2.0})
        self.engine.add_edge("P_AMIT_05", "P_FARHAN_01", "CONTACTED", {"call_count": 84, "weight": 2.2})
        self.engine.add_edge("P_FARHAN_01", "LOC_NUH", "LOCATED_AT", {"weight": 1.0})
        self.engine.add_edge("P_ROHAN_03", "LOC_SALTLAKE", "LOCATED_AT", {"weight": 1.0})

        # 7. Cross-Jurisdiction FIR Cases
        narrative_hr = (
            "Complainant reported losing ₹68 Lakhs in a stock trading app scam. "
            "Suspect identified as Mohammed Farhan @ Doctor operating from Nuh with phone 9810188234. "
            "Fraudulent funds routed to HDFC account A/c 50200088192341. Suspect seen driving vehicle HR 26 BC 9988."
        )
        case_hr = self.engine.add_node("CASE_HR_104", "Case", "FIR No. 104/2026 (Cyber Police Gurugram)", {
            "case_id": "CASE_HR_104",
            "fir_number": "104/2026",
            "station": "Cyber Police Station Gurugram",
            "jurisdiction_code": "HR-STF",
            "state": "Haryana",
            "crime_category": "Cyber Fraud & Phishing",
            "filed_date": "2026-01-14",
            "investigating_officer": "Insp. Virender Hooda",
            "narrative_text": narrative_hr
        })
        self.engine.add_edge("P_FARHAN_01", "CASE_HR_104", "ACCUSED_IN", {"role": "Mastermind", "weight": 3.0})
        self.engine.add_edge("P_AFTAB_02", "CASE_HR_104", "ACCUSED_IN", {"role": "Technical Operator", "weight": 2.0})
        self.engine.add_edge("ACC_HDFC_9921", "CASE_HR_104", "ACCUSED_IN", {"role": "Mule Account", "weight": 2.0})

        # Second cross-jurisdiction FIR in Delhi
        narrative_dl = (
            "Investigation into pan-India APK malware syndicate revealed call center in Salt Lake Kolkata. "
            "Primary accused identified as Mohammed Farhan using mobile 9810188234 and Rohan Mukherjee. "
            "Shell entity Apex Global Cyber Tech Solutions used for laundering proceeds."
        )
        case_dl = self.engine.add_node("CASE_DL_312", "Case", "FIR No. 312/2026 (Special Cell Cyber Delhi)", {
            "case_id": "CASE_DL_312",
            "fir_number": "312/2026",
            "station": "Special Cell Cyber Cell Delhi",
            "jurisdiction_code": "DL-POLICE-SPL",
            "state": "Delhi",
            "crime_category": "Cyber Fraud & Phishing",
            "filed_date": "2026-02-02",
            "investigating_officer": "Insp. Rajesh Kumar",
            "narrative_text": narrative_dl
        })
        self.engine.add_edge("P_FARHAN_01", "CASE_DL_312", "ACCUSED_IN", {"role": "Kingpin", "weight": 3.0})
        self.engine.add_edge("P_ROHAN_03", "CASE_DL_312", "ACCUSED_IN", {"role": "Accused Caller", "weight": 2.5})
        self.engine.add_edge("ORG_APEX_CYBER", "CASE_DL_312", "ACCUSED_IN", {"role": "Front Company", "weight": 2.0})

        # Third cross-jurisdiction FIR in West Bengal
        narrative_wb = (
            "Raid conducted at Sector V BPO facility. Accused Rohan Mukherjee and Kavita Sen apprehended. "
            "Coordinated with master handler Farhan Mewati. Mule account A/c 50200088192341 seized."
        )
        case_wb = self.engine.add_node("CASE_WB_88", "Case", "FIR No. 88/2026 (Salt Lake Cyber CID)", {
            "case_id": "CASE_WB_88",
            "fir_number": "88/2026",
            "station": "Salt Lake Cyber Police Station",
            "jurisdiction_code": "WB-CID",
            "state": "West Bengal",
            "crime_category": "Cyber Fraud & Phishing",
            "filed_date": "2026-02-18",
            "investigating_officer": "DySP Anirban Sen",
            "narrative_text": narrative_wb
        })
        self.engine.add_edge("P_ROHAN_03", "CASE_WB_88", "ACCUSED_IN", {"weight": 2.5})
        self.engine.add_edge("P_KAVITA_04", "CASE_WB_88", "ACCUSED_IN", {"weight": 2.0})
        self.engine.add_edge("ACC_HDFC_9921", "CASE_WB_88", "ACCUSED_IN", {"weight": 2.0})

        # Insert into SQL DB
        for c in [case_hr, case_dl, case_wb]:
            db.add(CaseRecord(
                case_id=c["case_id"],
                fir_number=c["fir_number"],
                station=c["station"],
                jurisdiction_code=c["jurisdiction_code"],
                state=c["state"],
                crime_category=c["crime_category"],
                filed_date=c["filed_date"],
                investigating_officer=c["investigating_officer"],
                narrative_text=c["narrative_text"]
            ))
        db.commit()
        return ["CASE_HR_104", "CASE_DL_312", "CASE_WB_88"]

    def _build_hawala_narco_syndicate(self, db) -> List[str]:
        """Syndicate 2: Cross-Border Hawala & Narco-Finance Network (Mumbai-Delhi-Gujarat)."""
        p_tariq = self.engine.add_node("P_TARIQ_11", "Person", "Haji Tariq Merchant", {
            "aliases": ["Bhaijaan", "Tariq Dubai"],
            "gender": "Male",
            "phone": "9820199182",
            "phone_hash": self.extractor.hash_pii("9820199182"),
            "status": "Kingpin / Red Corner Notice",
            "state_origin": "Maharashtra"
        })

        p_jayesh = self.engine.add_node("P_JAYESH_12", "Person", "Jayesh Patel", {
            "aliases": ["Kaka Angadia"],
            "gender": "Male",
            "phone": "9898011234",
            "phone_hash": self.extractor.hash_pii("9898011234"),
            "status": "Arrested",
            "state_origin": "Gujarat"
        })

        p_nisar = self.engine.add_node("P_NISAR_13", "Person", "Nisar Ahmed", {
            "aliases": ["Border Courier"],
            "gender": "Male",
            "phone": "9419188220",
            "phone_hash": self.extractor.hash_pii("9419188220"),
            "status": "Detained",
            "state_origin": "Jammu & Kashmir"
        })

        org_gold = self.engine.add_node("ORG_ALBARAKAH", "Organization", "Al-Barakah Bullion & Gems Trading", {
            "type": "Hawala Front & Gold Smuggling Channel"
        })

        acc_icici = self.engine.add_node("ACC_ICICI_7711", "FinancialAccount", "ICICI Bullion Escrow Account", {
            "account_number": "001105008812",
            "bank": "ICICI Bank",
            "ifsc": "ICIC0000011",
            "account_hash": self.extractor.hash_pii("001105008812")
        })

        self.engine.add_edge("P_TARIQ_11", "P_JAYESH_12", "ASSOCIATE_OF", {"role": "Hawala Operator", "weight": 3.0})
        self.engine.add_edge("P_TARIQ_11", "P_NISAR_13", "ASSOCIATE_OF", {"role": "Consignment Handler", "weight": 2.2})
        self.engine.add_edge("P_TARIQ_11", "ORG_ALBARAKAH", "MEMBER_OF", {"role": "Chief Financier", "weight": 3.0})
        self.engine.add_edge("P_JAYESH_12", "ACC_ICICI_7711", "TRANSFERRED_FUNDS", {"amount_inr": "₹2,10,00,000", "weight": 3.0})

        narrative_mum = (
            "Maharashtra ATS intercepted an Angadia cash courier in Zaveri Bazaar. "
            "Seized ₹3.5 Crore unaccounted cash linked to Jayesh Patel @ Kaka. "
            "Direct communication recorded with Haji Tariq Merchant on phone 9820199182. Account A/c 001105008812 identified."
        )
        case_mum = self.engine.add_node("CASE_MH_19", "Case", "FIR No. 19/2026 (ATS Police Station Mumbai)", {
            "case_id": "CASE_MH_19",
            "fir_number": "19/2026",
            "station": "ATS Police Station Mumbai",
            "jurisdiction_code": "MH-ATS",
            "state": "Maharashtra",
            "crime_category": "Hawala & Terror Financing",
            "filed_date": "2026-01-20",
            "investigating_officer": "ACP Sachin Deshmukh",
            "narrative_text": narrative_mum
        })
        self.engine.add_edge("P_TARIQ_11", "CASE_MH_19", "ACCUSED_IN", {"weight": 3.0})
        self.engine.add_edge("P_JAYESH_12", "CASE_MH_19", "ACCUSED_IN", {"weight": 2.5})
        self.engine.add_edge("ACC_ICICI_7711", "CASE_MH_19", "ACCUSED_IN", {"weight": 2.0})

        narrative_nia = (
            "National Investigation Agency (NIA) registered case under UAPA regarding narco-terror funding. "
            "Hawala kingpin Haji Tariq Merchant and cross-border associate Nisar Ahmed named. "
            "Shell firm Al-Barakah Bullion & Gems Trading used for converting proceeds into gold."
        )
        case_nia = self.engine.add_node("CASE_NIA_62", "Case", "FIR No. 62/2026 (NIA Special Cell New Delhi)", {
            "case_id": "CASE_NIA_62",
            "fir_number": "62/2026",
            "station": "NIA Special Police Station",
            "jurisdiction_code": "NIA-HQ",
            "state": "Central",
            "crime_category": "Hawala & Terror Financing",
            "filed_date": "2026-02-10",
            "investigating_officer": "SP Vikramjeet Singh",
            "narrative_text": narrative_nia
        })
        self.engine.add_edge("P_TARIQ_11", "CASE_NIA_62", "ACCUSED_IN", {"weight": 3.0})
        self.engine.add_edge("P_NISAR_13", "CASE_NIA_62", "ACCUSED_IN", {"weight": 2.5})
        self.engine.add_edge("ORG_ALBARAKAH", "CASE_NIA_62", "ACCUSED_IN", {"weight": 2.0})

        for c in [case_mum, case_nia]:
            db.add(CaseRecord(
                case_id=c["case_id"],
                fir_number=c["fir_number"],
                station=c["station"],
                jurisdiction_code=c["jurisdiction_code"],
                state=c["state"],
                crime_category=c["crime_category"],
                filed_date=c["filed_date"],
                investigating_officer=c["investigating_officer"],
                narrative_text=c["narrative_text"]
            ))
        db.commit()
        return ["CASE_MH_19", "CASE_NIA_62"]

    def _build_vehicle_theft_syndicate(self, db) -> List[str]:
        """Syndicate 3: Interstate Luxury Vehicle Theft & Chassis Tampering Gang (Delhi-UP-Haryana)."""
        p_satish = self.engine.add_node("P_SATISH_21", "Person", "Satish Gujjar", {
            "aliases": ["Pehalwan", "Satish Dadri"],
            "gender": "Male",
            "phone": "9811099281",
            "phone_hash": self.extractor.hash_pii("9811099281"),
            "status": "Kingpin / Gang Leader",
            "state_origin": "Uttar Pradesh"
        })

        p_vikas = self.engine.add_node("P_VIKAS_22", "Person", "Vikas Tyagi", {
            "aliases": ["Chassis Master", "Key Maker"],
            "gender": "Male",
            "phone": "9812033991",
            "phone_hash": self.extractor.hash_pii("9812033991"),
            "status": "Arrested",
            "state_origin": "Haryana"
        })

        p_monu = self.engine.add_node("P_MONU_23", "Person", "Monu Pehalwan", {
            "aliases": ["Shooter & Transporter"],
            "gender": "Male",
            "phone": "9873011449",
            "phone_hash": self.extractor.hash_pii("9873011449"),
            "status": "Wanted",
            "state_origin": "Delhi"
        })

        veh_fortuner = self.engine.add_node("VEH_FORT_8844", "Vehicle", "Toyota Fortuner (DL 01 AB 8844)", {
            "registration_number": "DL 01 AB 8844",
            "chassis_status": "Forged Chassis & Engine No"
        })

        veh_scorpio = self.engine.add_node("VEH_SCORP_1928", "Vehicle", "Mahindra Scorpio (HR 26 DQ 1928)", {
            "registration_number": "HR 26 DQ 1928",
            "chassis_status": "Stolen from Gurugram"
        })

        self.engine.add_edge("P_SATISH_21", "P_VIKAS_22", "ASSOCIATE_OF", {"role": "Technical Forger", "weight": 2.5})
        self.engine.add_edge("P_SATISH_21", "P_MONU_23", "ASSOCIATE_OF", {"role": "Enforcer", "weight": 2.0})
        self.engine.add_edge("P_SATISH_21", "VEH_FORT_8844", "OWNS_VEHICLE", {"weight": 1.0})
        self.engine.add_edge("P_VIKAS_22", "VEH_SCORP_1928", "VEHICLE_USED_IN", {"weight": 1.5})

        # Links to Syndicate 1 (Hidden Cross-Syndicate connection for Link Prediction!)
        # Satish Gujjar purchased burner phone from Amit Sharma (P_AMIT_05)
        self.engine.add_edge("P_SATISH_21", "P_AMIT_05", "CONTACTED", {"call_count": 12, "weight": 1.2})

        narrative_up = (
            "Noida Sector 20 police cracked an interstate luxury SUV lifting module. "
            "Gang leader identified as Satish Gujjar @ Pehalwan operating with Vikas Tyagi. "
            "Recovered Toyota Fortuner with fake number plate DL 01 AB 8844 and forged registration documents."
        )
        case_up = self.engine.add_node("CASE_UP_410", "Case", "FIR No. 410/2026 (Noida Sector 20 Police)", {
            "case_id": "CASE_UP_410",
            "fir_number": "410/2026",
            "station": "Sector 20 Police Station Noida",
            "jurisdiction_code": "UP-STF",
            "state": "Uttar Pradesh",
            "crime_category": "Interstate Vehicle Theft",
            "filed_date": "2026-02-05",
            "investigating_officer": "Insp. Manoj Tomar",
            "narrative_text": narrative_up
        })
        self.engine.add_edge("P_SATISH_21", "CASE_UP_410", "ACCUSED_IN", {"weight": 3.0})
        self.engine.add_edge("P_VIKAS_22", "CASE_UP_410", "ACCUSED_IN", {"weight": 2.0})
        self.engine.add_edge("VEH_FORT_8844", "CASE_UP_410", "ACCUSED_IN", {"weight": 2.0})

        narrative_dl2 = (
            "Delhi Police Special Cell busted armed auto-lifters syndicate. "
            "Monu Pehalwan and Satish Gujjar booked under extortion and vehicle lifting. "
            "Vehicle Mahindra Scorpio HR 26 DQ 1928 recovered with GPS jamming device."
        )
        case_dl2 = self.engine.add_node("CASE_DL_77", "Case", "FIR No. 77/2026 (Special Cell Rohini Delhi)", {
            "case_id": "CASE_DL_77",
            "fir_number": "77/2026",
            "station": "Special Cell Rohini",
            "jurisdiction_code": "DL-POLICE-SPL",
            "state": "Delhi",
            "crime_category": "Organized Crime & Extortion",
            "filed_date": "2026-02-14",
            "investigating_officer": "Insp. Surender Dahiya",
            "narrative_text": narrative_dl2
        })
        self.engine.add_edge("P_SATISH_21", "CASE_DL_77", "ACCUSED_IN", {"weight": 3.0})
        self.engine.add_edge("P_MONU_23", "CASE_DL_77", "ACCUSED_IN", {"weight": 2.5})
        self.engine.add_edge("VEH_SCORP_1928", "CASE_DL_77", "ACCUSED_IN", {"weight": 2.0})

        for c in [case_up, case_dl2]:
            db.add(CaseRecord(
                case_id=c["case_id"],
                fir_number=c["fir_number"],
                station=c["station"],
                jurisdiction_code=c["jurisdiction_code"],
                state=c["state"],
                crime_category=c["crime_category"],
                filed_date=c["filed_date"],
                investigating_officer=c["investigating_officer"],
                narrative_text=c["narrative_text"]
            ))
        db.commit()
        return ["CASE_UP_410", "CASE_DL_77"]
