"""
Master Test Runner for AI-Powered Criminal Network Analysis System
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.tests.test_nlp_extraction import test_phone_and_vehicle_extraction, test_crime_classification
from backend.tests.test_graph_analytics import test_graph_algorithms
from backend.tests.test_audit_integrity import test_audit_hash_chain

def run_all_tests():
    print("================================================================")
    print("RUNNING CRIMINAL NETWORK ANALYSIS SYSTEM TEST SUITE")
    print("================================================================")
    
    print("\n[1/3] Testing NLP Entity Extraction & Crime Classification...")
    test_phone_and_vehicle_extraction()
    test_crime_classification()

    print("\n[2/3] Testing Graph Analytics, Centrality & Link Prediction...")
    test_graph_algorithms()

    print("\n[3/3] Testing Tamper-Evident SHA-256 Audit Trail Integrity...")
    test_audit_hash_chain()

    print("\n================================================================")
    print("✓ ALL TESTS PASSED SUCCESSFULLY! BACKEND INTEGRITY CONFIRMED.")
    print("================================================================")

if __name__ == "__main__":
    run_all_tests()
