"""
Data models for the Voice-First Scheme Agent (SuvidhaVani).
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class CallerProfile(BaseModel):
    """Structured representation of caller attributes extracted from voice conversation."""
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None  # 'male', 'female', 'other'
    occupation: Optional[str] = None  # 'farmer', 'street_vendor', 'artisan', 'manual_worker', 'unemployed', etc.
    annual_income: Optional[float] = None  # in INR
    monthly_income: Optional[float] = None
    bpl_status: Optional[bool] = None  # True if BPL / Antyodaya / poor
    has_land: Optional[bool] = None
    land_ha: Optional[float] = None  # in hectares
    area_type: Optional[str] = None  # 'rural', 'urban'
    house_type: Optional[str] = None  # 'kutcha', 'pucca', 'homeless'
    state: Optional[str] = None
    is_tax_payer: Optional[bool] = None
    is_govt_employee: Optional[bool] = None
    has_existing_lpg: Optional[bool] = None
    has_girl_child_under_10: Optional[bool] = None
    is_pregnant_or_lactating: Optional[bool] = None
    has_existing_pension: Optional[bool] = None
    
    # Tracking metadata
    extracted_slots_history: Dict[str, Any] = Field(default_factory=dict)
    clarified_slots: List[str] = Field(default_factory=list)


class RuleItemCheck(BaseModel):
    criterion: str
    criterion_label_en: str
    criterion_label_hi: str
    required_value: Any
    actual_value: Any
    status: str  # 'PASSED', 'FAILED', 'UNKNOWN'
    explanation_en: str
    explanation_hi: str


class SchemeEligibility(BaseModel):
    scheme_id: str
    name_en: str
    name_hi: str
    category: str
    status: str  # 'ELIGIBLE', 'LIKELY_ELIGIBLE', 'NOT_ELIGIBLE', 'UNKNOWN'
    match_score: float  # 0.0 to 1.0
    benefits_en: str
    benefits_hi: str
    criteria_breakdown: List[RuleItemCheck]
    missing_criteria: List[str]
    disqualifiers: List[str]
    required_documents_en: List[str]
    required_documents_hi: List[str]
    application_steps_en: str
    application_steps_hi: str
    portal_url: str


class ContradictionAlert(BaseModel):
    slot: str
    previous_value: Any
    new_value: Any
    message_en: str
    message_hi: str
    severity: str = "HIGH"  # 'HIGH', 'MEDIUM'


class DisambiguationNotice(BaseModel):
    slot: str
    raw_utterance: str
    detected_ambiguity: str
    clarification_options_en: List[str]
    clarification_options_hi: List[str]


class AgentTurnResponse(BaseModel):
    agent_message_en: str
    agent_message_hi: str
    current_language: str  # 'en' or 'hi'
    spoken_text: str  # text formatted for TTS in selected language
    state: str  # 'GREETING', 'INQUIRING', 'DISAMBIGUATING', 'RECONCILING', 'RECOMMENDING', 'EXPLAINING'
    questions_asked_count: int
    slots_extracted_this_turn: Dict[str, Any]
    caller_profile: CallerProfile
    schemes_evaluation: List[SchemeEligibility]
    eligible_schemes_count: int
    likely_schemes_count: int
    contradiction: Optional[ContradictionAlert] = None
    disambiguation: Optional[DisambiguationNotice] = None
    decision_reached: bool = False
    next_recommended_question_en: Optional[str] = None
    next_recommended_question_hi: Optional[str] = None
