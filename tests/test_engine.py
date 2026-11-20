"""
Unit and integration tests for SuvidhaVani Scheme Agent.
Verifies multi-slot extraction, rules reasoning, vague disambiguation, and contradiction handling.
"""
import pytest
from engine.models import CallerProfile
from engine.nlu_extractor import NLUSlotExtractor
from engine.rules_engine import SchemeRulesEngine
from engine.vague_detector import VagueDetector
from engine.contradiction_detector import ContradictionDetector
from engine.agent_orchestrator import SchemeVoiceAgent


def test_nlu_multi_slot_extraction():
    extractor = NLUSlotExtractor()
    utterance = "नमस्ते, मैं रमेश हूँ, मेरी उम्र 45 साल है, गाँव में 1 हेक्टेयर ज़मीन पर खेती करता हूँ और मेरी सालाना कमाई 80000 रुपये है।"
    slots = extractor.extract_slots(utterance)

    assert slots.get("age") == 45
    assert slots.get("occupation") == "farmer"
    assert slots.get("has_land") is True
    assert slots.get("land_ha") == 1.0
    assert slots.get("annual_income") == 80000.0
    assert slots.get("area_type") == "rural"


def test_rules_engine_pmkisan_and_pmjay():
    engine = SchemeRulesEngine()
    profile = CallerProfile(
        age=45,
        gender="male",
        occupation="farmer",
        has_land=True,
        land_ha=1.0,
        annual_income=80000.0,
        bpl_status=True,
        area_type="rural",
        house_type="kutcha",
        is_tax_payer=False,
        is_govt_employee=False
    )
    evals = engine.evaluate_all(profile)

    eval_map = {e.scheme_id: e for e in evals}

    # PM-KISAN should be ELIGIBLE
    assert "pm_kisan" in eval_map
    assert eval_map["pm_kisan"].status == "ELIGIBLE"

    # Ayushman Bharat (PM-JAY) should be ELIGIBLE
    assert "pmjay" in eval_map
    assert eval_map["pmjay"].status == "ELIGIBLE"

    # PMAY-G should be ELIGIBLE (rural + kutcha house + low income)
    assert "pmay_g" in eval_map
    assert eval_map["pmay_g"].status == "ELIGIBLE"

    # PM-SVANidhi should be NOT_ELIGIBLE (since occupation is farmer, not street vendor)
    assert "pm_svanidhi" in eval_map
    assert eval_map["pm_svanidhi"].status == "NOT_ELIGIBLE"


def test_vague_income_detection():
    detector = VagueDetector()
    profile = CallerProfile(age=40, occupation="farmer")
    
    notice = detector.detect_vagueness("kuch khas nahi thoda bahut kama lete hain bas gujara hota hai", profile, "annual_income")
    assert notice is not None
    assert notice.slot == "annual_income"
    assert len(notice.clarification_options_en) == 3


def test_contradiction_age_vs_pension():
    detector = ContradictionDetector()
    profile = CallerProfile(age=24)
    alert = detector.detect_contradiction({}, profile, "Mujhe old age pension chahiye, main retired hu")
    assert alert is not None
    assert alert.slot == "age_vs_pension"
    assert "60" in alert.message_en


def test_contradiction_high_income_vs_bpl():
    detector = ContradictionDetector()
    profile = CallerProfile(bpl_status=True)
    alert = detector.detect_contradiction({"annual_income": 800000.0}, profile, "Meri saal ki kamai 8 lakh rupaye hai")
    assert alert is not None
    assert alert.slot == "income_vs_bpl"


def test_agent_orchestrator_turn_flow():
    agent = SchemeVoiceAgent()
    agent.reset(initial_language="hi")

    # Turn 1: Farmer introduces with multi-slot info
    r1 = agent.process_utterance("नमस्ते, मैं 45 वर्ष का किसान हूँ और गाँव में 1 हेक्टेयर ज़मीन पर खेती करता हूँ।")
    assert r1.slots_extracted_this_turn.get("age") == 45
    assert r1.slots_extracted_this_turn.get("occupation") == "farmer"
    assert r1.slots_extracted_this_turn.get("has_land") is True

    # Turn 2: Provides income
    r2 = agent.process_utterance("मेरी सालाना आय 80 हजार है और बीपीएल राशन कार्ड है, कोई टैक्स नहीं भरता।")
    assert r2.slots_extracted_this_turn.get("annual_income") == 80000.0
    assert r2.slots_extracted_this_turn.get("bpl_status") is True

    # After just 2 turns, decision should be reached or eligible schemes found!
    assert r2.eligible_schemes_count >= 1
    eligible_ids = [s.scheme_id for s in r2.schemes_evaluation if s.status == "ELIGIBLE"]
    assert "pm_kisan" in eligible_ids
