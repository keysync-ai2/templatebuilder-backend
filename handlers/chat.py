"""Chat Lambda — /api/chat/* routes.

POST /api/chat            — Send message, get AI response with optional widgets
"""

import json
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from models.conversation import Conversation
from models.message import Message
from services.llm_service import chat


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

    if path == "/api/chat" and method == "POST":
        return _chat(body, user_id)

    return error(404, "NOT_FOUND", "Route not found")


def _chat(body: dict, user_id: str):
    conversation_id = body.get("conversation_id")
    message = body.get("message", "").strip()

    if not message:
        return error(400, "VALIDATION_ERROR", "Message is required")

    session = get_session()
    try:
        # Get or create conversation
        if conversation_id:
            conv = session.query(Conversation).filter_by(id=conversation_id, user_id=user_id).first()
            if not conv:
                return error(404, "NOT_FOUND", "Conversation not found")
        else:
            conv = Conversation(user_id=user_id, title=message[:50])
            session.add(conv)
            session.commit()
            session.refresh(conv)

        # Load conversation history
        history_rows = (
            session.query(Message)
            .filter_by(conversation_id=conv.id)
            .order_by(Message.created_at)
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in history_rows]

        # Save user message
        user_msg = Message(conversation_id=conv.id, role="user", content=message)
        session.add(user_msg)
        session.commit()

        # Call LLM
        result = chat(
            messages=[{"role": "user", "content": message}],
            conversation_history=history,
        )

        # Save assistant message
        asst_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=result["content"],
            widgets=result.get("widgets", []),
        )
        session.add(asst_msg)
        session.commit()

        return success(200, {
            "conversation_id": conv.id,
            "message": result["content"],
            "widgets": result.get("widgets", []),
        })
    finally:
        session.close()
