"""
Authentication and Role Management Routes.
Supports Citizen, Admin, and Judge roles with Instant Demo Access.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import User, CitizenProfile

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    role: Optional[str] = "citizen"


class LoginRequest(BaseModel):
    phone: str
    password: Optional[str] = "demo"


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.phone == req.phone).first()
    if existing:
        return {
            "status": "existing_user",
            "user": {
                "id": existing.id,
                "name": existing.name,
                "phone": existing.phone,
                "role": existing.role
            }
        }

    new_user = User(
        name=req.name,
        phone=req.phone,
        email=req.email,
        role=req.role or "citizen"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create empty profile
    profile = CitizenProfile(user_id=new_user.id)
    db.add(profile)
    db.commit()

    return {
        "status": "registered",
        "user": {
            "id": new_user.id,
            "name": new_user.name,
            "phone": new_user.phone,
            "role": new_user.role
        }
    }


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        # Create demo user on the fly if not found
        user = User(
            name=f"Citizen ({req.phone[-4:]})",
            phone=req.phone,
            role="citizen"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "status": "success",
        "token": f"jwt_mock_token_for_{user.id}",
        "user": {
            "id": user.id,
            "name": user.name,
            "phone": user.phone,
            "email": user.email,
            "role": user.role
        }
    }


@router.get("/demo-login/{role}")
def demo_login(role: str, db: Session = Depends(get_db)):
    """1-Click Instant Login for Judges, Citizens, and Admins during SIH evaluation."""
    target_role = role.lower()
    if target_role not in ["citizen", "judge", "admin"]:
        target_role = "citizen"

    user = db.query(User).filter(User.role == target_role).first()
    if not user:
        user = User(
            name=f"SIH Demo {target_role.capitalize()}",
            phone="9999988888",
            email=f"{target_role}@sih.gov.in",
            role=target_role
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "status": "success",
        "token": f"jwt_demo_{target_role}_token",
        "user": {
            "id": user.id,
            "name": user.name,
            "phone": user.phone,
            "email": user.email,
            "role": user.role
        }
    }
