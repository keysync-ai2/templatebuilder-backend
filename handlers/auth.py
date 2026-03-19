"""Auth Lambda — /api/auth/* routes.

POST /api/auth/signup    — Create account
POST /api/auth/login     — Login, get tokens
POST /api/auth/refresh   — Refresh access token
GET  /api/auth/me        — Get current user profile
"""

import json
from utils.response import success, error, options_response
from utils.auth import verify_token
from services.auth_service import hash_password, check_password, create_tokens, decode_refresh_token
from config.database import get_session
from models.user import User


def handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    body = json.loads(event.get("body") or "{}")
    headers = event.get("headers") or {}

    if method == "OPTIONS":
        return options_response()

    if path == "/api/auth/signup" and method == "POST":
        return _signup(body)
    elif path == "/api/auth/login" and method == "POST":
        return _login(body)
    elif path == "/api/auth/refresh" and method == "POST":
        return _refresh(body)
    elif path == "/api/auth/me" and method == "GET":
        return _get_me(headers)
    else:
        return error(404, "NOT_FOUND", "Route not found")


def _signup(body: dict):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password", "")
    name = (body.get("name") or "").strip()

    if not email or not password:
        return error(400, "VALIDATION_ERROR", "Email and password required")
    if len(password) < 8:
        return error(400, "VALIDATION_ERROR", "Password must be at least 8 characters")

    session = get_session()
    try:
        existing = session.query(User).filter_by(email=email).first()
        if existing:
            return error(409, "EMAIL_EXISTS", "An account with this email already exists")

        display = name or email.split("@")[0]
        user = User(email=email, full_name=display, name=display, password_hash=hash_password(password))
        session.add(user)
        session.commit()
        session.refresh(user)

        tokens = create_tokens(str(user.id), user.email)
        return success(201, {**tokens, "user": {"id": str(user.id), "email": user.email, "name": user.name}})
    finally:
        session.close()


def _login(body: dict):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        return error(400, "VALIDATION_ERROR", "Email and password required")

    session = get_session()
    try:
        user = session.query(User).filter_by(email=email).first()
        if not user or not check_password(password, user.password_hash):
            return error(401, "INVALID_CREDENTIALS", "Invalid email or password")

        tokens = create_tokens(str(user.id), user.email)
        return success(200, {**tokens, "user": {"id": str(user.id), "email": user.email, "name": user.name}})
    finally:
        session.close()


def _refresh(body: dict):
    token = body.get("refresh_token", "")
    if not token:
        return error(400, "VALIDATION_ERROR", "refresh_token required")

    payload = decode_refresh_token(token)
    if not payload:
        return error(401, "INVALID_TOKEN", "Invalid or expired refresh token")

    tokens = create_tokens(payload["sub"], payload["email"])
    return success(200, tokens)


def _get_me(headers: dict):
    payload = verify_token(headers)
    if not payload:
        return error(401, "UNAUTHORIZED", "Invalid or missing token")

    session = get_session()
    try:
        user = session.query(User).filter_by(id=payload["sub"]).first()
        if not user:
            return error(404, "NOT_FOUND", "User not found")
        return success(200, {"id": str(user.id), "email": user.email, "name": user.name})
    finally:
        session.close()
