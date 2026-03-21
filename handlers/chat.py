"""Chat Lambda — /api/chat/* routes.

POST /api/chat                — Submit message, returns task_id immediately
GET  /api/chat/status/{id}    — Poll for result
"""

import json
import boto3
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from models.conversation import Conversation
from models.message import Message
from models.chat_task import ChatTask

_lambda_client = None


def _get_lambda_client():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client("lambda")
    return _lambda_client


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
        return _submit_chat(body, user_id)

    # GET /api/chat/tokens
    if path == "/api/chat/tokens" and method == "GET":
        from services.token_tracker import get_usage
        return success(200, get_usage(user_id))

    # POST /api/chat/permission
    if path == "/api/chat/permission" and method == "POST":
        return _handle_permission(body, user_id)

    # POST /api/chat/command
    if path == "/api/chat/command" and method == "POST":
        from handlers.command import _handle_command
        return _handle_command(body, user_id)

    # GET /api/chat/status/{task_id}
    parts = path.rstrip("/").split("/")
    if len(parts) == 5 and parts[3] == "status" and method == "GET":
        return _poll_status(parts[4], user_id)

    return error(404, "NOT_FOUND", "Route not found")


def _submit_chat(body: dict, user_id: str):
    """Submit a chat message. Creates task, invokes worker async, returns immediately."""
    message = body.get("message", "").strip()
    conversation_id = body.get("conversation_id")

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

        # Save user message
        user_msg = Message(conversation_id=conv.id, role="user", content=message)
        session.add(user_msg)

        # Create task
        task = ChatTask(
            user_id=user_id,
            conversation_id=conv.id,
            status="pending",
            message=message,
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        # Invoke worker Lambda asynchronously
        try:
            _get_lambda_client().invoke(
                FunctionName="email-builder-chat-worker",
                InvocationType="Event",  # async — returns immediately
                Payload=json.dumps({
                    "task_id": task.id,
                    "user_id": user_id,
                    "conversation_id": conv.id,
                    "message": message,
                }),
            )
        except Exception as e:
            # If async invoke fails, mark task as failed
            task.status = "failed"
            task.error_message = f"Failed to start worker: {str(e)}"
            session.commit()

        return success(202, {
            "task_id": task.id,
            "conversation_id": conv.id,
            "status": "pending",
        })
    finally:
        session.close()


def _poll_status(task_id: str, user_id: str):
    """Poll for task result."""
    session = get_session()
    try:
        task = session.query(ChatTask).filter_by(id=task_id, user_id=user_id).first()
        if not task:
            return error(404, "NOT_FOUND", "Task not found")

        result = {
            "task_id": task.id,
            "status": task.status,
            "conversation_id": task.conversation_id,
            "status_message": task.status_message or "",
        }

        if task.status == "completed":
            result["message"] = task.result_content
            result["widgets"] = task.result_widgets or []
            from services.token_tracker import get_usage
            result["token_usage"] = get_usage(user_id)
        elif task.status == "needs_permission":
            result["widgets"] = task.result_widgets or []
            result["pending_doc_id"] = task.pending_doc_id or ""
        elif task.status == "failed":
            result["error"] = task.error_message

        return success(200, result)
    finally:
        session.close()


def _handle_permission(body: dict, user_id: str):
    """Handle user's permission choice for map-reduce."""
    task_id = body.get("task_id", "")
    choice = body.get("choice", "")  # "summarize" or "skip"
    doc_id = body.get("doc_id", "")

    if not task_id or not choice:
        return error(400, "VALIDATION_ERROR", "task_id and choice required")

    if choice not in ("summarize", "skip"):
        return error(400, "VALIDATION_ERROR", "choice must be 'summarize' or 'skip'")

    session = get_session()
    try:
        task = session.query(ChatTask).filter_by(id=task_id, user_id=user_id).first()
        if not task:
            return error(404, "NOT_FOUND", "Task not found")

        task.permission_choice = choice
        task.status = "processing"
        task.status_message = "Resuming with your choice..."
        session.commit()

        # Invoke worker to resume
        try:
            _get_lambda_client().invoke(
                FunctionName="email-builder-chat-worker",
                InvocationType="Event",
                Payload=json.dumps({
                    "task_id": task_id,
                    "user_id": user_id,
                    "conversation_id": task.conversation_id,
                    "message": task.message,
                    "resume_permission": True,
                    "doc_id": doc_id or task.pending_doc_id,
                    "choice": choice,
                }),
            )
        except Exception as e:
            task.status = "failed"
            task.error_message = f"Failed to resume: {str(e)}"
            session.commit()

        return success(202, {
            "task_id": task_id,
            "status": "processing",
            "choice": choice,
        })
    finally:
        session.close()
