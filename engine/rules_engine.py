"""
Deterministic and Explainable Rules Evaluation Engine for Welfare Schemes.
Evaluates caller profiles against structured criteria from myScheme.
"""
import json
import os
from typing import List, Dict, Any, Tuple
from engine.models import CallerProfile, SchemeEligibility, RuleItemCheck


class SchemeRulesEngine:
    def __init__(self, schemes_file: str = None):
        if schemes_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            schemes_file = os.path.join(base_dir, "data", "schemes.json")
        self.schemes_file = schemes_file
        self.schemes_data = self._load_schemes()

    def _load_schemes(self) -> List[Dict[str, Any]]:
        with open(self.schemes_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("schemes", [])

    def evaluate_all(self, profile: CallerProfile) -> List[SchemeEligibility]:
        """Evaluates all schemes against the caller profile and returns ranked results."""
        results = []
        for scheme in self.schemes_data:
            eval_res = self.evaluate_scheme(scheme, profile)
            results.append(eval_res)

        # Sort order: ELIGIBLE first, then LIKELY_ELIGIBLE, then UNKNOWN, then NOT_ELIGIBLE
        status_priority = {
            "ELIGIBLE": 1,
            "LIKELY_ELIGIBLE": 2,
            "UNKNOWN": 3,
            "NOT_ELIGIBLE": 4
        }
        results.sort(key=lambda s: (status_priority.get(s.status, 5), -s.match_score))
        return results

    def evaluate_scheme(self, scheme: Dict[str, Any], profile: CallerProfile) -> SchemeEligibility:
        rules = scheme.get("rules", {})
        breakdown: List[RuleItemCheck] = []
        disqualifiers: List[str] = []
        missing_criteria: List[str] = []

        passed_count = 0
        total_evaluable = 0

        # 1. AGE CHECK
        min_age = rules.get("min_age", 0)
        max_age = rules.get("max_age", 120)
        target_person = rules.get("target_person", "applicant")

        if target_person == "girl_child":
            # Scheme like Sukanya Samriddhi
            if profile.has_girl_child_under_10 is True:
                breakdown.append(RuleItemCheck(
                    criterion="age_target",
                    criterion_label_en="Girl child under 10 years",
                    criterion_label_hi="10 वर्ष से कम आयु की बालिका",
                    required_value="Age <= 10 years",
                    actual_value="Yes",
                    status="PASSED",
                    explanation_en="Has girl child below 10 years eligible for opening account.",
                    explanation_hi="10 वर्ष से कम उम्र की बालिका मौजूद है, खाता खोला जा सकता है।"
                ))
                passed_count += 1
            elif profile.has_girl_child_under_10 is False:
                breakdown.append(RuleItemCheck(
                    criterion="age_target",
                    criterion_label_en="Girl child under 10 years",
                    criterion_label_hi="10 वर्ष से कम आयु की बालिका",
                    required_value="Age <= 10 years",
                    actual_value="No",
                    status="FAILED",
                    explanation_en="Requires a girl child under 10 years of age.",
                    explanation_hi="इसके लिए 10 वर्ष से कम उम्र की बालिका होना आवश्यक है।"
                ))
                disqualifiers.append("No girl child under 10 years / 10 वर्ष से कम की बालिका नहीं")
            else:
                breakdown.append(RuleItemCheck(
                    criterion="age_target",
                    criterion_label_en="Girl child under 10 years",
                    criterion_label_hi="10 वर्ष से कम आयु की बालिका",
                    required_value="Age <= 10 years",
                    actual_value=None,
                    status="UNKNOWN",
                    explanation_en="Information on whether caller has a daughter under 10 is needed.",
                    explanation_hi="क्या आपकी 10 वर्ष से कम उम्र की बेटी है, यह जानकारी चाहिए।"
                ))
                missing_criteria.append("has_girl_child_under_10")
            total_evaluable += 1
        else:
            if profile.age is not None:
                if min_age <= profile.age <= max_age:
                    breakdown.append(RuleItemCheck(
                        criterion="age",
                        criterion_label_en=f"Age ({min_age}-{max_age} yrs)",
                        criterion_label_hi=f"आयु ({min_age}-{max_age} वर्ष)",
                        required_value=f"{min_age} - {max_age}",
                        actual_value=profile.age,
                        status="PASSED",
                        explanation_en=f"Age {profile.age} is within eligible bracket ({min_age}-{max_age} yrs).",
                        explanation_hi=f"आयु {profile.age} वर्ष पात्रता सीमा ({min_age}-{max_age} वर्ष) के भीतर है।"
                    ))
                    passed_count += 1
                else:
                    breakdown.append(RuleItemCheck(
                        criterion="age",
                        criterion_label_en=f"Age ({min_age}-{max_age} yrs)",
                        criterion_label_hi=f"आयु ({min_age}-{max_age} वर्ष)",
                        required_value=f"{min_age} - {max_age}",
                        actual_value=profile.age,
                        status="FAILED",
                        explanation_en=f"Age {profile.age} is outside eligible bracket ({min_age}-{max_age} yrs).",
                        explanation_hi=f"आयु {profile.age} वर्ष पात्रता सीमा ({min_age}-{max_age} वर्ष) से बाहर है।"
                    ))
                    disqualifiers.append(f"Age {profile.age} outside {min_age}-{max_age} range")
            else:
                breakdown.append(RuleItemCheck(
                    criterion="age",
                    criterion_label_en=f"Age ({min_age}-{max_age} yrs)",
                    criterion_label_hi=f"आयु ({min_age}-{max_age} वर्ष)",
                    required_value=f"{min_age} - {max_age}",
                    actual_value=None,
                    status="UNKNOWN",
                    explanation_en=f"Applicant age not yet confirmed (requires {min_age}-{max_age} yrs).",
                    explanation_hi=f"आवेदक की आयु अभी ज्ञात नहीं है ({min_age}-{max_age} वर्ष आवश्यक)।"
                ))
                missing_criteria.append("age")
            total_evaluable += 1

        # 2. GENDER CHECK
        required_gender = rules.get("gender", "any")
        if required_gender != "any":
            if profile.gender is not None:
                if profile.gender.lower() == required_gender.lower():
                    breakdown.append(RuleItemCheck(
                        criterion="gender",
                        criterion_label_en=f"Gender: {required_gender.capitalize()}",
                        criterion_label_hi=f"लिंग: { 'महिला' if required_gender == 'female' else 'पुरुष' }",
                        required_value=required_gender,
                        actual_value=profile.gender,
                        status="PASSED",
                        explanation_en=f"Gender matches criteria ({required_gender}).",
                        explanation_hi=f"लिंग पात्रता से मेल खाता है ({profile.gender})।"
                    ))
                    passed_count += 1
                else:
                    breakdown.append(RuleItemCheck(
                        criterion="gender",
                        criterion_label_en=f"Gender: {required_gender.capitalize()}",
                        criterion_label_hi=f"लिंग: { 'महिला' if required_gender == 'female' else 'पुरुष' }",
                        required_value=required_gender,
                        actual_value=profile.gender,
                        status="FAILED",
                        explanation_en=f"Scheme specifically reserved for {required_gender} applicants.",
                        explanation_hi=f"यह योजना विशेष रूप से {required_gender} आवेदकों के लिए है।"
                    ))
                    disqualifiers.append(f"Requires {required_gender} applicant")
            else:
                breakdown.append(RuleItemCheck(
                    criterion="gender",
                    criterion_label_en=f"Gender: {required_gender.capitalize()}",
                    criterion_label_hi=f"लिंग: { 'महिला' if required_gender == 'female' else 'पुरुष' }",
                    required_value=required_gender,
                    actual_value=None,
                    status="UNKNOWN",
                    explanation_en=f"Gender confirmation needed (scheme is for {required_gender}).",
                    explanation_hi=f"लिंग की पुष्टि आवश्यक है ({required_gender} के लिए)।"
                ))
                missing_criteria.append("gender")
            total_evaluable += 1

        # 3. OCCUPATION CHECK
        required_occupations = rules.get("occupations", "any")
        if required_occupations != "any":
            total_evaluable += 1
            if profile.occupation is not None:
                prof_occ = profile.occupation.lower()
                # Check if matches any in the list or semantic equivalence
                matched = False
                for req_occ in required_occupations:
                    if req_occ in prof_occ or prof_occ in req_occ:
                        matched = True
                        break
                    # Special synonyms
                    if req_occ == "farmer" and any(k in prof_occ for k in ["kisan", "farming", "agriculture", "khet"]):
                        matched = True
                        break
                    if req_occ in ["street_vendor", "hawker", "thela_wala"] and any(k in prof_occ for k in ["vendor", "hawker", "thela", "rehri", "stall", "rehari"]):
                        matched = True
                        break
                    if req_occ in ["artisan", "carpenter", "blacksmith", "potter", "sculptor", "cobbler", "mason", "tailor"] and any(k in prof_occ for k in ["artisan", "carpenter", "badhai", "lohar", "blacksmith", "kumhar", "mochi", "tailor", "darzi", "mistri", "karigar"]):
                        matched = True
                        break
                    if req_occ in ["unskilled_labour", "manual_worker"] and any(k in prof_occ for k in ["labour", "mazdoor", "worker", "daily wage", "unskilled"]):
                        matched = True
                        break

                if matched:
                    breakdown.append(RuleItemCheck(
                        criterion="occupation",
                        criterion_label_en="Eligible Occupation",
                        criterion_label_hi="पात्र व्यवसाय",
                        required_value=", ".join(required_occupations),
                        actual_value=profile.occupation,
                        status="PASSED",
                        explanation_en=f"Occupation '{profile.occupation}' matches scheme target group.",
                        explanation_hi=f"व्यवसाय '{profile.occupation}' योजना के लक्षित समूह से मेल खाता है।"
                    ))
                    passed_count += 1
                else:
                    breakdown.append(RuleItemCheck(
                        criterion="occupation",
                        criterion_label_en="Eligible Occupation",
                        criterion_label_hi="पात्र व्यवसाय",
                        required_value=", ".join(required_occupations),
                        actual_value=profile.occupation,
                        status="FAILED",
                        explanation_en=f"Occupation '{profile.occupation}' does not qualify for this specialized scheme.",
                        explanation_hi=f"व्यवसाय '{profile.occupation}' इस विशेष योजना के लिए पात्र नहीं है।"
                    ))
                    disqualifiers.append(f"Occupation '{profile.occupation}' not among targeted trades")
            else:
                breakdown.append(RuleItemCheck(
                    criterion="occupation",
                    criterion_label_en="Eligible Occupation",
                    criterion_label_hi="पात्र व्यवसाय",
                    required_value=", ".join(required_occupations),
                    actual_value=None,
                    status="UNKNOWN",
                    explanation_en=f"Occupation needed (target: {', '.join(required_occupations[:3])}).",
                    explanation_hi=f"व्यवसाय की जानकारी आवश्यक है (लक्ष्य: {', '.join(required_occupations[:3])})।"
                ))
                missing_criteria.append("occupation")

        # 4. LAND OWNERSHIP CHECK
        land_required = rules.get("land_required", False)
        if land_required:
            total_evaluable += 1
            if profile.has_land is True:
                breakdown.append(RuleItemCheck(
                    criterion="land_ownership",
                    criterion_label_en="Agricultural Landholding",
                    criterion_label_hi="कृषि भूमि स्वामित्व",
                    required_value="Must own cultivable land",
                    actual_value=f"Yes ({profile.land_ha} ha)" if profile.land_ha else "Yes",
                    status="PASSED",
                    explanation_en="Owns cultivable land as required by scheme.",
                    explanation_hi="योजनानुसार कृषि योग्य भूमि का स्वामित्व उपलब्ध है।"
                ))
                passed_count += 1
            elif profile.has_land is False:
                breakdown.append(RuleItemCheck(
                    criterion="land_ownership",
                    criterion_label_en="Agricultural Landholding",
                    criterion_label_hi="कृषि भूमि स्वामित्व",
                    required_value="Must own cultivable land",
                    actual_value="Landless",
                    status="FAILED",
                    explanation_en="Scheme strictly requires agricultural landownership in applicant's name.",
                    explanation_hi="इस योजना के लिए आवेदक के नाम पर कृषि भूमि होना अनिवार्य है।"
                ))
                disqualifiers.append("Requires cultivable land ownership / भूमि स्वामित्व आवश्यक")
            else:
                breakdown.append(RuleItemCheck(
                    criterion="land_ownership",
                    criterion_label_en="Agricultural Landholding",
                    criterion_label_hi="कृषि भूमि स्वामित्व",
                    required_value="Must own cultivable land",
                    actual_value=None,
                    status="UNKNOWN",
                    explanation_en="Landholding status is unconfirmed.",
                    explanation_hi="भूमि स्वामित्व की स्थिति अभी पुष्ट नहीं है।"
                ))
                missing_criteria.append("has_land")

        # 5. INCOME CEILING & BPL CHECK
        max_income = rules.get("max_income")
        bpl_required = rules.get("bpl_required", False)

        if max_income is not None or bpl_required:
            total_evaluable += 1
            income_ok = True
            income_unknown = False

            if max_income is not None:
                if profile.annual_income is not None:
                    if profile.annual_income > max_income:
                        income_ok = False
                elif profile.bpl_status is True:
                    # BPL implies low income (< 1.5L), so satisfies max_income
                    income_ok = True
                else:
                    income_unknown = True

            if bpl_required:
                if profile.bpl_status is False and (profile.annual_income is not None and profile.annual_income > 200000):
                    income_ok = False
                elif profile.bpl_status is None and profile.annual_income is None:
                    income_unknown = True

            if income_unknown:
                breakdown.append(RuleItemCheck(
                    criterion="income_bpl",
                    criterion_label_en=f"Income Limit (<= ₹{max_income:,})" if max_income else "BPL / Low Income Status",
                    criterion_label_hi=f"आय सीमा (<= ₹{max_income:,})" if max_income else "बीपीएल / कम आय स्थिति",
                    required_value=f"<= ₹{max_income:,}" if max_income else "BPL / Poor household",
                    actual_value=None,
                    status="UNKNOWN",
                    explanation_en="Household income or BPL status needs to be verified.",
                    explanation_hi="पारिवारिक आय या बीपीएल स्थिति का सत्यापन आवश्यक है।"
                ))
                missing_criteria.append("annual_income")
            elif income_ok:
                actual_str = f"₹{int(profile.annual_income):,}" if profile.annual_income is not None else "BPL household"
                breakdown.append(RuleItemCheck(
                    criterion="income_bpl",
                    criterion_label_en=f"Income Limit (<= ₹{max_income:,})" if max_income else "BPL / Low Income Status",
                    criterion_label_hi=f"आय सीमा (<= ₹{max_income:,})" if max_income else "बीपीएल / कम आय स्थिति",
                    required_value=f"<= ₹{max_income:,}" if max_income else "BPL / Poor household",
                    actual_value=actual_str,
                    status="PASSED",
                    explanation_en=f"Income ({actual_str}) qualifies within poverty/economic criteria.",
                    explanation_hi=f"आय ({actual_str}) आर्थिक पात्रता के अनुकूल है।"
                ))
                passed_count += 1
            else:
                actual_str = f"₹{int(profile.annual_income):,}" if profile.annual_income is not None else "Above threshold"
                breakdown.append(RuleItemCheck(
                    criterion="income_bpl",
                    criterion_label_en=f"Income Limit (<= ₹{max_income:,})" if max_income else "BPL / Low Income Status",
                    criterion_label_hi=f"आय सीमा (<= ₹{max_income:,})" if max_income else "बीपीएल / कम आय स्थिति",
                    required_value=f"<= ₹{max_income:,}" if max_income else "BPL / Poor household",
                    actual_value=actual_str,
                    status="FAILED",
                    explanation_en=f"Income ({actual_str}) exceeds scheme limit.",
                    explanation_hi=f"आय ({actual_str}) योजना की निर्धारित सीमा से अधिक है।"
                ))
                disqualifiers.append(f"Income ({actual_str}) exceeds threshold / आय सीमा से अधिक")

        # 6. AREA (RURAL / URBAN) CHECK
        req_area = rules.get("area", "any")
        if req_area != "any":
            total_evaluable += 1
            if profile.area_type is not None:
                if profile.area_type.lower() == req_area.lower():
                    breakdown.append(RuleItemCheck(
                        criterion="area",
                        criterion_label_en=f"Area: {req_area.capitalize()}",
                        criterion_label_hi=f"क्षेत्र: { 'ग्रामीण' if req_area == 'rural' else 'शहरी' }",
                        required_value=req_area,
                        actual_value=profile.area_type,
                        status="PASSED",
                        explanation_en=f"Resides in {req_area} area as required.",
                        explanation_hi=f"{req_area} क्षेत्र के निवासी हैं, शर्त पूरी होती है।"
                    ))
                    passed_count += 1
                else:
                    breakdown.append(RuleItemCheck(
                        criterion="area",
                        criterion_label_en=f"Area: {req_area.capitalize()}",
                        criterion_label_hi=f"क्षेत्र: { 'ग्रामीण' if req_area == 'rural' else 'शहरी' }",
                        required_value=req_area,
                        actual_value=profile.area_type,
                        status="FAILED",
                        explanation_en=f"Scheme applies only to {req_area} areas (caller is {profile.area_type}).",
                        explanation_hi=f"यह योजना केवल {req_area} क्षेत्रों के लिए है (आवेदक {profile.area_type} क्षेत्र से हैं)।"
                    ))
                    disqualifiers.append(f"Only for {req_area} areas")
            else:
                breakdown.append(RuleItemCheck(
                    criterion="area",
                    criterion_label_en=f"Area: {req_area.capitalize()}",
                    criterion_label_hi=f"क्षेत्र: { 'ग्रामीण' if req_area == 'rural' else 'शहरी' }",
                    required_value=req_area,
                    actual_value=None,
                    status="UNKNOWN",
                    explanation_en=f"Rural or Urban residence status needed ({req_area} required).",
                    explanation_hi=f"ग्रामीण या शहरी निवास की जानकारी आवश्यक है ({req_area} क्षेत्र)।"
                ))
                missing_criteria.append("area_type")

        # 7. HOUSING TYPE CHECK (e.g. for PMAY-G)
        req_house = rules.get("house_type", "any")
        if req_house == "kutcha_or_homeless":
            total_evaluable += 1
            if profile.house_type is not None:
                if profile.house_type in ["kutcha", "homeless", "dilapidated"]:
                    breakdown.append(RuleItemCheck(
                        criterion="house_type",
                        criterion_label_en="Kutcha House / Homeless",
                        criterion_label_hi="कच्चा मकान / बेघर",
                        required_value="Kutcha or no pucca house",
                        actual_value=profile.house_type,
                        status="PASSED",
                        explanation_en=f"Living in {profile.house_type} house qualifies for housing assistance.",
                        explanation_hi=f"{profile.house_type} मकान में रहने के कारण आवास सहायता हेतु पात्र हैं।"
                    ))
                    passed_count += 1
                else:
                    breakdown.append(RuleItemCheck(
                        criterion="house_type",
                        criterion_label_en="Kutcha House / Homeless",
                        criterion_label_hi="कच्चा मकान / बेघर",
                        required_value="Kutcha or no pucca house",
                        actual_value=profile.house_type,
                        status="FAILED",
                        explanation_en="Owners of pucca (permanent) houses are not eligible for PMAY.",
                        explanation_hi="पक्के मकान के मालिक पीएम आवास योजना के लिए पात्र नहीं हैं।"
                    ))
                    disqualifiers.append("Already owns a pucca house / पहले से पक्का मकान है")
            else:
                breakdown.append(RuleItemCheck(
                    criterion="house_type",
                    criterion_label_en="Kutcha House / Homeless",
                    criterion_label_hi="कच्चा मकान / बेघर",
                    required_value="Kutcha or no pucca house",
                    actual_value=None,
                    status="UNKNOWN",
                    explanation_en="Housing status (kutcha/pucca) needs confirmation.",
                    explanation_hi="मकान के प्रकार (कच्चा/पक्का) की पुष्टि आवश्यक है।"
                ))
                missing_criteria.append("house_type")

        # 8. EXCLUSIONS (Taxpayer, Govt Employee, Existing LPG)
        exclusions = rules.get("exclusions", [])
        if "income_tax_payer" in exclusions:
            if profile.is_tax_payer is True:
                disqualifiers.append("Income Tax Payer exclusion / आयकर दाता अपात्र")
                breakdown.append(RuleItemCheck(
                    criterion="exclusion_tax",
                    criterion_label_en="Non-Tax Payer",
                    criterion_label_hi="गैर-आयकर दाता",
                    required_value="Must not pay income tax",
                    actual_value="Tax Payer",
                    status="FAILED",
                    explanation_en="Income tax payers are statutory exclusions for this welfare scheme.",
                    explanation_hi="आयकर दाता इस कल्याणकारी योजना के अंतर्गत शामिल नहीं हैं।"
                ))
            elif profile.is_tax_payer is False:
                passed_count += 1

        if "govt_employee" in exclusions:
            if profile.is_govt_employee is True:
                disqualifiers.append("Government Employee exclusion / सरकारी कर्मचारी अपात्र")
                breakdown.append(RuleItemCheck(
                    criterion="exclusion_govt",
                    criterion_label_en="Non-Govt Employee",
                    criterion_label_hi="गैर-सरकारी कर्मचारी",
                    required_value="No regular govt job",
                    actual_value="Govt Employee",
                    status="FAILED",
                    explanation_en="Government employees are excluded from this benefit.",
                    explanation_hi="सरकारी कर्मचारी इस लाभ से अपात्र हैं।"
                ))
            elif profile.is_govt_employee is False:
                passed_count += 1

        if "existing_lpg_connection" in exclusions:
            if profile.has_existing_lpg is True:
                disqualifiers.append("Already has LPG connection / पहले से एलपीजी गैस कनेक्शन है")
                breakdown.append(RuleItemCheck(
                    criterion="exclusion_lpg",
                    criterion_label_en="No Prior LPG Connection",
                    criterion_label_hi="पहले से गैस कनेक्शन न हो",
                    required_value="No active LPG in household",
                    actual_value="Has LPG",
                    status="FAILED",
                    explanation_en="Households with existing LPG connection cannot get Ujjwala 2.0 grant.",
                    explanation_hi="जिन परिवारों के पास पहले से एलपीजी कनेक्शन है, वे उज्ज्वला के पात्र नहीं हैं।"
                ))
            elif profile.has_existing_lpg is False:
                passed_count += 1

        # 9. SPECIAL CONDITIONS (e.g. pregnant/lactating for PMMVY)
        spec_cond = rules.get("special_condition")
        if spec_cond == "pregnant_or_lactating":
            total_evaluable += 1
            if profile.is_pregnant_or_lactating is True:
                passed_count += 1
                breakdown.append(RuleItemCheck(
                    criterion="special_maternity",
                    criterion_label_en="Pregnant / Lactating Mother",
                    criterion_label_hi="गर्भवती अथवा धात्री महिला",
                    required_value="Pregnant or nursing",
                    actual_value="Yes",
                    status="PASSED",
                    explanation_en="Qualifies as pregnant/nursing mother.",
                    explanation_hi="गर्भवती/धात्री महिला होने के कारण पात्र हैं।"
                ))
            elif profile.is_pregnant_or_lactating is False:
                disqualifiers.append("Not pregnant or nursing / गर्भवती या धात्री महिला नहीं")
                breakdown.append(RuleItemCheck(
                    criterion="special_maternity",
                    criterion_label_en="Pregnant / Lactating Mother",
                    criterion_label_hi="गर्भवती अथवा धात्री महिला",
                    required_value="Pregnant or nursing",
                    actual_value="No",
                    status="FAILED",
                    explanation_en="Scheme is exclusively for pregnant/lactating mothers.",
                    explanation_hi="यह योजना केवल गर्भवती/धात्री महिलाओं के लिए है।"
                ))
            else:
                missing_criteria.append("is_pregnant_or_lactating")
                breakdown.append(RuleItemCheck(
                    criterion="special_maternity",
                    criterion_label_en="Pregnant / Lactating Mother",
                    criterion_label_hi="गर्भवती अथवा धात्री महिला",
                    required_value="Pregnant or nursing",
                    actual_value=None,
                    status="UNKNOWN",
                    explanation_en="Information on pregnancy / recent childbirth needed.",
                    explanation_hi="गर्भावस्था अथवा हालिया प्रसव की जानकारी आवश्यक है।"
                ))

        # Overall Status Determination
        if len(disqualifiers) > 0:
            status = "NOT_ELIGIBLE"
            match_score = 0.0
        elif len(missing_criteria) == 0 and passed_count > 0:
            status = "ELIGIBLE"
            match_score = 1.0
        elif passed_count > 0 and len(missing_criteria) <= 2:
            status = "LIKELY_ELIGIBLE"
            match_score = round(passed_count / max(1, total_evaluable), 2)
        else:
            status = "UNKNOWN"
            match_score = round(passed_count / max(1, total_evaluable), 2)

        return SchemeEligibility(
            scheme_id=scheme["id"],
            name_en=scheme["name_en"],
            name_hi=scheme["name_hi"],
            category=scheme["category"],
            status=status,
            match_score=match_score,
            benefits_en=scheme["benefits_en"],
            benefits_hi=scheme["benefits_hi"],
            criteria_breakdown=breakdown,
            missing_criteria=missing_criteria,
            disqualifiers=disqualifiers,
            required_documents_en=scheme["required_documents_en"],
            required_documents_hi=scheme["required_documents_hi"],
            application_steps_en=scheme["application_steps_en"],
            application_steps_hi=scheme["application_steps_hi"],
            portal_url=scheme["portal_url"]
        )
