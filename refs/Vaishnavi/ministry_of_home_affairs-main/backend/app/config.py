"""
AI-Powered Criminal Network Analysis System
Configuration and System Constants
Themed on Ministry of Home Affairs (MHA) Specifications
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)

# Database & Storage
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'criminal_network.db'}")
GRAPH_DATA_PATH = DATA_DIR / "graph_store.json"

# Security & Authentication
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "MHA-CRIMINAL-NETWORK-SECURE-KEY-2026-X99QZ")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Role-Based Access Control (RBAC)
ROLES = {
    "ADMIN": "Admin",                           # Full system configuration & management
    "INVESTIGATOR": "Investigating Officer",    # Case intake, suspect profiling, search
    "ANALYST": "Intelligence Analyst",          # Network metrics, community & link analysis
    "AUDITOR": "Auditor"                        # Read-only audit trail verification
}

# Role Permissions Mapping
PERMISSIONS = {
    "Admin": ["read", "write", "delete", "admin", "export", "merge_entities"],
    "Investigating Officer": ["read", "write", "export", "merge_entities"],
    "Intelligence Analyst": ["read", "analytics", "export"],
    "Auditor": ["read_audit", "verify_integrity"]
}

# Indian Law Enforcement Crime Categories (IPC / Bharatiya Nyaya Sanhita - BNS)
CRIME_CATEGORIES = [
    "Cyber Fraud & Phishing",
    "Organized Crime & Extortion",
    "Hawala & Terror Financing",
    "Interstate Vehicle Theft",
    "Narcotics & Drug Trafficking",
    "Arms Smuggling & Illegal Weapons",
    "Fake Indian Currency Notes (FICN)",
    "Human Trafficking & Fake Passports"
]

# Major Law Enforcement Jurisdictions & Specialized Wings (MHA / State Police)
JURISDICTIONS = [
    {"code": "NIA-HQ", "name": "National Investigation Agency (NIA)", "state": "Central"},
    {"code": "I4C-CYBER", "name": "Indian Cybercrime Coordination Centre (I4C)", "state": "Central"},
    {"code": "NCRB-HQ", "name": "National Crime Records Bureau (NCRB)", "state": "Central"},
    {"code": "DL-POLICE-SPL", "name": "Delhi Police Special Cell", "state": "Delhi"},
    {"code": "MH-ATS", "name": "Maharashtra Anti-Terrorism Squad (ATS)", "state": "Maharashtra"},
    {"code": "HR-STF", "name": "Haryana Special Task Force (STF - Gurugram/Nuh)", "state": "Haryana"},
    {"code": "WB-CID", "name": "West Bengal CID Cyber Cell (Kolkata)", "state": "West Bengal"},
    {"code": "KA-CCB", "name": "Karnataka Central Crime Branch (Bengaluru)", "state": "Karnataka"},
    {"code": "JH-CYBER", "name": "Jharkhand Cyber Police (Jamtara Desk)", "state": "Jharkhand"},
    {"code": "UP-STF", "name": "Uttar Pradesh STF (Noida/Lucknow)", "state": "Uttar Pradesh"}
]

# Entity Types for Property Graph
NODE_TYPES = [
    "Person",
    "Case",
    "Organization",
    "Location",
    "CommunicationRecord",
    "FinancialAccount",
    "Vehicle"
]

# Relationship Edge Types
EDGE_TYPES = [
    "ASSOCIATE_OF",
    "ACCUSED_IN",
    "MEMBER_OF",
    "CONTACTED",
    "TRANSFERRED_FUNDS",
    "LOCATED_AT",
    "OWNS_VEHICLE",
    "VEHICLE_USED_IN",
    "FILED_AT"
]
