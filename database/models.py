"""
SQLAlchemy ORM models for the Voice-First Welfare Scheme platform.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    role = Column(String(20), default="citizen")  # "citizen", "admin", "judge"
    created_at = Column(DateTime, default=datetime.utcnow)

    profiles = relationship("CitizenProfile", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("ConversationSession", back_populates="user")
    saved_schemes = relationship("SavedScheme", back_populates="user")


class CitizenProfile(Base):
    __tablename__ = "citizen_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)  # male, female, other
    occupation = Column(String(100), nullable=True)
    annual_income = Column(Float, nullable=True)
    state = Column(String(100), default="All-India")
    district = Column(String(100), nullable=True)
    caste_category = Column(String(50), nullable=True)  # General, OBC, SC, ST
    is_disabled = Column(Boolean, default=False)
    area_type = Column(String(20), nullable=True)  # rural, urban
    house_type = Column(String(50), nullable=True)  # kutcha, pucca, homeless
    has_land = Column(Boolean, nullable=True)
    land_ha = Column(Float, nullable=True)
    bpl_status = Column(Boolean, nullable=True)
    is_tax_payer = Column(Boolean, nullable=True)
    is_govt_employee = Column(Boolean, nullable=True)
    has_existing_lpg = Column(Boolean, nullable=True)
    has_girl_child_under_10 = Column(Boolean, nullable=True)
    is_pregnant_or_lactating = Column(Boolean, nullable=True)
    has_existing_pension = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profiles")


class GovernmentScheme(Base):
    __tablename__ = "government_schemes"

    id = Column(String(100), primary_key=True, index=True)  # e.g. "pm_kisan"
    code = Column(String(50), index=True)
    name_en = Column(String(255), nullable=False)
    name_hi = Column(String(255), nullable=False)
    ministry_en = Column(String(255))
    ministry_hi = Column(String(255))
    level = Column(String(50), default="Central")  # Central, State
    category = Column(String(100), index=True)
    target_beneficiaries_en = Column(Text)
    target_beneficiaries_hi = Column(Text)
    brief_en = Column(Text)
    brief_hi = Column(Text)
    benefits_en = Column(Text)
    benefits_hi = Column(Text)
    rules_json = Column(Text)  # JSON-encoded criteria
    required_docs_json = Column(Text)  # JSON array
    application_steps_en = Column(Text)
    application_steps_hi = Column(Text)
    portal_url = Column(String(255))
    source_url = Column(String(255))
    verified_date = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("RequiredDocument", back_populates="scheme", cascade="all, delete-orphan")


class RequiredDocument(Base):
    __tablename__ = "required_documents"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(String(100), ForeignKey("government_schemes.id"))
    document_name_en = Column(String(255), nullable=False)
    document_name_hi = Column(String(255), nullable=False)
    is_mandatory = Column(Boolean, default=True)
    purpose = Column(String(255), nullable=True)

    scheme = relationship("GovernmentScheme", back_populates="documents")


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(String(100), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    language = Column(String(10), default="hi")
    state = Column(String(50), default="GREETING")
    questions_asked_count = Column(Integer, default=0)
    profile_data_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")
    evaluations = relationship("EligibilityEvaluation", back_populates="session", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), ForeignKey("conversation_sessions.id"))
    role = Column(String(20))  # "user" or "agent"
    text_content = Column(Text, nullable=False)
    spoken_text = Column(Text, nullable=True)
    language = Column(String(10), default="hi")
    extracted_slots_json = Column(Text, default="{}")
    state = Column(String(50), default="INQUIRING")
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ConversationSession", back_populates="messages")


class EligibilityEvaluation(Base):
    __tablename__ = "eligibility_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), ForeignKey("conversation_sessions.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scheme_id = Column(String(100), ForeignKey("government_schemes.id"))
    status = Column(String(50))  # ELIGIBLE, LIKELY_ELIGIBLE, NOT_ELIGIBLE, UNKNOWN
    match_score = Column(Float, default=0.0)
    breakdown_json = Column(Text)  # Detailed rule checklist
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ConversationSession", back_populates="evaluations")


class SavedScheme(Base):
    __tablename__ = "saved_schemes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    scheme_id = Column(String(100), ForeignKey("government_schemes.id"))
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="interested")  # "interested", "applied", "benefited"
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="saved_schemes")
