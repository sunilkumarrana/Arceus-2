"""
Personalized Document Checklist Generator.
Aggregates and deduplicates required documents across eligible schemes with actionable guidance.
"""
from typing import List, Dict, Any
from engine.rules_engine import SchemeRulesEngine


class DocumentChecklistGenerator:
    def __init__(self, rules_engine: SchemeRulesEngine):
        self.rules_engine = rules_engine

        # Document metadata guide: category, where to get it, tips
        self.doc_registry = {
            "aadhaar": {
                "category_en": "Identity Proof",
                "category_hi": "पहचान प्रमाण",
                "authority_en": "UIDAI / Nearest Aadhaar Seva Kendra",
                "authority_hi": "यूआईडीएआई / आधार सेवा केंद्र",
                "tip_en": "Ensure mobile number is linked for instant OTP verification.",
                "tip_hi": "सुनिश्चित करें कि त्वरित ओटीपी सत्यापन हेतु मोबाइल नंबर जुड़ा हो।"
            },
            "bank": {
                "category_en": "Banking & Direct Benefit Transfer",
                "category_hi": "बैंकिंग व प्रत्यक्ष लाभ अंतरण",
                "authority_en": "Bank Branch / Post Office (IPPB)",
                "authority_hi": "बैंक शाखा / डाकघर (आईपीपीबी)",
                "tip_en": "Account must have NPCI Aadhaar seeding active to receive DBT grants.",
                "tip_hi": "डीबीटी अनुदान प्राप्त करने के लिए एनपीसीआई आधार सीडिंग अनिवार्य है।"
            },
            "ration": {
                "category_en": "Family & Poverty Category Proof",
                "category_hi": "पारिवारिक व गरीबी श्रेणी प्रमाण",
                "authority_en": "Food & Civil Supplies Dept / Tehsil",
                "authority_hi": "खाद्य एवं नागरिक आपूर्ति विभाग / तहसील",
                "tip_en": "Carry original ration card showing all dependent members.",
                "tip_hi": "परिवार के सभी सदस्यों का विवरण दर्शाने वाला मूल राशन कार्ड साथ रखें।"
            },
            "land": {
                "category_en": "Land & Property Record",
                "category_hi": "भूमि व संपत्ति अभिलेख",
                "authority_en": "Revenue Dept / Bhulekh Portal / Patwari",
                "authority_hi": "राजस्व विभाग / भूलेख पोर्टल / लेखपाल/पटवारी",
                "tip_en": "Recent Khatauni / Khasra copy certified within the last 6 months.",
                "tip_hi": "विगत 6 महीने के भीतर प्रमाणित खतौनी/खसरा प्रति।"
            },
            "mcp": {
                "category_en": "Health & Maternity Record",
                "category_hi": "स्वास्थ्य व मातृत्व रिकॉर्ड",
                "authority_en": "Local Anganwadi Centre (AWC) / Primary Health Centre (PHC)",
                "authority_hi": "स्थानीय आंगनवाड़ी केंद्र / प्राथमिक स्वास्थ्य केंद्र",
                "tip_en": "Mother and Child Protection (MCP) card with early ANC registration stamp.",
                "tip_hi": "समय पर प्रसवपूर्व जांच (ANC) मुहर लगा हुआ एमसीपी कार्ड।"
            },
            "vending": {
                "category_en": "Trade / Occupational Proof",
                "category_hi": "व्यापार / व्यावसायिक प्रमाण",
                "authority_en": "Town Vending Committee (TVC) / Municipal Corporation",
                "authority_hi": "टाउन वेंडिंग कमेटी / नगर निगम",
                "tip_en": "Letter of Recommendation (LoR) can be generated if vending certificate is pending.",
                "tip_hi": "यदि वेंडिंग प्रमाणपत्र लंबित है तो अनुशंसा पत्र (LoR) बनवाया जा सकता है।"
            }
        }

    def generate_checklist(self, eligible_scheme_ids: List[str]) -> Dict[str, Any]:
        """Generates a structured, unified document checklist for all recommended schemes."""
        schemes_data = {s["id"]: s for s in self.rules_engine.schemes_data}
        selected = [schemes_data[sid] for sid in eligible_scheme_ids if sid in schemes_data]

        unified_docs: Dict[str, Dict[str, Any]] = {}

        for s in selected:
            docs_en = s.get("required_documents_en", [])
            docs_hi = s.get("required_documents_hi", [])

            for i in range(len(docs_en)):
                doc_en = docs_en[i]
                doc_hi = docs_hi[i] if i < len(docs_hi) else doc_en

                # Determine key category
                key = "general"
                t_low = doc_en.lower()
                if "aadhaar" in t_low:
                    key = "aadhaar"
                elif "bank" in t_low or "passbook" in t_low or "ifsc" in t_low:
                    key = "bank"
                elif "ration" in t_low or "bpl" in t_low or "secc" in t_low:
                    key = "ration"
                elif "land" in t_low or "khatauni" in t_low or "khasra" in t_low:
                    key = "land"
                elif "mcp" in t_low or "mother" in t_low or "birth certificate" in t_low:
                    key = "mcp"
                elif "vending" in t_low or "lor" in t_low:
                    key = "vending"

                meta = self.doc_registry.get(key, {
                    "category_en": "Supporting Verification",
                    "category_hi": "सहायक सत्यापन",
                    "authority_en": "Concerned Authority",
                    "authority_hi": "संबंधित विभाग",
                    "tip_en": "Keep original and self-attested copies ready.",
                    "tip_hi": "मूल प्रति और स्व-प्रमाणित फोटोकॉपी तैयार रखें।"
                })

                doc_id = f"doc_{key}_{hash(doc_en) % 10000}"
                if doc_id not in unified_docs:
                    unified_docs[doc_id] = {
                        "id": doc_id,
                        "title_en": doc_en,
                        "title_hi": doc_hi,
                        "category_en": meta["category_en"],
                        "category_hi": meta["category_hi"],
                        "issuing_authority_en": meta["authority_en"],
                        "issuing_authority_hi": meta["authority_hi"],
                        "pro_tip_en": meta["tip_en"],
                        "pro_tip_hi": meta["tip_hi"],
                        "needed_for_schemes": [s["name_en"]],
                        "status": "pending"  # "pending", "ready"
                    }
                else:
                    if s["name_en"] not in unified_docs[doc_id]["needed_for_schemes"]:
                        unified_docs[doc_id]["needed_for_schemes"].append(s["name_en"])

        items = list(unified_docs.values())
        return {
            "total_documents_required": len(items),
            "schemes_covered": [s["name_en"] for s in selected],
            "documents": items
        }
