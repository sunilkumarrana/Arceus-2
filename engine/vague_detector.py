"""
Vague Response Detection & Structured Disambiguation Engine.
Detects vague or imprecise citizen statements and converts them into targeted choices.
"""
import re
from typing import Optional, List
from engine.models import DisambiguationNotice, CallerProfile


class VagueDetector:
    def __init__(self):
        self.vague_income_phrases = [
            "kuch khas nahi", "thoda bahut", "bas gujara", "kam hi hai", "kamai kam hai",
            "not much", "very little", "hardly anything", "low income", "odd jobs",
            "kabhi milta hai kabhi nahi", "chalau", "gujara chal jata hai",
            "just manage", "scant", "meager", "thoda sa", "chhota mota kamai"
        ]

        self.vague_land_phrases = [
            "thodi si zameen", "thoda sa khet", "chhota khet", "chhoti zameen",
            "small patch", "some land", "little land", "kuch bigha", "chhoti si zameen",
            "thoda khet"
        ]

        self.vague_occupation_phrases = [
            "chhota mota kaam", "sab kaam kar lete", "whatever work", "kuch bhi kar lete",
            "odd jobs", "har tarah ka kaam", "idhar udhar ka kaam", "koi pakka kaam nahi",
            "temporary work", "roz ka alag", "casual work"
        ]

        self.vague_house_phrases = [
            "sadharan ghar", "bas rehne ki jagah", "simple house", "normal house",
            "chhota sa ghar", "kisi tarah reh rahe", "bas chhat hai"
        ]

    def detect_vagueness(self, text: str, current_profile: CallerProfile, last_inquiry_slot: Optional[str] = None) -> Optional[DisambiguationNotice]:
        t = text.lower().strip()

        # Check 1: Vague Income
        if (last_inquiry_slot in ["annual_income", "bpl_status", None]) and any(p in t for p in self.vague_income_phrases):
            # Verify if user actually gave a clear number
            if not re.search(r'\d{3,}', t) and not any(w in t for w in ["lakh", "lac", "hazar", "thousand", "लाख", "हजार"]):
                return DisambiguationNotice(
                    slot="annual_income",
                    raw_utterance=text,
                    detected_ambiguity="Vague income statement without numerical bracket",
                    clarification_options_en=[
                        "Under ₹1 Lakh / year (Very low income)",
                        "Between ₹1 Lakh - ₹2.5 Lakh / year",
                        "Above ₹2.5 Lakh / year"
                    ],
                    clarification_options_hi=[
                        "सालाना ₹1 लाख से कम (अति निर्धन)",
                        "₹1 लाख से ₹2.5 लाख के बीच",
                        "₹2.5 लाख से अधिक"
                    ]
                )

        # Check 2: Vague Landholding
        if (last_inquiry_slot in ["has_land", "land_ha", None]) and any(p in t for p in self.vague_land_phrases):
            if not re.search(r'\d+(?:\.\d+)?\s*(?:hectare|acre|bigha|हेक्टेयर|एकड़|बीघा)', t):
                return DisambiguationNotice(
                    slot="has_land",
                    raw_utterance=text,
                    detected_ambiguity="Vague landholding without specified area or title",
                    clarification_options_en=[
                        "Own cultivable land under 2 hectares (5 acres)",
                        "Own cultivable land above 2 hectares",
                        "Landless / Working on others' land"
                    ],
                    clarification_options_hi=[
                        "2 हेक्टेयर (लगभग 5 एकड़) से कम कृषि भूमि अपने नाम",
                        "2 हेक्टेयर से अधिक कृषि भूमि",
                        "भूमिहीन / दूसरों के खेत में मजदूरी"
                    ]
                )

        # Check 3: Vague Occupation
        if (last_inquiry_slot in ["occupation", None]) and any(p in t for p in self.vague_occupation_phrases):
            return DisambiguationNotice(
                slot="occupation",
                raw_utterance=text,
                detected_ambiguity="Multiple or undefined informal trades mentioned",
                clarification_options_en=[
                    "Farmer cultivating own or leased land",
                    "Daily wage agricultural / manual labourer",
                    "Street vendor / Roadside hawker (Thela-wala)",
                    "Traditional artisan / craftsman (carpenter, blacksmith, potter, etc.)"
                ],
                clarification_options_hi=[
                    "किसान (अपनी जमीन पर खेती करने वाले)",
                    "दैनिक खेतिहर / निर्माण मजदूर",
                    "रेहड़ी-पटरी / ठेले वाले विक्रेता",
                    "पारंपरिक कारीगर (बढ़ई, लोहार, कुम्हार, दर्जी आदि)"
                ]
            )

        # Check 4: Vague House Type
        if (last_inquiry_slot in ["house_type", None]) and any(p in t for p in self.vague_house_phrases):
            return DisambiguationNotice(
                slot="house_type",
                raw_utterance=text,
                detected_ambiguity="Ambiguous housing structure description",
                clarification_options_en=[
                    "Kutcha house (mud walls, thatched/tin roof)",
                    "Pucca house (brick and concrete construction)",
                    "Homeless / Living in rented room"
                ],
                clarification_options_hi=[
                    "कच्चा मकान (मिट्टी की दीवारें, टीन या छप्पर)",
                    "पक्का मकान (ईंट और सीमेंट की छत)",
                    "बेघर / किराए के कमरे में"
                ]
            )

        return None
