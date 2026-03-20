"""Chat Worker Lambda — processes chat messages asynchronously.

Invoked by chat.py via async Lambda invoke. Runs the LLM tool-call loop
and writes the result back to the chat_tasks table.

Timeout: 300s (5 minutes)
"""

import json
import logging
from config.database import get_session
from models.conversation import Conversation
from models.message import Message
from models.chat_task import ChatTask
from services.llm_service import chat

logger = logging.getLogger(__name__)


def handler(event, context):
    """Process a chat task. Event has: task_id, user_id, conversation_id, message."""
    task_id = event.get("task_id")
    user_id = event.get("user_id")
    conversation_id = event.get("conversation_id")
    message = event.get("message", "")

    if not task_id:
        logger.error("No task_id in event")
        return

    session = get_session()
    try:
        # Mark as processing
        task = session.query(ChatTask).filter_by(id=task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        task.status = "processing"
        session.commit()

        # Load conversation history
        history_rows = (
            session.query(Message)
            .filter_by(conversation_id=conversation_id)
            .order_by(Message.created_at)
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in history_rows]

        # Call LLM (can take minutes)
        result = chat(
            messages=[{"role": "user", "content": message}],
            conversation_history=history,
        )

        # Save assistant message to conversation
        asst_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=result["content"],
            widgets=result.get("widgets", []),
        )
        session.add(asst_msg)

        # Update task with result
        task.status = "completed"
        task.result_content = result["content"]
        task.result_widgets = result.get("widgets", [])
        session.commit()

        logger.info(f"Task {task_id} completed")

    except Exception as e:
        logger.exception(f"Task {task_id} failed")
        try:
            task = session.query(ChatTask).filter_by(id=task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                session.commit()
        except Exception:
            pass
    finally:
        session.close()
