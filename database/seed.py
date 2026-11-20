"""
Database initialization and seeding script.
Populates SQLite with official schemes from data/schemes.json and demo accounts.
"""
import os
import json
from database.connection import engine, SessionLocal, Base
from database.models import User, GovernmentScheme, RequiredDocument, CitizenProfile


def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed Schemes if empty
        existing_schemes_count = db.query(GovernmentScheme).count()
        if existing_schemes_count == 0:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            schemes_file = os.path.join(base_dir, "data", "schemes.json")
            with open(schemes_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for s in data.get("schemes", []):
                scheme_row = GovernmentScheme(
                    id=s["id"],
                    code=s.get("code", s["id"].upper()),
                    name_en=s["name_en"],
                    name_hi=s["name_hi"],
                    ministry_en=s.get("ministry_en", "Government of India"),
                    ministry_hi=s.get("ministry_hi", "भारत सरकार"),
                    level=s.get("level", "Central"),
                    category=s.get("category", "General"),
                    target_beneficiaries_en=s.get("target_beneficiaries_en", ""),
                    target_beneficiaries_hi=s.get("target_beneficiaries_hi", ""),
                    brief_en=s.get("brief_en", ""),
                    brief_hi=s.get("brief_hi", ""),
                    benefits_en=s.get("benefits_en", ""),
                    benefits_hi=s.get("benefits_hi", ""),
                    rules_json=json.dumps(s.get("rules", {}), ensure_ascii=False),
                    required_docs_json=json.dumps(s.get("required_documents_en", []), ensure_ascii=False),
                    application_steps_en=s.get("application_steps_en", ""),
                    application_steps_hi=s.get("application_steps_hi", ""),
                    portal_url=s.get("portal_url", ""),
                    source_url=s.get("source_url", ""),
                    verified_date=s.get("verified_date", "2024-11-15")
                )
                db.add(scheme_row)

                # Add individual documents
                docs_en = s.get("required_documents_en", [])
                docs_hi = s.get("required_documents_hi", [])
                for i in range(len(docs_en)):
                    doc_hi = docs_hi[i] if i < len(docs_hi) else docs_en[i]
                    doc_row = RequiredDocument(
                        scheme_id=s["id"],
                        document_name_en=docs_en[i],
                        document_name_hi=doc_hi,
                        is_mandatory=True,
                        purpose="Identity & Eligibility Verification"
                    )
                    db.add(doc_row)

            db.commit()
            print("Successfully seeded 12 Government Schemes into Database!")

        # 2. Seed Demo Users if not present
        if db.query(User).count() == 0:
            demo_citizen = User(
                name="Ramesh Kumar (Demo Citizen)",
                email="citizen@suvidha.gov.in",
                phone="9876543210",
                hashed_password="demo_hashed_password",
                role="citizen"
            )
            demo_judge = User(
                name="SIH Evaluation Judge",
                email="judge@sih.gov.in",
                phone="9876543211",
                hashed_password="judge_hashed_password",
                role="judge"
            )
            demo_admin = User(
                name="Ministry Admin",
                email="admin@suvidha.gov.in",
                phone="9876543212",
                hashed_password="admin_hashed_password",
                role="admin"
            )
            db.add_all([demo_citizen, demo_judge, demo_admin])
            db.commit()

            # Seed sample profile
            sample_profile = CitizenProfile(
                user_id=demo_citizen.id,
                age=45,
                gender="male",
                occupation="farmer",
                annual_income=80000.0,
                state="Uttar Pradesh",
                district="Varanasi",
                caste_category="OBC",
                area_type="rural",
                house_type="kutcha",
                has_land=True,
                land_ha=1.0,
                bpl_status=True,
                is_tax_payer=False,
                is_govt_employee=False
            )
            db.add(sample_profile)
            db.commit()
            print("Successfully seeded Demo Users and Citizen Profiles!")

    except Exception as e:
        db.rollback()
        print(f"Error during database seed: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
