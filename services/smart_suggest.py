"""Smart suggestion service — LLM extracts content, Pinecone finds layouts, Python customizes templates.

Flow:
1. LLM extracts structured content from user request
2. Fetch Unsplash images for relevant queries
3. Pinecone finds top 5 matching template layouts
4. Inject LLM content + images + brand colors into each template
5. Return 5 fully customized suggestions
"""

import json
import os
import uuid
import copy
import logging
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from config.database import get_session
from models.brand_profile import BrandProfile
from models.template_library import TemplateLibraryItem
from services.suggestion import search_templates, build_query

logger = logging.getLogger(__name__)

UNSPLASH_API = "https://api.unsplash.com"
UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")


def fetch_unsplash_images(queries, per_query=1):
    """Fetch images from Unsplash for a list of queries."""
    if not UNSPLASH_KEY:
        return {}

    images = {}
    for q in queries:
        try:
            url = f"{UNSPLASH_API}/search/photos?{urlencode({'query': q, 'per_page': str(per_query)})}"
            req = Request(url, headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"})
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            results = data.get("results", [])
            if results:
                images[q] = results[0].get("urls", {}).get("regular", "")
        except Exception as e:
            logger.warning(f"Unsplash fetch failed for '{q}': {e}")
    return images


def get_brand_context(user_id):
    """Fetch brand profile for a user."""
    session = get_session()
    try:
        brand = session.query(BrandProfile).filter_by(user_id=user_id).first()
        return brand.to_dict() if brand else None
    finally:
        session.close()


def customize_template(template_components, content, images, brand):
    """Inject content, images, and brand colors into a template's component tree.

    Args:
        template_components: list of nested component dicts (from library)
        content: dict with keys like headline, subtitle, cta_text, features, etc.
        images: dict of {query: url} from Unsplash
        brand: brand profile dict or None

    Returns:
        New component list with content injected
    """
    components = copy.deepcopy(template_components)
    image_urls = list(images.values()) if images else []
    image_idx = [0]  # mutable counter

    def _next_image():
        if not image_urls:
            return None
        url = image_urls[image_idx[0] % len(image_urls)]
        image_idx[0] += 1
        return url

    # Brand colors
    primary = (brand or {}).get("primary_color", "#2563EB")
    secondary = (brand or {}).get("secondary_color", "#1E40AF")
    company = (brand or {}).get("business_name", content.get("company", ""))

    headline = content.get("headline", "")
    subtitle = content.get("subtitle", "")
    cta_text = content.get("cta_text", "Get Started")
    features = content.get("features", [])
    body_text = content.get("body_text", "")
    feature_idx = [0]

    def _walk(comp):
        ctype = comp.get("type", "")
        props = comp.get("props", {})

        # Apply brand colors to rows/columns with dark backgrounds
        if ctype == "row":
            bg = props.get("backgroundColor", "")
            if bg and bg not in ("#FFFFFF", "#F8F9FA", "#F0FDF4", "#FFFFFF", "transparent", ""):
                props["backgroundColor"] = primary

        if ctype == "column":
            bg = props.get("backgroundColor", "")
            if bg and bg not in ("#FFFFFF", "#F8F9FA", "#F0FDF4", "transparent", "", "#FFFFFF"):
                props["backgroundColor"] = primary

        # Inject content
        if ctype == "heading":
            level = props.get("level", "h2")
            if level == "h1" and headline:
                props["content"] = headline
            elif level == "h2":
                if subtitle and not body_text:
                    props["content"] = subtitle
            elif level == "h3" and features and feature_idx[0] < len(features):
                props["content"] = features[feature_idx[0]]
                feature_idx[0] += 1

            # Apply brand color to headings on dark bg
            color = props.get("color", "")
            if color and color not in ("#FFFFFF", "#ffffff"):
                props["color"] = primary

        if ctype == "text":
            content_text = props.get("content", "")
            # Replace first long text with subtitle
            if subtitle and len(content_text) > 50:
                props["content"] = subtitle
                subtitle_used = True

            # Replace company name in footer
            if company and "<strong>" in content_text:
                import re
                props["content"] = re.sub(r"<strong>.*?</strong>", f"<strong>{company}</strong>", content_text)

        if ctype == "button":
            if cta_text and props.get("text"):
                # Only replace first CTA
                props["text"] = cta_text
                cta_text_used = True
            # Apply brand color
            bg = props.get("backgroundColor", "")
            if bg and bg not in ("#FFFFFF", "#ffffff"):
                props["backgroundColor"] = primary

        if ctype == "image":
            img_url = _next_image()
            if img_url:
                props["src"] = img_url

        # Recurse into children
        for child in comp.get("children", []):
            if isinstance(child, dict):
                _walk(child)

    for comp in components:
        _walk(comp)

    # Remap IDs to avoid conflicts
    def _remap(items):
        for comp in items:
            comp["id"] = f"sug-{uuid.uuid4().hex[:8]}"
            for child in comp.get("children", []):
                if isinstance(child, dict):
                    _remap([child])
    _remap(components)

    return components


def generate_suggestions(user_id, content):
    """Generate 5 customized template suggestions.

    Args:
        user_id: for brand profile lookup
        content: dict from LLM with:
            - purpose: str
            - headline: str
            - subtitle: str
            - cta_text: str
            - features: list[str]
            - body_text: str
            - company: str
            - tone: str
            - image_queries: list[str]

    Returns:
        list of 5 suggestion dicts with customized components
    """
    # 1. Get brand
    brand = get_brand_context(user_id)

    # 2. Fetch images
    image_queries = content.get("image_queries", [])
    images = fetch_unsplash_images(image_queries) if image_queries else {}

    # 3. Find matching templates
    purpose = content.get("purpose", "email")
    tone = content.get("tone") or (brand or {}).get("tone", "")
    query_text = build_query(purpose, brand, tone)
    matches = search_templates(query_text, top_k=5)

    # 4. Fetch full templates from DB
    session = get_session()
    try:
        slugs = [m["slug"] for m in matches]
        templates = session.query(TemplateLibraryItem).filter(
            TemplateLibraryItem.slug.in_(slugs),
            TemplateLibraryItem.is_active == True,
        ).all()
        template_map = {t.slug: t for t in templates}
    finally:
        session.close()

    # 5. Customize each template
    suggestions = []
    for match in matches:
        t = template_map.get(match["slug"])
        if not t:
            continue

        customized = customize_template(t.components, content, images, brand)

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
