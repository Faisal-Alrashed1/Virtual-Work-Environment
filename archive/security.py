from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import get_db
from app.models.domain import User

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(value: str) -> str:
    return pwd.hash(value)


def verify_password(value: str, hashed: str) -> bool:
    return pwd.verify(value, hashed)


def token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iss": "venv-api",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def current_user(raw: str = Depends(oauth), db: Session = Depends(get_db)) -> User:
    try:
        user_id = jwt.decode(raw, settings.secret_key, algorithms=[settings.algorithm], issuer="venv-api")["sub"]
    except (JWTError, KeyError):
        raise HTTPException(401, "جلسة غير صالحة")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "المستخدم غير موجود")
    return user
