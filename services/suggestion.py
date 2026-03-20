"""Template suggestion engine — Pinecone semantic search + brand context."""

import os
import logging
from pinecone import Pinecone

logger = logging.getLogger(__name__)

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_INDEX = "template-library"
EMBED_MODEL = "multilingual-e5-large"

_pc = None
_idx = None


def _get_index():
    global _pc, _idx
    if _idx is None:
        _pc = Pinecone(api_key=PINECONE_API_KEY)
        _idx = _pc.Index(PINECONE_INDEX)
    return _pc, _idx


def build_query(purpose, brand_profile=None, tone_override=None):
    """Build a natural language query from purpose + brand context."""
    parts = []

    if brand_profile:
        if brand_profile.get("industry") and brand_profile["industry"] != "other":
            parts.append(brand_profile["industry"])
        if tone_override:
            parts.append(tone_override)
        elif brand_profile.get("tone"):
            parts.append(brand_profile["tone"])

    parts.append(purpose)
    parts.append("email template")

    return " ".join(parts)


def search_templates(query_text, top_k=5):
    """Search Pinecone for templates matching the query.

    Returns list of {slug, name, description, industry, purpose, tone, score}.
    """
    pc, idx = _get_index()

    # Embed the query
    query_embedding = pc.inference.embed(
        model=EMBED_MODEL,
        inputs=[query_text],
        parameters={"input_type": "query"},
    )

    # Search
    results = idx.query(
        vector=query_embedding.data[0].values,
        top_k=top_k,
        include_metadata=True,
    )

    suggestions = []
    for match in results.matches:
        meta = match.metadata or {}
        suggestions.append({
            "slug": match.id,
            "name": meta.get("name", match.id),
            "description": meta.get("description", ""),
            "industry": meta.get("industry", ""),
            "purpose": meta.get("purpose", ""),
            "tone": meta.get("tone", ""),
            "score": round(float(match.score), 3),
        })

    return suggestions
