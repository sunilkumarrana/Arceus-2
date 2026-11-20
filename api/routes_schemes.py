"""
API Routes for Schemes Catalog, Details, Comparison, and Document Checklists.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import GovernmentScheme
from engine.rules_engine import SchemeRulesEngine
from engine.scheme_comparator import SchemeComparator
from engine.document_checklist import DocumentChecklistGenerator

router = APIRouter(prefix="/api/schemes", tags=["Schemes"])

rules_engine = SchemeRulesEngine()
comparator = SchemeComparator(rules_engine)
checklist_gen = DocumentChecklistGenerator(rules_engine)


class CompareRequest(BaseModel):
    scheme_ids: List[str]


class ChecklistRequest(BaseModel):
    scheme_ids: List[str]


@router.get("")
def list_schemes(
    category: Optional[str] = None,
    level: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lists all verified government welfare schemes with filtering and search."""
    schemes = rules_engine.schemes_data

    if category and category.lower() != "all":
        schemes = [s for s in schemes if s.get("category", "").lower() == category.lower()]

    if level and level.lower() != "all":
        schemes = [s for s in schemes if s.get("level", "").lower() == level.lower()]

    if search:
        q = search.lower().strip()
        schemes = [
            s for s in schemes if (
                q in s.get("name_en", "").lower() or
                q in s.get("name_hi", "").lower() or
                q in s.get("brief_en", "").lower() or
                q in s.get("brief_hi", "").lower() or
                q in s.get("category", "").lower()
            )
        ]

    return {
        "total": len(schemes),
        "schemes": schemes
    }


@router.get("/{scheme_id}")
def get_scheme(scheme_id: str):
    """Retrieves full verified details of a single government scheme."""
    scheme = next((s for s in rules_engine.schemes_data if s["id"] == scheme_id), None)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return scheme


@router.post("/compare")
def compare_schemes(req: CompareRequest):
    """Compares 2 to 3 selected schemes across standardized criteria and benefits."""
    if len(req.scheme_ids) < 2:
        raise HTTPException(status_code=400, detail="Please select at least 2 schemes to compare.")
    if len(req.scheme_ids) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 schemes can be compared simultaneously.")
    return comparator.compare_schemes(req.scheme_ids)


@router.post("/checklist")
def generate_checklist(req: ChecklistRequest):
    """Generates a personalized, consolidated document checklist for selected schemes."""
    if not req.scheme_ids:
        raise HTTPException(status_code=400, detail="Scheme IDs list cannot be empty.")
    return checklist_gen.generate_checklist(req.scheme_ids)
