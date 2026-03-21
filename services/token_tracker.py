"""Token usage tracking — per user per day.

Tracks input + output tokens from all LLM calls.
Daily limit: 2M tokens. Alerts at 80%/100%.
"""

import uuid
import logging
from datetime import date, datetime, timezone
from config.database import get_session

logger = logging.getLogger(__name__)

DAILY_LIMIT = 2_000_000  # 2M tokens
WARN_THRESHOLD = 0.8     # 80%


def estimate_tokens(text):
    """Rough token estimate: ~4 chars = 1 token."""
    if not text:
        return 0
    return len(str(text)) // 4


def track_usage(user_id, input_tokens, output_tokens):
    """Record token usage for a user. Called after each LLM API response."""
    session = get_session()
    try:
        today = date.today()
        from sqlalchemy import text as sql_text

        # Upsert
        result = session.execute(sql_text('''
            INSERT INTO token_usage (id, user_id, date, input_tokens, output_tokens, call_count)
            VALUES (:id, :uid, :d, :inp, :out, 1)
            ON CONFLICT (user_id, date) DO UPDATE SET
                input_tokens = token_usage.input_tokens + :inp,
                output_tokens = token_usage.output_tokens + :out,
                call_count = token_usage.call_count + 1,
                updated_at = NOW()
        '''), {
            'id': str(uuid.uuid4()),
            'uid': user_id,
            'd': today,
            'inp': input_tokens,
            'out': output_tokens,
        })
        session.commit()
    except Exception as e:
        logger.warning(f"Failed to track tokens for {user_id}: {e}")
    finally:
        session.close()


def get_usage(user_id):
    """Get today's token usage for a user.

    Returns: {input_tokens, output_tokens, total, limit, percentage, warning, blocked}
    """
    session = get_session()
    try:
        from sqlalchemy import text as sql_text
        today = date.today()
        result = session.execute(sql_text(
            'SELECT input_tokens, output_tokens, call_count FROM token_usage WHERE user_id = :uid AND date = :d'
        ), {'uid': user_id, 'd': today})
        row = result.fetchone()

        if row:
            inp, out, calls = row
        else:
            inp, out, calls = 0, 0, 0

        total = inp + out
        pct = total / DAILY_LIMIT if DAILY_LIMIT > 0 else 0

        return {
            'input_tokens': inp,
            'output_tokens': out,
            'total': total,
            'calls': calls,
            'limit': DAILY_LIMIT,
            'percentage': round(pct * 100, 1),
            'warning': pct >= WARN_THRESHOLD,
            'blocked': pct >= 1.0,
        }
    except Exception as e:
        logger.warning(f"Failed to get usage for {user_id}: {e}")
        return {
            'input_tokens': 0, 'output_tokens': 0, 'total': 0,
            'calls': 0, 'limit': DAILY_LIMIT, 'percentage': 0,
            'warning': False, 'blocked': False,
        }
    finally:
        session.close()


def check_limit(user_id):
    """Quick check if user is over the daily limit.

    Returns: (allowed: bool, usage: dict)
    """
    usage = get_usage(user_id)
    return not usage['blocked'], usage
