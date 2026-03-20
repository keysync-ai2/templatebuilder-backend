"""Chat Worker Lambda — processes chat messages asynchronously.

Updates status_message at each step so frontend can show progress.
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


def _update_status(session, task_id, status, message=""):
    """Update task status + status_message in DB."""
    task = session.query(ChatTask).filter_by(id=task_id).first()
    if task:
        task.status = status
        task.status_message = message
        session.commit()


def handler(event, context):
    task_id = event.get("task_id")
    user_id = event.get("user_id")
    conversation_id = event.get("conversation_id")
    message = event.get("message", "")

    if not task_id:
        logger.error("No task_id in event")
        return

    session = get_session()
    try:
        # Step 1: Analyzing
        _update_status(session, task_id, "processing", "Analyzing your request...")

        # Load conversation history
        history_rows = (
            session.query(Message)
            .filter_by(conversation_id=conversation_id)
            .order_by(Message.created_at)
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in history_rows]

        # Step 2: Generating
        _update_status(session, task_id, "processing", "Generating email content...")

        # Call LLM (this internally updates steps via suggest_templates)
        # We pass a status callback so smart_suggest can update progress
        import services.smart_suggest as smart_suggest
        _original_generate = smart_suggest.generate_suggestions

        def _wrapped_generate(uid, content):
            _update_status(session, task_id, "processing", "Finding perfect images...")
            # Fetch images
            image_queries = content.get("image_queries", [])
            images = smart_suggest.fetch_unsplash_images(image_queries) if image_queries else {}

            _update_status(session, task_id, "processing", "Matching template layouts...")
            # Search Pinecone
            brand = smart_suggest.get_brand_context(uid)
            purpose = content.get("purpose", "email")
            tone = content.get("tone") or (brand or {}).get("tone", "")
            query_text = smart_suggest.build_query(purpose, brand, tone)
            matches = smart_suggest.search_templates(query_text, top_k=5)

            _update_status(session, task_id, "processing", "Customizing templates for you...")
            # Fetch + customize
            s2 = get_session()
            try:
                slugs = [m["slug"] for m in matches]
                from models.template_library import TemplateLibraryItem
                templates = s2.query(TemplateLibraryItem).filter(
                    TemplateLibraryItem.slug.in_(slugs),
                    TemplateLibraryItem.is_active == True,
                ).all()
                template_map = {t.slug: t for t in templates}
            finally:
                s2.close()

            suggestions = []
            for match in matches:
                t = template_map.get(match["slug"])
                if not t:
                    continue
                customized = smart_suggest.customize_template(t.components, content, images, brand)
                suggestions.append({
                    "slug": match["slug"],
                    "name": t.name,
                    "description": t.description,
                    "industry": t.industry,
                    "purpose": t.purpose,
                    "tone": t.tone,
                    "score": match["score"],
                    "components": customized,
                })

            return suggestions, query_text

        # Monkey-patch for this request
        smart_suggest.generate_suggestions = _wrapped_generate

        try:
            result = chat(
                messages=[{"role": "user", "content": message}],
                conversation_history=history,
                user_id=user_id,
            )
        finally:
            smart_suggest.generate_suggestions = _original_generate

        _update_status(session, task_id, "processing", "Preparing your results...")

        # Save assistant message
        asst_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=result["content"],
            widgets=result.get("widgets", []),
        )
        session.add(asst_msg)

        # Complete task
        task = session.query(ChatTask).filter_by(id=task_id).first()
        if task:
            task.status = "completed"
            task.status_message = "Done!"
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
                task.status_message = "Something went wrong"
                session.commit()
        except Exception:
            pass
    finally:
        session.close()
