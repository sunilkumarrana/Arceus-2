"""
Contradiction Detection & Reconciliation Engine.
Detects factual, logical, and policy contradictions in citizen utterances.
"""
from typing import Optional, Dict, Any
from engine.models import CallerProfile, ContradictionAlert


class ContradictionDetector:
    def detect_contradiction(
        self,
        new_slots: Dict[str, Any],
        profile: CallerProfile,
        raw_text: str
    ) -> Optional[ContradictionAlert]:
        t = raw_text.lower().strip()

        # 1. AGE CONTRADICTIONS
        # Case 1A: New age vs Old age
        if "age" in new_slots and profile.age is not None:
            new_age = new_slots["age"]
            if abs(new_age - profile.age) >= 5:
                return ContradictionAlert(
                    slot="age",
                    previous_value=profile.age,
                    new_value=new_age,
                    message_en=(
                        f"Earlier you mentioned your age is {profile.age} years, but now you mentioned {new_age} years. "
                        "Could you please confirm your exact age so I can check the right schemes for you?"
                    ),
                    message_hi=(
                        f"आपने पहले बताया था कि आपकी आयु {profile.age} वर्ष है, और अभी आपने {new_age} वर्ष बताया। "
                        "कृपया अपनी सही उम्र स्पष्ट करें ताकि सही योजनाओं की जांच हो सके।"
                    ),
                    severity="HIGH"
                )

        # Case 1B: Young age (< 60) claiming Old Age Pension / Retirement
        curr_age = new_slots.get("age", profile.age)
        if curr_age is not None and curr_age < 60:
            if any(w in t for w in ["old age pension", "vriddha pension", "retire ho gaya", "retired for", "senior citizen pension", "वृद्धावस्था पेंशन", "पेंशन चाहिए 60 साल वाली"]):
                return ContradictionAlert(
                    slot="age_vs_pension",
                    previous_value=f"Age {curr_age}",
                    new_value="Requesting Senior Citizen Pension",
                    message_en=(
                        f"You mentioned earlier that you are {curr_age} years old. The National Old Age Pension Scheme "
                        f"(IGNOAPS) strictly requires applicants to be 60 years or older. "
                        "Could you please clarify your actual age or if you are inquiring on behalf of an elderly family member?"
                    ),
                    message_hi=(
                        f"आपने पहले अपनी उम्र {curr_age} वर्ष बताई थी, जबकि राष्ट्रीय वृद्धावस्था पेंशन योजना "
                        f"के लिए न्यूनतम 60 वर्ष की आयु अनिवार्य है। "
                        "क्या आप अपनी सही उम्र स्पष्ट कर सकते हैं, या आप परिवार के किसी बुजुर्ग के लिए पूछ रहे हैं?"
                    ),
                    severity="HIGH"
                )

        # 2. INCOME VS BPL / TAXPAYER CONTRADICTIONS
        curr_income = new_slots.get("annual_income", profile.annual_income)
        curr_bpl = new_slots.get("bpl_status", profile.bpl_status)
        curr_tax = new_slots.get("is_tax_payer", profile.is_tax_payer)

        # Case 2A: High Income claiming BPL
        if curr_income is not None and curr_income >= 300000 and curr_bpl is True:
            return ContradictionAlert(
                slot="income_vs_bpl",
                previous_value="BPL Card Holder",
                new_value=f"Annual Income ₹{int(curr_income):,}",
                message_en=(
                    f"A household income of ₹{int(curr_income):,} per year is above the statutory Below Poverty Line (BPL) threshold. "
                    "Could you clarify if your personal income is different from your official ration card status?"
                ),
                message_hi=(
                    f"सालाना ₹{int(curr_income):,} की आय गरीबी रेखा (बीपीएल) की आधिकारिक सीमा से अधिक है। "
                    "कृपया स्पष्ट करें कि क्या आपका राशन कार्ड बीपीएल श्रेणी का है या वार्षिक आय भिन्न है?"
                ),
                severity="HIGH"
            )

        # Case 2B: Income Tax Payer claiming BPL
        if curr_tax is True and curr_bpl is True:
            return ContradictionAlert(
                slot="tax_vs_bpl",
                previous_value="BPL Status",
                new_value="Income Tax Payer",
                message_en=(
                    "You indicated both being an income tax payer and having BPL status, which are mutually exclusive under government welfare rules. "
                    "Could you please confirm if you file income tax returns?"
                ),
                message_hi=(
                    "आपने आयकर दाता होने और बीपीएल श्रेणी दोनों का उल्लेख किया है, जो सरकारी नियमों में परस्पर विरोधी हैं। "
                    "कृपया स्पष्ट करें कि क्या आप आयकर भरते हैं?"
                ),
                severity="HIGH"
            )

        # 3. LAND OWNERSHIP CONTRADICTION
        # Landless vs owning land
        if "has_land" in new_slots and profile.has_land is not None:
            if profile.has_land is False and new_slots["has_land"] is True:
                return ContradictionAlert(
                    slot="has_land",
                    previous_value="Landless",
                    new_value="Owns Land",
                    message_en=(
                        "Earlier you indicated you do not own land, but now you mentioned agricultural landholding. "
                        "Do you own agricultural land registered in your name?"
                    ),
                    message_hi=(
                        "पहले आपने बताया था कि आपके पास कृषि भूमि नहीं है, पर अभी आपने जमीन का जिक्र किया। "
                        "क्या आपके नाम पर आधिकारिक कृषि भूमि दर्ज है?"
                    ),
                    severity="HIGH"
                )

        # 4. HOUSING CONTRADICTION
        if "house_type" in new_slots and profile.house_type is not None:
            if profile.house_type == "pucca" and new_slots["house_type"] in ["kutcha", "homeless"]:
                return ContradictionAlert(
                    slot="house_type",
                    previous_value="Pucca (Concrete) House",
                    new_value=f"{new_slots['house_type'].capitalize()} House",
                    message_en=(
                        "You previously stated you have a pucca house, but now mentioned living in a kutcha house. "
                        "Which best describes your current residential condition?"
                    ),
                    message_hi=(
                        "आपने पहले बताया था कि आपके पास पक्का मकान है, और अब कच्चे मकान का उल्लेख किया। "
                        "कृपया स्पष्ट करें कि आपका मौजूदा निवास किस प्रकार का है?"
                    ),
                    severity="HIGH"
                )

        # 5. GENDER VS MATERNITY CONTRADICTION
        curr_gender = new_slots.get("gender", profile.gender)
        if curr_gender == "male":
            if any(w in t for w in ["i am pregnant", "garbhvati hu", "mera bachha hone wala hai", "main garbhavati hu"]):
                return ContradictionAlert(
                    slot="gender_vs_maternity",
                    previous_value="Male Applicant",
                    new_value="Pregnancy Claim",
                    message_en=(
                        "Maternity benefits like PMMVY are provided directly to the pregnant mother. "
                        "Are you inquiring on behalf of your wife or a female family member?"
                    ),
                    message_hi=(
                        "मातृत्व वंदना योजना के लाभ सीधे गर्भवती माता के बैंक खाते में दिए जाते हैं। "
                        "क्या आप अपनी पत्नी अथवा परिवार की किसी महिला के लिए जानकारी ले रहे हैं?"
                    ),
                    severity="HIGH"
                )

        return None
