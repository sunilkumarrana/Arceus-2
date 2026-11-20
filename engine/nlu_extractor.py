"""
High-Precision Multilingual NLU and Slot Extractor for English, Hindi, and Hinglish.
Extracts multiple demographic and socio-economic slots in a single caller turn.
"""
import re
from typing import Dict, Any, Tuple, Optional
from engine.models import CallerProfile


class NLUSlotExtractor:
    def __init__(self):
        # Hindi word-to-number mappings for common spoken numbers
        self.hi_numbers = {
            "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5,
            "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
            "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15,
            "सोलह": 16, "सत्रह": 17, "अठारह": 18, "उन्नीस": 19, "बीस": 20,
            "इक्कीस": 21, "बाइस": 22, "तेईस": 23, "चौबीस": 24, "पच्चीस": 25,
            "छब्बीस": 26, "सत्ताईस": 27, "अट्ठाइस": 28, "उनतीस": 29, "तीस": 30,
            "पैंतीस": 35, "चालीस": 40, "पैंतालीस": 45, "पचास": 50,
            "पचपन": 55, "साठ": 60, "पैंसठ": 65, "सत्तर": 70, "पचहत्तर": 75,
            "अस्सी": 80, "पचासी": 85, "नब्बे": 90, "सौ": 100
        }

    def extract_slots(self, text: str, current_profile: Optional[CallerProfile] = None) -> Dict[str, Any]:
        """Extracts all recognizable slots from the caller's utterance."""
        slots: Dict[str, Any] = {}
        t = text.lower().strip()

        # 1. AGE EXTRACTION
        age = self._extract_age(t)
        if age is not None:
            slots["age"] = age

        # 2. GENDER EXTRACTION
        gender = self._extract_gender(t)
        if gender is not None:
            slots["gender"] = gender

        # 3. OCCUPATION EXTRACTION
        occ = self._extract_occupation(t)
        if occ is not None:
            slots["occupation"] = occ

        # 4. INCOME EXTRACTION (Annualized)
        income = self._extract_income(t)
        if income is not None:
            slots["annual_income"] = income

        # 5. LAND OWNERSHIP AND SIZE
        has_land, land_ha = self._extract_land(t)
        if has_land is not None:
            slots["has_land"] = has_land
        if land_ha is not None:
            slots["land_ha"] = land_ha

        # 6. HOUSING TYPE
        house = self._extract_house_type(t)
        if house is not None:
            slots["house_type"] = house

        # 7. AREA (RURAL / URBAN)
        area = self._extract_area(t)
        if area is not None:
            slots["area_type"] = area

        # 8. BPL / POVERTY STATUS
        bpl = self._extract_bpl(t)
        if bpl is not None:
            slots["bpl_status"] = bpl

        # 9. EXCLUSIONS (Taxpayer, Govt employee, LPG)
        tax = self._extract_taxpayer(t)
        if tax is not None:
            slots["is_tax_payer"] = tax

        govt = self._extract_govt_employee(t)
        if govt is not None:
            slots["is_govt_employee"] = govt

        lpg = self._extract_lpg(t)
        if lpg is not None:
            slots["has_existing_lpg"] = lpg

        # 10. SPECIAL FAMILY CONDITIONS
        girl_child = self._extract_girl_child(t)
        if girl_child is not None:
            slots["has_girl_child_under_10"] = girl_child

        maternity = self._extract_maternity(t)
        if maternity is not None:
            slots["is_pregnant_or_lactating"] = maternity

        return slots

    def _extract_age(self, t: str) -> Optional[int]:
        # Regex patterns for age
        # e.g. "age is 45", "45 years old", "45 saal", "45 baras", "उम्र 45", "45 वर्ष"
        patterns = [
            r'(?:age|उम्र|आयु)\s*(?:is|hai|ho gayi|meri)?\s*(\d{1,3})',
            r'(\d{1,3})\s*(?:years|year|yrs|saal|sal|bars|baras|varsh|साल|वर्ष|बरस)',
            r'i\s*am\s*(\d{1,3})',
            r'main\s*(\d{1,3})\s*ka',
            r'main\s*(\d{1,3})\s*ki'
        ]
        for pat in patterns:
            m = re.search(pat, t)
            if m:
                val = int(m.group(1))
                if 1 <= val <= 110:
                    return val

        # Hindi word numbers: "पैंतालीस साल", "साठ वर्ष"
        for word, num in self.hi_numbers.items():
            if re.search(rf'{word}\s*(?:साल|वर्ष|बरस|saal)', t):
                return num

        return None

    def _extract_gender(self, t: str) -> Optional[str]:
        # Female cues
        female_cues = [
            r'\b(?:female|woman|lady|girl|mother|wife|widow)\b',
            r'\b(?:महिला|औरत|स्त्री|लड़की|माता|पत्नी|विधवा|बहू|बेटी|गृहिणी)\b',
            r'\b(?:mahila|aurat|ladki|mata|patni|vidhwa|grihini)\b',
            r'\bmai\s+aurat\s+hu\b',
            r'\bmai\s+mahila\s+hu\b'
        ]
        for cue in female_cues:
            if re.search(cue, t):
                return "female"

        # Male cues
        male_cues = [
            r'\b(?:male|man|boy|father|husband)\b',
            r'\b(?:पुरुष|आदमी|लड़का|पिता|पति)\b',
            r'\b(?:purush|aadmi|ladka|pita|pati)\b'
        ]
        for cue in male_cues:
            if re.search(cue, t):
                return "male"

        return None

    def _extract_occupation(self, t: str) -> Optional[str]:
        # Farmer
        if any(w in t for w in ["farmer", "kisan", "kheti", "farming", "agriculture", "किसान", "खेती", "कृषि", "khet me"]):
            return "farmer"

        # Street Vendor / Hawker
        if any(w in t for w in ["street vendor", "hawker", "thela", "thelawala", "rehri", "stall", "roadside vendor", "ठेले", "रेहड़ी", "पटरी", "सड़क किनारे", "दुकानदार"]):
            return "street_vendor"

        # Artisan / Traditional Craftsman
        artisan_words = [
            "carpenter", "blacksmith", "potter", "sculptor", "cobbler", "mason", "tailor", "weaver", "barber",
            "बढ़ई", "लोहार", "कुम्हार", "मोची", "राजमिस्त्री", "दर्जी", "बुनकर", "कारीगर", "शिल्पकार",
            "badhai", "lohar", "kumhar", "mochi", "mistri", "darzi", "karigar", "artisan"
        ]
        if any(w in t for w in artisan_words):
            return "artisan"

        # Daily wage / manual worker
        if any(w in t for w in ["daily wage", "mazdoor", "majdoor", "labour", "labor", "dihadi", "kuli", "मजदूर", "मजदूरी", "दिहाड़ी", "श्रमिक"]):
            return "unskilled_labour"

        # Student
        if any(w in t for w in ["student", "studying", "padhai", "विद्यार्थी", "छात्र", "छात्रा"]):
            return "student"

        # Unemployed
        if any(w in t for w in ["unemployed", "berojgar", "jobless", "no work", "बेरोजगार", "कोई काम नहीं"]):
            return "unemployed"

        # Retired / Pensioner
        if any(w in t for w in ["retired", "retirement", "buzurg", "vriddh", "बुजुर्ग", "वृद्ध", "पेंशनभोगी"]):
            return "retired"

        return None

    def _extract_income(self, t: str) -> Optional[float]:
        # Monthly income indicators (e.g. "8000 per month", "10000 mahina", "10 हजार महीना")
        monthly_m = re.search(r'(\d+[\d,.]*)\s*(?:k|thousand|hazar|हजार)?\s*(?:per\s*month|pm|mahina|mahine|प्रति\s*माह|महीना)', t)
        if monthly_m:
            num_str = monthly_m.group(1).replace(',', '')
            try:
                base = float(num_str)
                if "hazar" in t or "हजार" in t or "thousand" in t or "k" in t:
                    base *= 1000
                elif base < 200:
                    base *= 1000
                return base * 12.0  # Annualized
            except ValueError:
                pass

        # Lakh phrases (e.g. "1.5 lakh", "2 lakh", "2.5 lakh", "दो लाख", "डेढ़ लाख")
        lakh_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lac|लाख)', t)
        if lakh_m:
            return float(lakh_m.group(1)) * 100000.0

        if "डेढ़ लाख" in t or "dedh lakh" in t:
            return 150000.0
        if "ढाई लाख" in t or "dhai lakh" in t:
            return 250000.0
        if "एक लाख" in t or "ek lakh" in t:
            return 100000.0
        if "दो लाख" in t or "do lakh" in t:
            return 200000.0

        # Direct annual numbers (e.g. "₹80,000", "80000", "60 thousand", "60 hazar", "60 हजार")
        hazar_m = re.search(r'(\d+)\s*(?:k|thousand|hazar|हजार)', t)
        if hazar_m:
            return float(hazar_m.group(1)) * 1000.0

        # Raw number >= 10000
        raw_m = re.search(r'(?:rs\.?|inr|₹|kamai|aamdani|income)?\s*(\d{4,7})\b', t)
        if raw_m:
            val = float(raw_m.group(1))
            if val >= 5000:
                if val <= 25000 and any(w in t for w in ["month", "mahina"]):
                    return val * 12.0
                return val

        return None

    def _extract_land(self, t: str) -> Tuple[Optional[bool], Optional[float]]:
        # Landless indicators
        if any(w in t for w in ["no land", "landless", "bhoomihin", "zameen nahi", "zamin nahi", "khet nahi", "भूमिहीन", "जमीन नहीं", "खेत नहीं"]):
            return (False, 0.0)

        # Land size in Hectares
        hec_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:hectare|hector|हेक्टेयर)', t)
        if hec_m:
            return (True, float(hec_m.group(1)))

        # Land size in Acres (1 Acre ≈ 0.4046 Hectares)
        acre_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:acre|एकड़|एकड)', t)
        if acre_m:
            ha = round(float(acre_m.group(1)) * 0.4046, 2)
            return (True, ha)

        # Land size in Bigha (1 Bigha ≈ 0.25 Hectares average)
        bigha_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:bigha|बीघा)', t)
        if bigha_m:
            ha = round(float(bigha_m.group(1)) * 0.25, 2)
            return (True, ha)

        # Generic positive land indication
        if any(w in t for w in ["have land", "own land", "khet hai", "zameen hai", "apni zameen", "जमीन है", "खेत है"]):
            return (True, 1.0)  # assumed smallholding until clarified

        return (None, None)

    def _extract_house_type(self, t: str) -> Optional[str]:
        if any(w in t for w in ["kutcha", "kaccha", "jhopdi", "mitti ka", "mud house", "tin shed", "thatch", "कच्चा", "झोपड़ी", "मिट्टी का"]):
            return "kutcha"
        if any(w in t for w in ["pucca", "pakka", "cement", "concrete", "rcc", "brick house", "पक्का", "ईंट का मकान"]):
            return "pucca"
        if any(w in t for w in ["homeless", "no house", "ghar nahi", "kiraye", "बेघर", "छत नहीं"]):
            return "homeless"
        return None

    def _extract_area(self, t: str) -> Optional[str]:
        if any(w in t for w in ["village", "gaon", "gramin", "rural", "dehat", "गाँव", "गांव", "ग्रामीण", "देहात"]):
            return "rural"
        if any(w in t for w in ["city", "town", "urban", "shahar", "kasba", "metro", "शहर", "शहरी", "कस्बा"]):
            return "urban"
        return None

    def _extract_bpl(self, t: str) -> Optional[bool]:
        if any(w in t for w in ["bpl", "ration card", "rashan card", "antyodaya", "garib", "garibi rekha", "बीपीएल", "राशन कार्ड", "अंत्योदय", "गरीबी रेखा"]):
            return True
        if any(w in t for w in ["no bpl", "apl card", "ameer", "taxpayer", "राशन कार्ड नहीं"]):
            return False
        return None

    def _extract_taxpayer(self, t: str) -> Optional[bool]:
        if any(w in t for w in ["pay tax", "income tax", "itr", "taxpayer", "tax bharta", "आयकर", "टैक्स भरता"]):
            if any(w in t for w in ["nahi", "no", "not", "नहीं"]):
                return False
            return True
        if any(w in t for w in ["no tax", "tax nahi", "don't pay tax", "टैक्स नहीं"]):
            return False
        return None

    def _extract_govt_employee(self, t: str) -> Optional[bool]:
        if any(w in t for w in ["govt employee", "govt job", "sarkari naukri", "सरकारी नौकरी", "सरकारी कर्मचारी"]):
            if any(w in t for w in ["nahi", "no", "not", "नहीं"]):
                return False
            return True
        if any(w in t for w in ["private", "daily wage", "no govt job", "sarkari nahi"]):
            return False
        return None

    def _extract_lpg(self, t: str) -> Optional[bool]:
        if any(w in t for w in ["have gas", "gas connection", "lpg cylinder", "hp gas", "indane", "सिलेंडर है", "गैस कनेक्शन है"]):
            if any(w in t for w in ["nahi", "no", "नहीं"]):
                return False
            return True
        if any(w in t for w in ["no gas", "no lpg", "chulhe", "chulha", "लकड़ी पर खाना", "गैस नहीं है"]):
            return False
        return None

    def _extract_girl_child(self, t: str) -> Optional[bool]:
        if any(w in t for w in ["beti", "daughter", "girl child", "ladki", "बेटी", "बालिका", "कन्या"]):
            # Check age if mentioned
            m = re.search(r'(?:beti|daughter|ladki|बेटी)\s*(?:is|ki उम्र)?\s*(\d{1,2})', t)
            if m:
                child_age = int(m.group(1))
                return child_age <= 10
            # If "chhoti beti" or "small daughter"
            if any(w in t for w in ["chhoti", "small", "little", "छोटी"]):
                return True
            return True
        return None

    def _extract_maternity(self, t: str) -> Optional[bool]:
        if any(w in t for w in ["pregnant", "pregnancy", "garbhwati", "bachha hone wala", "गर्भवती", "धात्री", "नया बच्चा"]):
            return True
        return None
