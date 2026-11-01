import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from .models import SessionToken, User


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("pbkdf2_sha256$"):
        _, iterations, salt, digest = password_hash.split("$", 3)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                        bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest)
    return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), password_hash)


def create_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(SessionToken(token=token, user_id=user.id, created_at=datetime.now(timezone.utc)))
    db.commit()
    return token


def require_user(authorization: str | None, db: Session) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token = authorization.removeprefix("Bearer ").strip()
    session = db.get(SessionToken, token)
    user = db.get(User, session.user_id) if session else None
    if not user or session.created_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc) - timedelta(hours=24):
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user
