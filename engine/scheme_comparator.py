"""
Scheme Comparison Engine.
Provides side-by-side comparative analysis of 2 to 3 government welfare schemes.
"""
from typing import List, Dict, Any, Optional
from engine.rules_engine import SchemeRulesEngine


class SchemeComparator:
    def __init__(self, rules_engine: SchemeRulesEngine):
        self.rules_engine = rules_engine

    def compare_schemes(self, scheme_ids: List[str]) -> Dict[str, Any]:
        """Compares given schemes side by side across standardized dimensions."""
        schemes_data = {s["id"]: s for s in self.rules_engine.schemes_data}
        selected = [schemes_data[sid] for sid in scheme_ids if sid in schemes_data]

        if not selected:
            return {"error": "No valid schemes selected for comparison"}

        comparison_matrix = {
            "schemes": [],
            "dimensions": [
                {
                    "key": "category",
                    "label_en": "Domain / Category",
                    "label_hi": "श्रेणी / कार्यक्षेत्र"
                },
                {
                    "key": "ministry",
                    "label_en": "Nodal Ministry / Department",
                    "label_hi": "नोडल मंत्रालय / विभाग"
                },
                {
                    "key": "benefits",
                    "label_en": "Financial / Material Benefits",
                    "label_hi": "वित्तीय / भौतिक लाभ"
                },
                {
                    "key": "target_beneficiaries",
                    "label_en": "Target Beneficiaries",
                    "label_hi": "लक्षित लाभार्थी"
                },
                {
                    "key": "age_limit",
                    "label_en": "Eligible Age Bracket",
                    "label_hi": "पात्र आयु सीमा"
                },
                {
                    "key": "income_limit",
                    "label_en": "Income / BPL Criteria",
                    "label_hi": "आय / बीपीएल शर्त"
                },
                {
                    "key": "occupation_scope",
                    "label_en": "Target Occupations",
                    "label_hi": "लक्षित व्यवसाय"
                },
                {
                    "key": "application_mode",
                    "label_en": "Application Mode & Portal",
                    "label_hi": "आवेदन प्रक्रिया व पोर्टल"
                }
            ],
            "values": {}
        }

        for s in selected:
            rules = s.get("rules", {})
            min_age = rules.get("min_age", 0)
            max_age = rules.get("max_age", 120)
            max_inc = rules.get("max_income")
            bpl = rules.get("bpl_required", False)
            occs = rules.get("occupations", "any")

            age_str_en = f"{min_age} to {max_age} years" if max_age < 120 else f"{min_age}+ years"
            age_str_hi = f"{min_age} से {max_age} वर्ष" if max_age < 120 else f"{min_age}+ वर्ष"

            inc_str_en = f"Up to ₹{max_inc:,}/year" if max_inc else ("BPL Required" if bpl else "No strict income cap")
            inc_str_hi = f"₹{max_inc:,}/वर्ष तक" if max_inc else ("बीपीएल अनिवार्य" if bpl else "कोई आय सीमा नहीं")

            occ_str_en = ", ".join(occs) if isinstance(occs, list) else "Open to all occupations"
            occ_str_hi = ", ".join(occs) if isinstance(occs, list) else "सभी व्यवसायों के लिए"

            scheme_summary = {
                "id": s["id"],
                "code": s.get("code", s["id"].upper()),
                "name_en": s["name_en"],
                "name_hi": s["name_hi"],
                "portal_url": s["portal_url"]
            }
            comparison_matrix["schemes"].append(scheme_summary)

            comparison_matrix["values"][s["id"]] = {
                "category": {"en": s.get("category", "General"), "hi": s.get("category", "सामान्य")},
                "ministry": {"en": s.get("ministry_en", "GoI"), "hi": s.get("ministry_hi", "भारत सरकार")},
                "benefits": {"en": s.get("benefits_en", ""), "hi": s.get("benefits_hi", "")},
                "target_beneficiaries": {"en": s.get("target_beneficiaries_en", ""), "hi": s.get("target_beneficiaries_hi", "")},
                "age_limit": {"en": age_str_en, "hi": age_str_hi},
                "income_limit": {"en": inc_str_en, "hi": inc_str_hi},
                "occupation_scope": {"en": occ_str_en, "hi": occ_str_hi},
                "application_mode": {"en": s.get("application_steps_en", "")[:120] + "...", "hi": s.get("application_steps_hi", "")[:120] + "..."}
            }

        return comparison_matrix
