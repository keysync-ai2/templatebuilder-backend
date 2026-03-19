"""JWT generation, password hashing, token verification."""

import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from config.settings import JWT_SECRET, JWT_ACCESS_TTL, JWT_REFRESH_TTL


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_tokens(user_id, email: str) -> dict:
    now = datetime.now(timezone.utc)
    uid = str(user_id)
    access = jwt.encode(
        {"sub": uid, "email": email, "exp": now + timedelta(seconds=JWT_ACCESS_TTL), "type": "access"},
        JWT_SECRET,
        algorithm="HS256",
    )
    refresh = jwt.encode(
        {"sub": uid, "email": email, "exp": now + timedelta(seconds=JWT_REFRESH_TTL), "type": "refresh"},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"access_token": access, "refresh_token": refresh}


def decode_refresh_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            return None
        return payload
    except jwt.InvalidTokenError:
        return None
