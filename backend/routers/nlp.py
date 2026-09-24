"""
NLP / OCR Router (Phase 5).
Provides NER extraction, crime classification on FIR documents.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.postgres import get_db
from backend.services.nlp_service import (
    process_case_documents,
    extract_entities_from_text,
    classify_crime,
    get_available_cases_with_documents,
)
from backend.logging_config import logger

router = APIRouter(prefix="/api/nlp", tags=["NLP"])


@router.get("/cases")
def list_cases_with_documents():
    """List all case IDs that have document directories available for NLP processing."""
    cases = get_available_cases_with_documents()
    return {"total": len(cases), "cases": cases}


@router.get("/extract/{case_id}")
def extract_case_nlp(case_id: str):
    """
    Run NER extraction and crime classification on all documents for a case.
    Uses spaCy if installed, otherwise regex fallback for Indian-context entities.
    """
    case_id_upper = case_id.upper()
    result = process_case_documents(case_id_upper)
    if result["documents_found"] == 0:
        return {
            "case_id": case_id_upper,
            "documents_found": 0,
            "message": "No documents found for this case. Check dataset/evidence/documents/ directory.",
            "results": [],
            "entity_summary": {},
        }
    return result


@router.post("/classify")
def classify_text(body: dict):
    """
    Classify a crime type from free-text using TF-IDF + Logistic Regression.
    Falls back to keyword matching if scikit-learn is unavailable.
    """
    text = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="'text' field is required")
    return classify_crime(text)


@router.post("/ner")
def extract_entities(body: dict):
    """
    Extract named entities from arbitrary text.
    Returns persons, phones, vehicles, dates, monetary amounts, and legal sections.
    """
    text = body.get("text", "")
    doc_id = body.get("doc_id", "adhoc")
    case_id = body.get("case_id", "")
    if not text:
        raise HTTPException(status_code=400, detail="'text' field is required")
    return extract_entities_from_text(text, doc_id=doc_id, case_id=case_id)
