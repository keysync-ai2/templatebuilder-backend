"""Context Manager — rolling summary + history pruning.

Manages conversation context within 20K token budget:
- Last 5 message pairs sent as-is
- Older messages folded into rolling summary (max 2K tokens)
- Summary stored on conversation record in DB
"""

import logging
from openai import OpenAI
from config.settings import DEEPSEEK_API_KEY
from config.database import get_session
from models.conversation import Conversation
from services.token_tracker import estimate_tokens

logger = logging.getLogger(__name__)

HISTORY_BUDGET = 20000       # 20K tokens max for history
SUMMARY_BUDGET = 2000        # 2K tokens for rolling summary
RECENT_PAIRS = 5             # Keep last 5 pairs (10 messages)
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


def build_history(conversation_id, conversation_history, user_id=None):
    """Build the conversation history for the LLM.

    Returns: list of {role, content} messages within 20K token budget.
    """
    if not conversation_history:
        return []

    # Split into pairs (user + assistant)
    pairs = []
    i = 0
    while i < len(conversation_history):
        if i + 1 < len(conversation_history):
            pairs.append([conversation_history[i], conversation_history[i + 1]])
            i += 2
        else:
            pairs.append([conversation_history[i]])
            i += 1

    # If within limit, return as-is
    if len(pairs) <= RECENT_PAIRS:
        flat = []
        for pair in pairs:
            for msg in pair:
                content = _prune_content(msg.get("content", ""))
                flat.append({"role": msg.get("role", "user"), "content": content})
        total = sum(estimate_tokens(m["content"]) for m in flat)
        if total <= HISTORY_BUDGET:
            return flat

    # Need rolling summary — get recent pairs + summarize the rest
    recent_pairs = pairs[-RECENT_PAIRS:]
    old_pairs = pairs[:-RECENT_PAIRS]

    # Load existing rolling summary
    summary = _get_rolling_summary(conversation_id)

    # Update summary with old pairs that haven't been summarized yet
    if old_pairs:
        summary = _update_summary(summary, old_pairs)
        _save_rolling_summary(conversation_id, summary)

    # Build final history
    result = []

    if summary:
        result.append({
            "role": "system",
            "content": f"[Conversation context summary]\n{summary}",
        })

    for pair in recent_pairs:
        for msg in pair:
            content = _prune_content(msg.get("content", ""))
            result.append({"role": msg.get("role", "user"), "content": content})

    # Final check — truncate if still over budget
    total = sum(estimate_tokens(m["content"]) for m in result)
    while total > HISTORY_BUDGET and len(result) > 2:
        removed = result.pop(1)  # Remove oldest after summary
        total -= estimate_tokens(removed["content"])

    return result


def _prune_content(content):
    """Remove large JSON/HTML blobs from message content."""
    if not content:
        return ""

    # Strip component tree JSON (from template suggestions)
    import re
    content = re.sub(r'\{["\']components["\']:\s*\[.*?\]\}', '[template data]', content, flags=re.DOTALL)

    # Strip raw HTML documents
    content = re.sub(r'<!DOCTYPE.*?</html>', '[HTML document]', content, flags=re.DOTALL)

    # Strip very long JSON arrays
    content = re.sub(r'\[\s*\{.*?\}\s*\]', '[data array]', content, flags=re.DOTALL)

    # Truncate if still too long
    if len(content) > 2000:
        content = content[:2000] + "... [truncated]"

    return content


def _get_rolling_summary(conversation_id):
    """Load rolling summary from DB."""
    if not conversation_id:
        return ""
    session = get_session()
    try:
        conv = session.query(Conversation).filter_by(id=conversation_id).first()
        return conv.rolling_summary if conv and hasattr(conv, 'rolling_summary') else ""
    except Exception:
        return ""
    finally:
        session.close()


def _save_rolling_summary(conversation_id, summary):
    """Save rolling summary to DB."""
    if not conversation_id:
        return
    session = get_session()
    try:
        conv = session.query(Conversation).filter_by(id=conversation_id).first()
        if conv:
            conv.rolling_summary = summary
            session.commit()
    except Exception as e:
        logger.warning(f"Failed to save rolling summary: {e}")
    finally:
        session.close()


def _update_summary(existing_summary, new_pairs):
    """Update rolling summary by folding in new message pairs.

    Uses LLM to summarize existing_summary + new_pairs into max 2K tokens.
    """
    # Build text of new pairs
    new_text = ""
    for pair in new_pairs:
        for msg in pair:
            role = msg.get("role", "user")
            content = _prune_content(msg.get("content", ""))[:500]
            new_text += f"{role}: {content}\n"

    prompt = f"""Summarize the following conversation context into a concise summary (max 400 words).
Preserve: user's intent, decisions made, templates/products discussed, brand details, any preferences.
Drop: raw data, HTML, JSON, technical details.

{f"Previous summary: {existing_summary}" if existing_summary else "No previous summary."}

New messages to include:
{new_text}

Write a single paragraph summary:"""

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=600,
            temperature=0.3,
            messages=[
                {"role": "system", "content": "You summarize conversations concisely. Output only the summary, no preamble."},
                {"role": "user", "content": prompt},
            ],
        )
        summary = response.choices[0].message.content or ""

        # Track tokens
        from services.token_tracker import track_usage
        usage = response.usage
        if usage:
            track_usage("system-summary", usage.prompt_tokens, usage.completion_tokens)

        return summary[:2000]  # Hard cap
    except Exception as e:
        logger.error(f"Rolling summary failed: {e}")
        # Fallback: just concatenate
        fallback = existing_summary + "\n" + new_text[:500] if existing_summary else new_text[:500]
        return fallback[:2000]
