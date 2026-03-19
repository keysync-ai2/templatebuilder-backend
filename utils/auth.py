"""JWT token verification helper."""

import jwt
from config.settings import JWT_SECRET


def verify_token(headers: dict) -> dict | None:
    """Extract and verify JWT from Authorization header.

    Returns the decoded payload dict, or None if invalid/missing.
    """
    auth = headers.get("Authorization") or headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None

    token = auth[7:]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
