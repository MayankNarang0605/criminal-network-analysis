"""
Unit Tests for NLP Entity Extraction and Crime Classification
"""

from backend.app.nlp.entity_extractor import EntityExtractor
from backend.app.nlp.crime_classifier import CrimeClassifier

def test_phone_and_vehicle_extraction():
    extractor = EntityExtractor()
    sample_text = (
        "Accused Vikram Singh @ Vicky was apprehended near Sector 62 Noida. "
        "He was driving a stolen vehicle DL 01 AB 1234 and carrying mobile phone +91 98765 43210. "
        "Payments were received in HDFC account A/c 502000881923 and UPI vicky@okhdfcbank."
    )

    result = extractor.extract(sample_text)

    # Verify extracted entities
    assert len(result["phones"]) >= 1
    assert result["phones"][0]["normalized"] == "9876543210"

    assert len(result["vehicles"]) >= 1
    assert "DL 01 AB 1234" in result["vehicles"][0]["registration_number"]

    assert len(result["financial_accounts"]) >= 1
    assert any("502000881923" in acc.get("account_number", "") for acc in result["financial_accounts"])
    assert any("vicky@okhdfcbank" in acc.get("upi_id", "") for acc in result["financial_accounts"])

    assert len(result["persons"]) >= 1
    assert "Vikram Singh" in result["persons"][0]["name"]
    assert "Vicky" in result["persons"][0]["aliases"]

    print("✓ Phone, Vehicle, Financial, and Person extraction test passed!")

def test_crime_classification():
    classifier = CrimeClassifier()
    cyber_text = "Victim was lured through a fake stock investment WhatsApp group and APK link. Lost 45 lakhs via UPI and RTGS to mule bank accounts in Mewat."
    res = classifier.classify(cyber_text)

    assert res["predicted_category"] == "Cyber Fraud & Phishing"
    assert res["confidence_percentage"] > 50.0

    hawala_text = "Seized ₹2.5 crore unaccounted cash from Angadia courier linked to Hawala channel in Zaveri Bazaar with overseas gold smuggling."
    res2 = classifier.classify(hawala_text)
    assert res2["predicted_category"] == "Hawala & Terror Financing"

    print("✓ Crime category classification test passed!")

if __name__ == "__main__":
    test_phone_and_vehicle_extraction()
    test_crime_classification()
