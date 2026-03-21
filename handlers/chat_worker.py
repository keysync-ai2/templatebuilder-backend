"""Chat Worker Lambda — processes chat messages asynchronously.

Updates status_message at each step so frontend can show progress.
Timeout: 300s (5 minutes)
"""

import json
import logging
from config.database import get_session
from models.message import Message
from models.chat_task import ChatTask
from services.llm_service import chat

logger = logging.getLogger(__name__)


def _update_status(task_id, status, message=""):
    """Update task status in DB."""
    session = get_session()
    try:
        task = session.query(ChatTask).filter_by(id=task_id).first()
        if task:
            task.status = status
            task.status_message = message
            session.commit()
    finally:
        session.close()


def handler(event, context):
    task_id = event.get("task_id")
    user_id = event.get("user_id")
    conversation_id = event.get("conversation_id")
    message = event.get("message", "")

    if not task_id:
        logger.error("No task_id in event")
        return

    try:
        _update_status(task_id, "processing", "Analyzing your request...")

        # Load history
        session = get_session()
        try:
            history_rows = (
                session.query(Message)
                .filter_by(conversation_id=conversation_id)
                .order_by(Message.created_at)
                .all()
            )
            history = [{"role": m.role, "content": m.content} for m in history_rows]
        finally:
            session.close()

        _update_status(task_id, "processing", "Preparing AI assistant...")

        # Patch smart_suggest to use our status callback
        import services.smart_suggest as smart_suggest
        original_fn = smart_suggest.generate_suggestions

        def _patched_generate(uid, req, status_callback=None):
            def _cb(msg):
                _update_status(task_id, "processing", msg)
            return original_fn(uid, req, status_callback=_cb)

        smart_suggest.generate_suggestions = _patched_generate

        try:
            result = chat(
                messages=[{"role": "user", "content": message}],
                conversation_history=history,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        finally:
            smart_suggest.generate_suggestions = original_fn

        _update_status(task_id, "processing", "Saving your results...")

        # Build enriched content for DB (includes tool summaries for history context)
        enriched_content = result["content"] or ""
        for w in result.get("widgets", []):
            if w.get("type") == "suggestion-cards":
                suggestions = w.get("data", {}).get("suggestions", [])
                if suggestions:
                    enriched_content += "\n\n[Suggested templates: "
                    enriched_content += ", ".join(
                        f"{i+1}. {s['name']} ({s['slug']}, {s['score']:.0%} match)"
                        for i, s in enumerate(suggestions)
                    )
                    enriched_content += "]"

        # Save assistant message
        session = get_session()
        try:
            asst_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=enriched_content,
                widgets=result.get("widgets", []),
            )
            session.add(asst_msg)

            task = session.query(ChatTask).filter_by(id=task_id).first()
            if task:
                task.status = "completed"
                task.status_message = "Done!"
                task.result_content = result["content"]
                task.result_widgets = result.get("widgets", [])
            session.commit()
        finally:
            session.close()

        logger.info(f"Task {task_id} completed")

    except Exception as e:
        logger.exception(f"Task {task_id} failed: {e}")
        try:
            _update_status(task_id, "failed", "Something went wrong")
            session = get_session()
            try:
                task = session.query(ChatTask).filter_by(id=task_id).first()
                if task:
                    task.error_message = str(e)
                    session.commit()
            finally:
                session.close()
        except Exception:
            pass
