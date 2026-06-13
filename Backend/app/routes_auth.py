from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select
from pydantic import BaseModel

from .models import User
from .db import get_session
from .auth_helpers import get_current_user
from .auth_utils import hash_password, verify_password, create_token

router = APIRouter()


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
    }



class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str


@router.post("/register")
def register_user(data: RegisterRequest):
    if data.role not in ("admin", "applicant"):
        raise HTTPException(400, "Invalid role")

    with get_session() as session:
        existing = session.exec(
            select(User).where(User.email == data.email)
        ).first()

        if existing:
            raise HTTPException(400, "Email already registered")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        return {
            "status": "registered",
            "user_id": user.id,
        }


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(data: LoginRequest):
    with get_session() as session:
        user = session.exec(
            select(User).where(User.email == data.email)
        ).first()

        if not user:
            raise HTTPException(401, "Invalid credentials")

        if not verify_password(data.password, user.hashed_password):
            raise HTTPException(401, "Invalid credentials")

        token = create_token({
            "sub": str(user.id),
            "role": user.role,
        })

        return {
            "access_token": token,
            "token_type": "bearer",
        }
