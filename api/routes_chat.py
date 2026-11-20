"""
Conversation & Voice Processing API Routes.
Coordinates multi-turn voice/text chat, language detection, and session persistence.
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import ConversationSession, ConversationMessage, User
from engine.agent_orchestrator import SchemeVoiceAgent
import os
import json

router = APIRouter(prefix="/api/chat", tags=["Conversation & Voice"])

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
schemes_path = os.path.join(base_dir, "data", "schemes.json")

# In-memory fast agent cache: session_id -> SchemeVoiceAgent
agent_sessions: Dict[str, SchemeVoiceAgent] = {}


def get_agent(session_id: str, lang: str = "hi") -> SchemeVoiceAgent:
    if session_id not in agent_sessions:
        agent = SchemeVoiceAgent(schemes_path)
        agent.reset(initial_language=lang)
        agent_sessions[session_id] = agent
    return agent_sessions[session_id]


class ChatTurnRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_session"
    language: Optional[str] = None  # "hi" or "en" or auto-detect
    user_id: Optional[int] = None


class ResetSessionRequest(BaseModel):
    session_id: Optional[str] = "default_session"
    language: Optional[str] = "hi"


@router.post("")
def chat_turn(req: ChatTurnRequest, db: Session = Depends(get_db)):
    """
    Processes a citizen's voice transcription or text message.
    Updates the session, runs NLU and rules reasoning, and returns spoken and visual responses.
    """
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    agent = get_agent(req.session_id, req.language or "hi")
    resp = agent.process_utterance(req.message.strip(), forced_lang=req.language)

    # Persist message to database if DB session available
    try:
        session_record = db.query(ConversationSession).filter(ConversationSession.id == req.session_id).first()
        if not session_record:
            session_record = ConversationSession(
                id=req.session_id,
                user_id=req.user_id,
                language=resp.current_language,
                state=resp.state,
                questions_asked_count=resp.questions_asked_count,
                profile_data_json=json.dumps(resp.caller_profile.model_dump(), ensure_ascii=False)
            )
            db.add(session_record)
        else:
            session_record.language = resp.current_language
            session_record.state = resp.state
            session_record.questions_asked_count = resp.questions_asked_count
            session_record.profile_data_json = json.dumps(resp.caller_profile.model_dump(), ensure_ascii=False)

        # Record User message
        msg_user = ConversationMessage(
            session_id=req.session_id,
            role="user",
            text_content=req.message.strip(),
            language=resp.current_language,
            extracted_slots_json=json.dumps(resp.slots_extracted_this_turn, ensure_ascii=False),
            state=resp.state
        )
        # Record Agent message
        msg_agent = ConversationMessage(
            session_id=req.session_id,
            role="agent",
            text_content=resp.spoken_text,
            spoken_text=resp.spoken_text,
            language=resp.current_language,
            state=resp.state
        )
        db.add_all([msg_user, msg_agent])
        db.commit()
    except Exception as e:
        db.rollback()
        # Fallback continues without database failure blocking the voice agent

    return resp


@router.post("/reset")
def reset_conversation(req: ResetSessionRequest, db: Session = Depends(get_db)):
    """Resets the conversation and citizen slots for a new caller."""
    agent = get_agent(req.session_id, req.language or "hi")
    agent.reset(initial_language=req.language or "hi")

    try:
        session_record = db.query(ConversationSession).filter(ConversationSession.id == req.session_id).first()
        if session_record:
            session_record.state = "GREETING"
            session_record.questions_asked_count = 0
            session_record.profile_data_json = "{}"
            db.commit()
    except Exception:
        db.rollback()

    greeting_hi = "नमस्ते! मैं सुविधा वाणी हूँ, आपका सरकारी योजना सहायक। आप बोलकर या लिखकर अपनी जानकारी बता सकते हैं। आप क्या काम करते हैं और आपकी क्या आवश्यकता है?"
    greeting_en = "Namaste! I am Suvidha Vani, your voice assistant for Government Schemes. Tell me about yourself or what support you are looking for."

    spoken = greeting_hi if (req.language or "hi") == "hi" else greeting_en

    return {
        "status": "reset_successful",
        "session_id": req.session_id,
        "language": req.language or "hi",
        "greeting_message": spoken,
        "initial_state": "GREETING"
    }


@router.get("/history/{session_id}")
def get_history(session_id: str, db: Session = Depends(get_db)):
    """Retrieves full conversation messages for the given session."""
    agent = agent_sessions.get(session_id)
    in_memory_history = agent.history if agent else []

    db_messages = db.query(ConversationMessage).filter(ConversationMessage.session_id == session_id).order_by(ConversationMessage.created_at.asc()).all()

    return {
        "session_id": session_id,
        "history_count": len(db_messages) if db_messages else len(in_memory_history),
        "messages": [
            {
                "role": m.role,
                "text": m.text_content,
                "language": m.language,
                "state": m.state,
                "created_at": m.created_at.strftime("%H:%M:%S")
            }
            for m in db_messages
        ] if db_messages else in_memory_history
    }
