"""
Auth router — register, login, me, change password.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.core.database import get_db
from app.core.auth import hash_password, verify_password, create_access_token, get_current_doctor
from app.models.db_models import Doctor, AuditLog
import uuid

auth_router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Schemas ──────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    doctor_id:      str           # e.g. DR-001
    email:          str
    full_name:      str
    specialisation: Optional[str] = None
    password:       str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    doctor_id:    str
    full_name:    str
    email:        str
    specialisation: Optional[str]


# ─── Register ─────────────────────────────────────────────────────

@auth_router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create a new doctor account."""
    # Check duplicate email or doctor_id
    existing = await db.execute(
        select(Doctor).where(
            (Doctor.email == req.email) | (Doctor.doctor_id == req.doctor_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="A doctor with this email or ID already exists"
        )

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    doctor = Doctor(
        id=str(uuid.uuid4()),
        doctor_id=req.doctor_id,
        email=req.email,
        full_name=req.full_name,
        specialisation=req.specialisation,
        hashed_password=hash_password(req.password),
        is_active=True,
    )
    db.add(doctor)
    db.add(AuditLog(
        session_id=None,
        doctor_id=req.doctor_id,
        action="DOCTOR_REGISTERED",
        meta_data={"email": req.email, "full_name": req.full_name},
    ))
    await db.commit()

    token = create_access_token(doctor.doctor_id, doctor.email)
    return TokenResponse(
        access_token=token,
        doctor_id=doctor.doctor_id,
        full_name=doctor.full_name,
        email=doctor.email,
        specialisation=doctor.specialisation,
    )


# ─── Login ────────────────────────────────────────────────────────

@auth_router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login with email + password. Returns JWT access token."""
    result = await db.execute(
        select(Doctor).where(Doctor.email == form.username)
    )
    doctor = result.scalar_one_or_none()

    if not doctor or not verify_password(form.password, doctor.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not doctor.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    # Update last login timestamp
    doctor.last_login = datetime.utcnow()
    db.add(AuditLog(
        session_id=None,
        doctor_id=doctor.doctor_id,
        action="DOCTOR_LOGIN",
        meta_data={"email": doctor.email},
    ))
    await db.commit()

    token = create_access_token(doctor.doctor_id, doctor.email)
    return TokenResponse(
        access_token=token,
        doctor_id=doctor.doctor_id,
        full_name=doctor.full_name,
        email=doctor.email,
        specialisation=doctor.specialisation,
    )


# ─── Me ───────────────────────────────────────────────────────────

@auth_router.get("/me")
async def get_me(doctor: Doctor = Depends(get_current_doctor)):
    """Return the currently authenticated doctor's profile."""
    return {
        "doctor_id":      doctor.doctor_id,
        "email":          doctor.email,
        "full_name":      doctor.full_name,
        "specialisation": doctor.specialisation,
        "last_login":     doctor.last_login.isoformat() if doctor.last_login else None,
    }


# ─── Change password ──────────────────────────────────────────────

@auth_router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(req.current_password, doctor.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    doctor.hashed_password = hash_password(req.new_password)
    db.add(AuditLog(
        session_id=None,
        doctor_id=doctor.doctor_id,
        action="PASSWORD_CHANGED",
        meta_data={},
    ))
    await db.commit()
    return {"message": "Password changed successfully"}
