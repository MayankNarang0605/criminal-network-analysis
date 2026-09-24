"""
Evidence Integrity & Cryptographic Ledger Router (Phase 18).
Implements Section 65B Indian Evidence Act compliance:
- Immutable SHA-256 hash chains
- Merkle root integrity verification
- Tamper detection
"""
import hashlib
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.postgres import get_db
from backend.models.evidence import EvidenceMetadata, EvidenceHashChain

router = APIRouter(prefix="/api/evidence", tags=["Evidence"])


class EvidenceItemResponse(BaseModel):
    evidence_id: str
    case_id: str
    source_table: Optional[str] = None
    record_id: Optional[str] = None
    evidence_type: Optional[str] = None
    collected_date: Optional[str] = None
    custodian: Optional[str] = None
    content_sha256: Optional[str] = None
    block_hash: Optional[str] = None
    sequence_index: Optional[int] = None

    class Config:
        from_attributes = True


class ChainVerificationResult(BaseModel):
    case_id: str
    total_records: int
    chain_valid: bool
    tampered_records: List[Dict[str, Any]]
    head_block_hash: Optional[str]
    root_hash: Optional[str]


@router.get("", response_model=List[EvidenceItemResponse])
def list_evidence(
    case_id: Optional[str] = Query(None, description="Filter evidence by case ID"),
    evidence_type: Optional[str] = Query(None, description="Filter by evidence category"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve chain of custody evidence records with cryptographic hashes."""
    query = db.query(EvidenceMetadata)
    if case_id:
        query = query.filter(EvidenceMetadata.case_id == case_id)
    if evidence_type:
        query = query.filter(EvidenceMetadata.evidence_type == evidence_type)

    items = query.order_by(EvidenceMetadata.evidence_id.asc()).offset(offset).limit(limit).all()

    # Join hash-chain info
    res = []
    for item in items:
        hc = db.query(EvidenceHashChain).filter(EvidenceHashChain.evidence_id == item.evidence_id).first()
        res.append(EvidenceItemResponse(
            evidence_id=item.evidence_id,
            case_id=item.case_id,
            source_table=item.source_table,
            record_id=item.record_id,
            evidence_type=item.evidence_type,
            collected_date=item.collected_date,
            custodian=item.custodian,
            content_sha256=hc.content_sha256 if hc else None,
            block_hash=hc.block_hash if hc else None,
            sequence_index=hc.sequence_index if hc else None,
        ))
    return res


@router.get("/verify/{case_id}", response_model=ChainVerificationResult)
def verify_case_hash_chain(case_id: str, db: Session = Depends(get_db)):
    """
    Verify mathematical integrity of the SHA-256 evidence hash chain for a specific case.
    Re-computes previous_hash links and identifies any tampering.
    """
    blocks = (
        db.query(EvidenceHashChain)
        .filter(EvidenceHashChain.case_id == case_id)
        .order_by(EvidenceHashChain.sequence_index.asc())
        .all()
    )

    if not blocks:
        return ChainVerificationResult(
            case_id=case_id,
            total_records=0,
            chain_valid=True,
            tampered_records=[],
            head_block_hash=None,
            root_hash=None,
        )

    tampered = []
    prev_hash = "0" * 64

    for b in blocks:
        # Verify link continuity
        if b.previous_hash != prev_hash and b.sequence_index != 1:
            tampered.append({
                "sequence_index": b.sequence_index,
                "evidence_id": b.evidence_id,
                "reason": "Previous hash pointer mismatch",
                "expected": prev_hash,
                "found": b.previous_hash,
            })
        
        # Verify block hash computation
        computed_block = hashlib.sha256((b.previous_hash + b.content_sha256).encode("utf-8")).hexdigest()
        if b.block_hash and b.block_hash != computed_block:
            tampered.append({
                "sequence_index": b.sequence_index,
                "evidence_id": b.evidence_id,
                "reason": "Block hash payload corrupted",
                "expected": computed_block,
                "found": b.block_hash,
            })

        prev_hash = b.block_hash or computed_block

    is_valid = len(tampered) == 0
    head_hash = blocks[-1].block_hash if blocks else None

    # Merkle tree root over leaf block_hash per case contract
    level = [b.block_hash for b in blocks if b.block_hash]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i+1] if i+1 < len(level) else level[i]
            nxt.append(hashlib.sha256((a + b).encode("utf-8")).hexdigest())
        level = nxt
    merkle_root = level[0] if level else None

    return ChainVerificationResult(
        case_id=case_id,
        total_records=len(blocks),
        chain_valid=is_valid,
        tampered_records=tampered,
        head_block_hash=head_hash,
        root_hash=merkle_root,
    )
