"""Authentication: bcrypt password hashing + database-backed sessions.

Sessions are opaque random tokens in an httpOnly cookie — revocable server-side
(unlike stateless JWTs), which is what you want for logout and account security.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Cookie, Depends, HTTPException

from .config import settings
from .models import AuthSession, SessionLocal, User

SESSION_COOKIE = "gl_session"
SESSION_TTL = timedelta(days=30)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_session(db, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(
        token=token,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + SESSION_TTL,
    ))
    db.commit()
    return token


def destroy_session(db, token: str) -> None:
    s = db.get(AuthSession, token)
    if s:
        db.delete(s)
        db.commit()


def user_from_token(token: str | None) -> User | None:
    if not token:
        return None
    db = SessionLocal()
    try:
        s = db.get(AuthSession, token)
        if not s:
            return None
        expires = s.expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires is not None and expires < datetime.now(timezone.utc):
            db.delete(s)
            db.commit()
            return None
        return db.get(User, s.user_id)
    finally:
        db.close()


def get_current_user(gl_session: str | None = Cookie(default=None)) -> User:
    """FastAPI dependency: 401 when there's no valid session."""
    user = user_from_token(gl_session)
    if not user:
        raise HTTPException(401, "Not signed in")
    return user


def require_verified(user: User = Depends(get_current_user)) -> User:
    
    if user.email_verified:
        return user
    raise HTTPException(403, {"code": "email_unverified",
                              "detail": "Verify your email to create projects or run pipelines."})
