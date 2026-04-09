"""
Authentication core — JWT tokens + bcrypt password hashing.

Uses bcrypt directly (not passlib) — passlib 1.7.4 is incompatible
with bcrypt>=4.0 which dropped the __about__ attribute.

Tokens expire after 8 hours (one full clinic day).
"""
from __future__ import annotations
from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

TOKEN_EXPIRE_HOURS = 8


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(doctor_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub":   doctor_id,
        "email": email,
        "exp":   expire,
        "iat":   datetime.utcnow(),
        "type":  "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_doctor(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """FastAPI dependency — injects the authenticated Doctor into any route."""
    from app.models.db_models import Doctor
    payload = decode_token(token)
    doctor_id: str = payload.get("sub")
    if not doctor_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(
        select(Doctor).where(Doctor.doctor_id == doctor_id)
    )
    doctor = result.scalar_one_or_none()
    if not doctor or not doctor.is_active:
        raise HTTPException(status_code=401, detail="Doctor account not found or inactive")

    return doctor
