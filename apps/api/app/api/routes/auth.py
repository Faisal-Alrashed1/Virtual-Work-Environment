from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import current_user, hash_password, token, verify_password
from app.models.domain import User
from app.schemas.api import Login, Register

router = APIRouter()

@router.post("/auth/register")
def register(data: Register, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(409, "البريد مستخدم")
    user = User(name=data.name, email=data.email, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": token(user), "user": {"id": user.id, "name": user.name, "role": user.role}}

@router.post("/auth/login")
def login(data: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "بيانات الدخول غير صحيحة")
    return {"access_token": token(user), "user": {"id": user.id, "name": user.name, "role": user.role}}

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
