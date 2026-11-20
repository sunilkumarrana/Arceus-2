"""
API Routes for Citizen Profile Manual Evaluation, Dashboard Analytics, and Saved Schemes.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import User, CitizenProfile, SavedScheme, GovernmentScheme
from engine.models import CallerProfile, SchemeEligibility
from engine.rules_engine import SchemeRulesEngine

router = APIRouter(prefix="/api/eligibility", tags=["Eligibility"])
rules_engine = SchemeRulesEngine()


class ManualProfileEvaluationRequest(BaseModel):
    user_id: Optional[int] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    annual_income: Optional[float] = None
    state: Optional[str] = "All-India"
    district: Optional[str] = None
    caste_category: Optional[str] = None
    is_disabled: Optional[bool] = False
    area_type: Optional[str] = None
    house_type: Optional[str] = None
    has_land: Optional[bool] = None
    land_ha: Optional[float] = None
    bpl_status: Optional[bool] = None
    is_tax_payer: Optional[bool] = None
    is_govt_employee: Optional[bool] = None
    has_existing_lpg: Optional[bool] = None
    has_girl_child_under_10: Optional[bool] = None
    is_pregnant_or_lactating: Optional[bool] = None


class SaveSchemeRequest(BaseModel):
    user_id: int
    scheme_id: str
    notes: Optional[str] = ""
    status: Optional[str] = "interested"


@router.post("/evaluate")
def evaluate_profile(req: ManualProfileEvaluationRequest, db: Session = Depends(get_db)):
    """Directly evaluates a manual citizen profile form against all scheme rules."""
    profile = CallerProfile(
        age=req.age,
        gender=req.gender,
        occupation=req.occupation,
        annual_income=req.annual_income,
        state=req.state,
        district=req.district,
        area_type=req.area_type,
        house_type=req.house_type,
        has_land=req.has_land,
        land_ha=req.land_ha,
        bpl_status=req.bpl_status,
        is_tax_payer=req.is_tax_payer,
        is_govt_employee=req.is_govt_employee,
        has_existing_lpg=req.has_existing_lpg,
        has_girl_child_under_10=req.has_girl_child_under_10,
        is_pregnant_or_lactating=req.is_pregnant_or_lactating
    )

    evaluations = rules_engine.evaluate_all(profile)

    eligible = [e for e in evaluations if e.status == "ELIGIBLE"]
    likely = [e for e in evaluations if e.status == "LIKELY_ELIGIBLE"]
    ineligible = [e for e in evaluations if e.status == "NOT_ELIGIBLE"]
    unknown = [e for e in evaluations if e.status == "UNKNOWN"]

    # If user_id provided, save/update profile in DB
    if req.user_id:
        existing_profile = db.query(CitizenProfile).filter(CitizenProfile.user_id == req.user_id).first()
        if existing_profile:
            for k, v in req.model_dump().items():
                if v is not None and hasattr(existing_profile, k):
                    setattr(existing_profile, k, v)
        else:
            new_profile = CitizenProfile(**req.model_dump())
            db.add(new_profile)
        db.commit()

    return {
        "summary": {
            "total_evaluated": len(evaluations),
            "eligible_count": len(eligible),
            "likely_count": len(likely),
            "ineligible_count": len(ineligible),
            "unknown_count": len(unknown)
        },
        "profile": profile,
        "evaluations": evaluations
    }


@router.get("/dashboard")
def get_dashboard(user_id: Optional[int] = 1, db: Session = Depends(get_db)):
    """Retrieves personalized citizen dashboard statistics, recommended, and saved schemes."""
    # Find profile if exists
    profile_record = db.query(CitizenProfile).filter(CitizenProfile.user_id == user_id).first() if user_id else None

    if profile_record:
        caller_profile = CallerProfile(
            age=profile_record.age,
            gender=profile_record.gender,
            occupation=profile_record.occupation,
            annual_income=profile_record.annual_income,
            area_type=profile_record.area_type,
            house_type=profile_record.house_type,
            has_land=profile_record.has_land,
            land_ha=profile_record.land_ha,
            bpl_status=profile_record.bpl_status,
            is_tax_payer=profile_record.is_tax_payer,
            is_govt_employee=profile_record.is_govt_employee
        )
    else:
        # Default active profile sample for immediate demo
        caller_profile = CallerProfile(
            age=45,
            gender="male",
            occupation="farmer",
            annual_income=80000.0,
            has_land=True,
            land_ha=1.0,
            bpl_status=True,
            area_type="rural",
            house_type="kutcha",
            is_tax_payer=False,
            is_govt_employee=False
        )

    evaluations = rules_engine.evaluate_all(caller_profile)
    eligible = [e for e in evaluations if e.status == "ELIGIBLE"]
    likely = [e for e in evaluations if e.status == "LIKELY_ELIGIBLE"]
    ineligible = [e for e in evaluations if e.status == "NOT_ELIGIBLE"]

    # Saved schemes for user
    saved_items = []
    if user_id:
        saved_records = db.query(SavedScheme).filter(SavedScheme.user_id == user_id).all()
        for sr in saved_records:
            s_obj = next((s for s in rules_engine.schemes_data if s["id"] == sr.scheme_id), None)
            if s_obj:
                saved_items.append({
                    "scheme_id": sr.scheme_id,
                    "name_en": s_obj["name_en"],
                    "name_hi": s_obj["name_hi"],
                    "category": s_obj.get("category", ""),
                    "benefits_en": s_obj.get("benefits_en", ""),
                    "status": sr.status,
                    "saved_at": sr.created_at.strftime("%Y-%m-%d")
                })

    return {
        "stats": {
            "total_evaluated": len(evaluations),
            "eligible_count": len(eligible),
            "likely_count": len(likely),
            "ineligible_count": len(ineligible),
            "saved_count": len(saved_items)
        },
        "active_profile": caller_profile,
        "eligible_schemes": eligible,
        "likely_schemes": likely,
        "ineligible_schemes": ineligible,
        "saved_schemes": saved_items
    }


@router.post("/save")
def save_scheme(req: SaveSchemeRequest, db: Session = Depends(get_db)):
    """Saves or bookmarks a scheme for a citizen."""
    existing = db.query(SavedScheme).filter(
        SavedScheme.user_id == req.user_id,
        SavedScheme.scheme_id == req.scheme_id
    ).first()

    if existing:
        existing.status = req.status
        existing.notes = req.notes
    else:
        new_save = SavedScheme(
            user_id=req.user_id,
            scheme_id=req.scheme_id,
            notes=req.notes,
            status=req.status
        )
        db.add(new_save)
    db.commit()
    return {"status": "success", "message": "Scheme saved to your citizen dashboard"}
