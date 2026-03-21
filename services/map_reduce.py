"""Map-Reduce — summarize large tool responses.

When any MCP tool response exceeds 70K tokens:
1. Split into 40K token chunks with 5K overlap
2. Summarize each chunk independently
3. Combine summaries into a final summary

Max input: 300K tokens (8 chunks).
"""

import json
import logging
from openai import OpenAI
from config.settings import DEEPSEEK_API_KEY
from services.token_tracker import estimate_tokens, track_usage

logger = logging.getLogger(__name__)

CHUNK_SIZE = 40000          # 40K tokens per chunk
OVERLAP = 5000              # 5K token overlap between chunks
MAX_INPUT = 300000          # 300K tokens max
THRESHOLD = 70000           # Trigger map-reduce above this
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


def needs_map_reduce(content):
    """Check if content exceeds the threshold for map-reduce.

    Args:
        content: string or dict (will be JSON-serialized)

    Returns: (needs: bool, estimated_tokens: int)
    """
    if isinstance(content, dict):
        text = json.dumps(content, default=str)
    else:
        text = str(content)

    tokens = estimate_tokens(text)
    return tokens > THRESHOLD, tokens


def summarize_large_response(content, tool_name="tool", user_id=None):
    """Map-reduce summarization of a large tool response.

    Args:
        content: string or dict — the large response
        tool_name: name of the tool that produced this (for context)
        user_id: for token tracking

    Returns: summarized string (~3K tokens)
    """
    if isinstance(content, dict):
        text = json.dumps(content, default=str, indent=None)
    else:
        text = str(content)

    total_tokens = estimate_tokens(text)

    if total_tokens > MAX_INPUT:
        text = text[:MAX_INPUT * 4]  # Rough char limit
        total_tokens = MAX_INPUT
        logger.warning(f"Tool response truncated from {estimate_tokens(str(content))} to {MAX_INPUT} tokens")

    # Split into chunks
    chunks = _split_chunks(text, CHUNK_SIZE, OVERLAP)
    logger.info(f"Map-reduce: {total_tokens} tokens → {len(chunks)} chunks for {tool_name}")

    # Map: summarize each chunk
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        summary = _summarize_chunk(chunk, tool_name, i + 1, len(chunks))
        chunk_summaries.append(summary)

        # Track tokens
        if user_id:
            track_usage(user_id, estimate_tokens(chunk), estimate_tokens(summary))

    # Reduce: combine summaries
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    combined = "\n\n".join(chunk_summaries)

    # If combined is still too large, do another pass
    if estimate_tokens(combined) > 5000:
        final = _reduce_summaries(combined, tool_name)
        if user_id:
            track_usage(user_id, estimate_tokens(combined), estimate_tokens(final))
        return final

    return combined


def _split_chunks(text, chunk_size, overlap):
    """Split text into chunks by estimated token count with overlap."""
    chars_per_token = 4
    chunk_chars = chunk_size * chars_per_token
    overlap_chars = overlap * chars_per_token

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap_chars  # Move back by overlap

        if end >= len(text):
            break

    return chunks


def _summarize_chunk(chunk, tool_name, chunk_num, total_chunks):
    """Summarize a single chunk."""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=800,
            temperature=0.3,
            messages=[
                {"role": "system", "content": "Summarize data concisely. Keep key facts, numbers, names. Remove formatting and redundancy."},
                {"role": "user", "content": f"Summarize this data from {tool_name} (chunk {chunk_num}/{total_chunks}):\n\n{chunk}"},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"Chunk {chunk_num} summarization failed: {e}")
        return f"[Chunk {chunk_num}: summarization failed — {len(chunk)} chars of data]"


def _reduce_summaries(combined_summaries, tool_name):
    """Reduce multiple chunk summaries into a final summary."""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=1000,
            temperature=0.3,
            messages=[
                {"role": "system", "content": "Combine these summaries into one concise final summary. Preserve all key information."},
                {"role": "user", "content": f"Combine these summaries from {tool_name}:\n\n{combined_summaries}"},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"Reduce step failed: {e}")
        return combined_summaries[:3000]
