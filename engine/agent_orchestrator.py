"""
Conversation Orchestrator and Dialogue State Machine.
Coordinates NLU, Contradiction Detection, Vague Disambiguation, Rules Reasoning, and Voice Response generation.
"""
import re
from typing import Dict, Any, Optional, List
from engine.models import CallerProfile, AgentTurnResponse, SchemeEligibility, ContradictionAlert, DisambiguationNotice
from engine.nlu_extractor import NLUSlotExtractor
from engine.rules_engine import SchemeRulesEngine
from engine.vague_detector import VagueDetector
from engine.contradiction_detector import ContradictionDetector
from engine.entropy_questioner import EntropyQuestioner


class SchemeVoiceAgent:
    def __init__(self, schemes_file: str = None):
        self.rules_engine = SchemeRulesEngine(schemes_file)
        self.nlu = NLUSlotExtractor()
        self.vague_detector = VagueDetector()
        self.contradiction_detector = ContradictionDetector()
        self.questioner = EntropyQuestioner()

        # Session state
        self.profile = CallerProfile()
        self.history: List[Dict[str, str]] = []
        self.questions_asked_count: int = 0
        self.last_asked_slot: Optional[str] = None
        self.language: str = "hi"  # default to Hindi / bilingual
        self.state: str = "GREETING"
        self.active_contradiction: Optional[ContradictionAlert] = None

    def reset(self, initial_language: str = "hi"):
        """Resets agent conversation for a new caller."""
        self.profile = CallerProfile()
        self.history = []
        self.questions_asked_count = 0
        self.last_asked_slot = None
        self.language = initial_language
        self.state = "GREETING"
        self.active_contradiction = None

    def detect_language(self, text: str) -> str:
        """Detects whether user is speaking in Hindi (Devanagari/transliterated) or English."""
        # Devanagari Unicode range
        if re.search(r'[\u0900-\u097F]', text):
            return "hi"
        # Common Hinglish markers
        hinglish_words = ["namaste", "pranam", "kisan", "kheti", "haan", "nahi", "saal", "meri", "mera", "hume", "chahiye", "bhaiya", "suno", "madad"]
        t_low = text.lower()
        if any(w in t_low for w in hinglish_words):
            return "hi"
        # Common English markers
        english_words = ["hello", "hi", "i am", "my name is", "farmer", "scheme", "benefit", "years old", "income", "eligible"]
        if any(w in t_low for w in english_words):
            return "en"
        return self.language

    def process_utterance(self, user_text: str, forced_lang: Optional[str] = None) -> AgentTurnResponse:
        """Processes a caller turn, updates knowledge, checks rules, and returns voice response."""
        lang = forced_lang or self.detect_language(user_text)
        self.language = lang
        self.history.append({"role": "user", "text": user_text})

        # Step 1: NLU Slot Extraction
        extracted_slots = self.nlu.extract_slots(user_text, self.profile)

        # Step 2: Contradiction Check
        contradiction = self.contradiction_detector.detect_contradiction(
            extracted_slots,
            self.profile,
            user_text
        )

        if contradiction:
            self.state = "RECONCILING"
            self.active_contradiction = contradiction
            msg_en = contradiction.message_en
            msg_hi = contradiction.message_hi
            spoken = msg_hi if lang == "hi" else msg_en

            # Evaluate schemes with current profile
            evals = self.rules_engine.evaluate_all(self.profile)
            eligible_count = len([s for s in evals if s.status == "ELIGIBLE"])
            likely_count = len([s for s in evals if s.status == "LIKELY_ELIGIBLE"])

            resp = AgentTurnResponse(
                agent_message_en=msg_en,
                agent_message_hi=msg_hi,
                current_language=lang,
                spoken_text=spoken,
                state=self.state,
                questions_asked_count=self.questions_asked_count,
                slots_extracted_this_turn=extracted_slots,
                caller_profile=self.profile,
                schemes_evaluation=evals,
                eligible_schemes_count=eligible_count,
                likely_schemes_count=likely_count,
                contradiction=contradiction,
                decision_reached=False
            )
            self.history.append({"role": "agent", "text": spoken})
            return resp

        # If we were reconciling and received a clear resolution
        if self.active_contradiction and extracted_slots:
            self.active_contradiction = None

        # Step 3: Vague Answer Detection
        disambiguation = self.vague_detector.detect_vagueness(
            user_text,
            self.profile,
            self.last_asked_slot
        )

        if disambiguation:
            self.state = "DISAMBIGUATING"
            opts_en = " or ".join(disambiguation.clarification_options_en)
            opts_hi = " या ".join(disambiguation.clarification_options_hi)

            msg_en = f"To determine your eligibility accurately, could you clarify: is it {opts_en}?"
            msg_hi = f"आपकी सही पात्रता सुनिश्चित करने के लिए, क्या आप स्पष्ट कर सकते हैं: क्या यह {opts_hi} है?"
            spoken = msg_hi if lang == "hi" else msg_en

            evals = self.rules_engine.evaluate_all(self.profile)
            eligible_count = len([s for s in evals if s.status == "ELIGIBLE"])
            likely_count = len([s for s in evals if s.status == "LIKELY_ELIGIBLE"])

            resp = AgentTurnResponse(
                agent_message_en=msg_en,
                agent_message_hi=msg_hi,
                current_language=lang,
                spoken_text=spoken,
                state=self.state,
                questions_asked_count=self.questions_asked_count,
                slots_extracted_this_turn=extracted_slots,
                caller_profile=self.profile,
                schemes_evaluation=evals,
                eligible_schemes_count=eligible_count,
                likely_schemes_count=likely_count,
                disambiguation=disambiguation,
                decision_reached=False
            )
            self.history.append({"role": "agent", "text": spoken})
            return resp

        # Step 4: Update Profile with new slots
        for k, v in extracted_slots.items():
            setattr(self.profile, k, v)
            self.profile.extracted_slots_history[k] = v

        # Step 5: Rules Evaluation
        evals = self.rules_engine.evaluate_all(self.profile)
        eligible_schemes = [s for s in evals if s.status == "ELIGIBLE"]
        likely_schemes = [s for s in evals if s.status == "LIKELY_ELIGIBLE"]

        # Step 6: Determine Next Action (Decision vs Next Question)
        slot_to_ask, next_q_en, next_q_hi = self.questioner.select_next_question(
            self.profile,
            evals,
            self.questions_asked_count
        )

        if slot_to_ask is None or (len(eligible_schemes) >= 1 and self.questions_asked_count >= 3):
            # DECISION REACHED: Present recommendations & explain reasoning
            self.state = "RECOMMENDING"
            decision_reached = True

            if eligible_schemes:
                names_en = ", ".join([s.name_en for s in eligible_schemes[:3]])
                names_hi = ", ".join([s.name_hi for s in eligible_schemes[:3]])
                top_scheme = eligible_schemes[0]

                msg_en = (
                    f"Congratulations! Based on the details provided, you are eligible for {len(eligible_schemes)} welfare scheme(s): "
                    f"{names_en}. For example, under {top_scheme.name_en}, you qualify for {top_scheme.benefits_en}. "
                    "All required criteria have been verified. Would you like me to explain the application process or documents needed?"
                )
                msg_hi = (
                    f"बधाई हो! आपकी दी गई जानकारी के अनुसार आप {len(eligible_schemes)} सरकारी योजनाओं के लिए पूरी तरह पात्र हैं: "
                    f"{names_hi}। उदाहरण के लिए, {top_scheme.name_hi} के तहत आपको {top_scheme.benefits_hi} का लाभ मिलेगा। "
                    "सभी पात्रता नियम सत्यापित हो चुके हैं। क्या आप आवेदन करने के चरण या आवश्यक दस्तावेजों की जानकारी चाहते हैं?"
                )
            elif likely_schemes:
                top_likely = likely_schemes[0]
                msg_en = (
                    f"You are very likely eligible for {top_likely.name_en} ({top_likely.benefits_en}). "
                    f"To finalize your application, please have your {', '.join(top_likely.required_documents_en[:2])} ready."
                )
                msg_hi = (
                    f"आप {top_likely.name_hi} ({top_likely.benefits_hi}) के लिए अत्यधिक संभावित पात्र हैं। "
                    f"आवेदन पूरा करने के लिए अपने {', '.join(top_likely.required_documents_hi[:2])} तैयार रखें।"
                )
            else:
                msg_en = (
                    "Based on your profile, we could not find an immediate direct central welfare scheme match. "
                    "However, you may explore state-specific livelihood or skill development programs on myScheme.gov.in."
                )
                msg_hi = (
                    "आपकी दी गई जानकारी के अनुसार वर्तमान में कोई सीधी केंद्रीय कल्याण योजना मेल नहीं खाती। "
                    "लेकिन आप myScheme.gov.in पर राज्य स्तरीय आजीविका या कौशल विकास योजनाएं देख सकते हैं।"
                )

            spoken = msg_hi if lang == "hi" else msg_en

            resp = AgentTurnResponse(
                agent_message_en=msg_en,
                agent_message_hi=msg_hi,
                current_language=lang,
                spoken_text=spoken,
                state=self.state,
                questions_asked_count=self.questions_asked_count,
                slots_extracted_this_turn=extracted_slots,
                caller_profile=self.profile,
                schemes_evaluation=evals,
                eligible_schemes_count=len(eligible_schemes),
                likely_schemes_count=len(likely_schemes),
                decision_reached=True
            )
            self.history.append({"role": "agent", "text": spoken})
            return resp

        # Step 7: Ask Next Optimal Question
        self.state = "INQUIRING"
        self.last_asked_slot = slot_to_ask
        self.questions_asked_count += 1

        msg_en = next_q_en
        msg_hi = next_q_hi
        spoken = msg_hi if lang == "hi" else msg_en

        resp = AgentTurnResponse(
            agent_message_en=msg_en,
            agent_message_hi=msg_hi,
            current_language=lang,
            spoken_text=spoken,
            state=self.state,
            questions_asked_count=self.questions_asked_count,
            slots_extracted_this_turn=extracted_slots,
            caller_profile=self.profile,
            schemes_evaluation=evals,
            eligible_schemes_count=len(eligible_schemes),
            likely_schemes_count=len(likely_schemes),
            decision_reached=False,
            next_recommended_question_en=next_q_en,
            next_recommended_question_hi=next_q_hi
        )
        self.history.append({"role": "agent", "text": spoken})
        return resp
