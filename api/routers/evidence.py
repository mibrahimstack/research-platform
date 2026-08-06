"""Evidence APIs exposing exact claim-to-source provenance."""

from fastapi import APIRouter, HTTPException, Query

from api.schemas import ClaimEvidence
from db.evidence import get_document_claims

router = APIRouter(prefix="/api/v1/evidence", tags=["Evidence & Provenance"])


@router.get("/documents/{document_id}/claims", response_model=list[ClaimEvidence])
def document_claims(document_id: str, limit: int = Query(default=100, ge=1, le=500)):
    """Return claims plus the exact quote and character offsets that support each one."""
    try:
        return [ClaimEvidence(**claim) for claim in get_document_claims(document_id, limit)]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve evidence: {exc}")
