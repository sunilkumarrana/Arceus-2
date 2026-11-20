"""
Entropy-Driven Optimal Question Selection Engine.
Minimizes the number of questions asked by maximizing Information Gain across candidate schemes.
"""
from typing import List, Optional, Tuple, Dict
from engine.models import CallerProfile, SchemeEligibility


class EntropyQuestioner:
    def __init__(self):
        # Slot priority weighting and conversational question templates
        self.question_templates = {
            "occupation": {
                "en": "To match you with the right government schemes, what is your primary occupation or livelihood?",
                "hi": "आपके लिए सही सरकारी योजना ढूंढने के लिए, आप मुख्य रूप से क्या काम या व्यवसाय करते हैं?"
            },
            "annual_income": {
                "en": "Roughly, what is your total annual household income, or do you hold a BPL ration card?",
                "hi": "लगभग आपके पूरे परिवार की सालाना कमाई कितनी है, या क्या आपके पास बीपीएल राशन कार्ड है?"
            },
            "age": {
                "en": "Could you please tell me your age?",
                "hi": "क्या आप कृपया अपनी आयु (उम्र) बता सकते हैं?"
            },
            "has_land": {
                "en": "Do you own cultivable agricultural land, and roughly how many acres or hectares?",
                "hi": "क्या आपके पास खेती योग्य ज़मीन है, और लगभग कितनी (एकड़ या हेक्टेयर)?"
            },
            "area_type": {
                "en": "Do you reside in a rural village area or an urban city?",
                "hi": "क्या आप किसी ग्रामीण गाँव में रहते हैं या शहरी क्षेत्र में?"
            },
            "house_type": {
                "en": "What type of house do you live in: a kutcha (mud/thatched) house, or a permanent pucca house?",
                "hi": "आप किस प्रकार के मकान में रहते हैं: कच्चा मकान या पक्का मकान?"
            },
            "gender": {
                "en": "Could you please confirm your gender (male or female)?",
                "hi": "क्या आप कृपया स्पष्ट कर सकते हैं कि आप पुरुष हैं या महिला?"
            },
            "is_tax_payer": {
                "en": "Do you or any member of your immediate family file income tax?",
                "hi": "क्या आप या आपके परिवार का कोई सदस्य आयकर (इनकम टैक्स) भरते हैं?"
            },
            "has_existing_lpg": {
                "en": "Does your household already have an LPG gas cylinder connection?",
                "hi": "क्या आपके घर में पहले से एलपीजी गैस कनेक्शन मौजूद है?"
            },
            "has_girl_child_under_10": {
                "en": "Do you have a daughter under 10 years of age in your family?",
                "hi": "क्या आपके परिवार में 10 वर्ष से कम आयु की कोई बेटी है?"
            }
        }

    def select_next_question(
        self,
        profile: CallerProfile,
        evaluations: List[SchemeEligibility],
        questions_asked_so_far: int
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Calculates information gain for all unknown slots across active candidate schemes.
        Returns: (slot_name, question_en, question_hi) or (None, None, None) if decision reached.
        """
        # Count current status
        eligible_schemes = [s for s in evaluations if s.status == "ELIGIBLE"]
        likely_schemes = [s for s in evaluations if s.status == "LIKELY_ELIGIBLE"]
        unknown_schemes = [s for s in evaluations if s.status == "UNKNOWN"]

        # MINIMIZING QUESTIONS THRESHOLD:
        # If we have confirmed eligible schemes and questions count >= 2, or no more active candidates
        if len(eligible_schemes) >= 2 and len(likely_schemes) == 0:
            return None, None, None

        if len(eligible_schemes) >= 1 and questions_asked_so_far >= 3 and len(likely_schemes) <= 1:
            return None, None, None

        # Gather all active candidates that could become eligible
        active_candidates = likely_schemes + unknown_schemes
        if not active_candidates:
            return None, None, None

        # Compute frequency of missing criteria
        slot_frequency: Dict[str, float] = {}

        for scheme in active_candidates:
            # Schemes that are closer to being eligible get higher weight
            weight = 2.0 if scheme.status == "LIKELY_ELIGIBLE" else 1.0
            for crit in scheme.missing_criteria:
                slot_frequency[crit] = slot_frequency.get(crit, 0.0) + weight

        # Filter out slots that are already known in profile
        filtered_slots = {}
        for slot, score in slot_frequency.items():
            if getattr(profile, slot, None) is None:
                filtered_slots[slot] = score

        if not filtered_slots:
            return None, None, None

        # Pick the slot with highest information gain score
        best_slot = max(filtered_slots.items(), key=lambda x: x[1])[0]

        template = self.question_templates.get(best_slot, {
            "en": f"Could you provide more details regarding your {best_slot}?",
            "hi": f"क्या आप अपने {best_slot} के बारे में कुछ और जानकारी दे सकते हैं?"
        })

        return best_slot, template["en"], template["hi"]
