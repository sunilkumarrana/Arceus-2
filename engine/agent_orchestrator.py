"""
Conversation Orchestrator and Dialogue State Machine.
Coordinates NLU, Intent Matching, Contradiction Detection, Vague Disambiguation, Rules Reasoning, and Voice Response generation.
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

        # Scheme intent keywords
        self.scheme_intent_map = {
            "pm_kisan": ["pm kisan", "pmkisan", "kisan samman", "kheti", "farmer", "agriculture", "किसान", "खेती", "कृषि"],
            "pmjay": ["ayushman", "pmjay", "pm-jay", "health", "hospital", "medical", "swasthya", "ilaj", "आयुष्मान", "इलाज", "स्वास्थ्य", "अस्पताल"],
            "pmay_g": ["pmay", "awas", "housing", "makan", "ghar", "pucca house", "आवास", "मकान", "घर"],
            "pm_svanidhi": ["svanidhi", "street vendor", "thela", "hawker", "rehri", "vendor loan", "रेहड़ी", "ठेले", "स्वनिधि", "पटरी", "दुकान"],
            "pmuy_ujjwala": ["ujjwala", "gas cylinder", "lpg", "chulha", "उज्ज्वला", "गैस", "सिलेंडर", "चूल्हा"],
            "apy": ["atal pension", "apy", "pension", "पेंशन", "60 साल"],
            "ssy": ["sukanya", "samriddhi", "girl child", "beti", "daughter", "सुकन्या", "बेटी", "बालिका"],
            "ignops": ["old age", "vriddha", "senior citizen", "बुजुर्ग", "वृद्धावस्था"],
            "pm_vishwakarma": ["vishwakarma", "artisan", "carpenter", "blacksmith", "badhai", "karigar", "toolkit", "विश्वकर्मा", "कारीगर", "बढ़ई"],
            "mgnrega": ["mgnrega", "nrega", "100 days", "unskilled labour", "rozgar", "मनरेगा", "नरेगा", "रोजगार"],
            "pmmvy": ["matru vandana", "pmmvy", "pregnant", "garbhvati", "maternity", "मातृ वंदना", "गर्भवती"],
            "pm_surya_ghar": ["surya", "solar", "rooftop", "muft bijli", "electricity", "सोलर", "सूर्य घर", "बिजली", "रूफटॉप"]
        }

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
        if re.search(r'[\u0900-\u097F]', text):
            return "hi"
        hinglish_words = ["namaste", "pranam", "kisan", "kheti", "haan", "nahi", "saal", "meri", "mera", "hume", "chahiye", "bhaiya", "suno", "madad"]
        t_low = text.lower()
        if any(w in t_low for w in hinglish_words):
            return "hi"
        english_words = ["hello", "hi", "i am", "my name is", "farmer", "scheme", "benefit", "years old", "income", "eligible"]
        if any(w in t_low for w in english_words):
            return "en"
        return self.language

    def match_scheme_intent(self, text: str) -> List[str]:
        """Matches user text against known welfare scheme keywords."""
        t_low = text.lower()
        matched = []
        for scheme_id, keywords in self.scheme_intent_map.items():
            if any(k in t_low for k in keywords):
                matched.append(scheme_id)
        return matched

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

        # Clear contradiction if resolved
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

        # Step 5: Direct Scheme Intent Matching
        matched_intent_ids = self.match_scheme_intent(user_text)

        # Step 6: Rules Evaluation
        evals = self.rules_engine.evaluate_all(self.profile)

        # If user explicitly asked for specific scheme(s), boost them to the very top!
        if matched_intent_ids:
            def sort_key(s):
                if s.scheme_id in matched_intent_ids:
                    return (0, -s.match_score)
                status_priority = {"ELIGIBLE": 1, "LIKELY_ELIGIBLE": 2, "UNKNOWN": 3, "NOT_ELIGIBLE": 4}
                return (status_priority.get(s.status, 5), -s.match_score)
            evals.sort(key=sort_key)

        eligible_schemes = [s for s in evals if s.status == "ELIGIBLE"]
        likely_schemes = [s for s in evals if s.status == "LIKELY_ELIGIBLE"]

        # Step 7: Formulate Response
        # If user asked about a specific scheme (e.g. "PM Kisan" or "Ayushman Bharat")
        if matched_intent_ids:
            target_scheme = next((s for s in evals if s.scheme_id == matched_intent_ids[0]), None)
            if target_scheme:
                scheme_title_en = target_scheme.name_en
                scheme_title_hi = target_scheme.name_hi
                benefits_en = target_scheme.benefits_en
                benefits_hi = target_scheme.benefits_hi

                if target_scheme.status == "ELIGIBLE":
                    msg_en = f"Great news! You qualify for {scheme_title_en}. It provides {benefits_en}. I have shown the full details on your screen."
                    msg_hi = f"बढ़िया! आप {scheme_title_hi} के लिए पूरी तरह पात्र हैं। इसके तहत आपको {benefits_hi} मिलता है। मैंने स्क्रीन पर योजना का पूरा विवरण दिखा दिया है।"
                else:
                    msg_en = f"Here are the details for {scheme_title_en}: it provides {benefits_en}. To check your exact eligibility, could you tell me your age or approximate income?"
                    msg_hi = f"{scheme_title_hi} के तहत आपको {benefits_hi} मिलता है। आपकी पात्रता जांचने के लिए, क्या आप अपनी उम्र या सालाना कमाई बता सकते हैं?"

                spoken = msg_hi if lang == "hi" else msg_en
                resp = AgentTurnResponse(
                    agent_message_en=msg_en,
                    agent_message_hi=msg_hi,
                    current_language=lang,
                    spoken_text=spoken,
                    state="RECOMMENDING",
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

        # Step 8: Information Gain Question or Decision Reached
        slot_to_ask, next_q_en, next_q_hi = self.questioner.select_next_question(
            self.profile,
            evals,
            self.questions_asked_count
        )

        if slot_to_ask is None or (len(eligible_schemes) >= 1 and self.questions_asked_count >= 2):
            self.state = "RECOMMENDING"
            decision_reached = True

            if eligible_schemes:
                names_en = ", ".join([s.name_en.split('(')[0].strip() for s in eligible_schemes[:3]])
                names_hi = ", ".join([s.name_hi.split('(')[0].strip() for s in eligible_schemes[:3]])
                top_scheme = eligible_schemes[0]

                msg_en = (
                    f"Based on what you told me, you are eligible for {names_en}. "
                    f"For instance, under {top_scheme.name_en.split('(')[0].strip()}, you qualify for {top_scheme.benefits_en}. "
                    "I have displayed the related scheme cards below on your screen."
                )
                msg_hi = (
                    f"आपकी जानकारी के अनुसार आप {names_hi} के लिए पात्र हैं। "
                    f"जैसे {top_scheme.name_hi.split('(')[0].strip()} के तहत आपको {top_scheme.benefits_hi} का लाभ मिलेगा। "
                    "मैंने संबंधित योजनाओं का विवरण आपकी स्क्रीन पर दिखा दिया है।"
                )
            elif likely_schemes:
                top_likely = likely_schemes[0]
                msg_en = (
                    f"You are very likely eligible for {top_likely.name_en.split('(')[0].strip()} ({top_likely.benefits_en}). "
                    f"Please check the details shown below."
                )
                msg_hi = (
                    f"आप {top_likely.name_hi.split('(')[0].strip()} के लिए संभावित पात्र हैं। "
                    f"कृपया नीचे दिए गए योजना विवरण को देखें।"
                )
            else:
                msg_en = "I have displayed the available welfare schemes below. You can ask me about farming, healthcare, pension, or housing."
                msg_hi = "मैंने संबंधित सरकारी योजनाएं नीचे दिखा दी हैं। आप मुझसे खेती, स्वास्थ्य, पेंशन या आवास के बारे में पूछ सकते हैं।"

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

        # Ask next optimal question
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
