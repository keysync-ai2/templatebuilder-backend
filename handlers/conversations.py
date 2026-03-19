"""Conversations Lambda — /api/conversations/* routes.

GET    /api/conversations           — List conversations
GET    /api/conversations/{id}      — Get conversation with messages
DELETE /api/conversations/{id}      — Delete conversation
PUT    /api/conversations/{id}      — Update title
"""

import json
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from models.conversation import Conversation
from models.message import Message


def handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    body = json.loads(event.get("body") or "{}")
    headers = event.get("headers") or {}

    if method == "OPTIONS":
        return options_response()

    payload = verify_token(headers)
    if not payload:
        return error(401, "UNAUTHORIZED", "Invalid or missing token")
    user_id = payload["sub"]

    if path == "/api/conversations" and method == "GET":
        return _list(user_id)

    parts = path.rstrip("/").split("/")
    if len(parts) == 4 and parts[2] == "conversations":
        conv_id = parts[3]
        if method == "GET":
            return _get(conv_id, user_id)
        if method == "PUT":
            return _update(conv_id, user_id, body)
        if method == "DELETE":
            return _delete(conv_id, user_id)

    return error(404, "NOT_FOUND", "Route not found")


def _list(user_id: str):
    session = get_session()
    try:
        convs = (
            session.query(Conversation)
            .filter_by(user_id=user_id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
        return success(200, {
            "conversations": [
                {"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()}
                for c in convs
            ]
        })
    finally:
        session.close()


def _get(conv_id: str, user_id: str):
    session = get_session()
    try:
        conv = session.query(Conversation).filter_by(id=conv_id, user_id=user_id).first()
        if not conv:
            return error(404, "NOT_FOUND", "Conversation not found")

        msgs = (
            session.query(Message)
            .filter_by(conversation_id=conv.id)
            .order_by(Message.created_at)
            .all()
        )
        return success(200, {
            "id": conv.id,
            "title": conv.title,
            "messages": [
                {"id": m.id, "role": m.role, "content": m.content, "widgets": m.widgets or []}
                for m in msgs
            ],
        })
    finally:
        session.close()


def _update(conv_id: str, user_id: str, body: dict):
    session = get_session()
    try:
        conv = session.query(Conversation).filter_by(id=conv_id, user_id=user_id).first()
        if not conv:
            return error(404, "NOT_FOUND", "Conversation not found")
        if "title" in body:
            conv.title = body["title"]
        session.commit()
        return success(200, {"id": conv.id, "title": conv.title})
    finally:
        session.close()


def _delete(conv_id: str, user_id: str):
    session = get_session()
    try:
        conv = session.query(Conversation).filter_by(id=conv_id, user_id=user_id).first()
        if not conv:
            return error(404, "NOT_FOUND", "Conversation not found")
        session.delete(conv)
        session.commit()
        return success(200, {"deleted": True})
    finally:
        session.close()
