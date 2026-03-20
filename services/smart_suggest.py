"""Smart Suggestion v2.1 — Slot-based LLM content filling with brand awareness.

Flow:
1. Pinecone finds top 5 matching template layouts
2. Extract named slots from each template's component tree
3. ONE LLM call fills all slots with brand-aware content
4. Python injects content + brand header (logo+tagline) + images + colors
5. Returns 5 fully customized suggestions
"""

import json
import os
import uuid
import copy
import logging
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from openai import OpenAI
from config.database import get_session
from config.settings import DEEPSEEK_API_KEY
from models.brand_profile import BrandProfile
from models.template_library import TemplateLibraryItem
from services.suggestion import search_templates, build_query

logger = logging.getLogger(__name__)

UNSPLASH_API = "https://api.unsplash.com"
UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

_llm_client = None


def _get_llm():
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _llm_client


def _id():
    return f"sug-{uuid.uuid4().hex[:8]}"


# ─── Brand context ───

def get_brand_context(user_id):
    session = get_session()
    try:
        brand = session.query(BrandProfile).filter_by(user_id=user_id).first()
        return brand.to_dict() if brand else None
    finally:
        session.close()


# ─── Slot extraction ───

def extract_slots(components):
    """Extract named content slots from a template's component tree."""
    slots = {}
    counters = {"heading": 0, "text": 0, "button": 0, "image": 0}

    def _section_name(row_idx, total):
        if row_idx == 0:
            return "hero"
        if row_idx == total - 1:
            return "footer"
        if row_idx == total - 2:
            return "cta"
        return f"section_{row_idx}"

    def _walk(comp, section, path):
        ctype = comp.get("type", "")
        props = comp.get("props", {})

        if ctype in ("heading", "text", "button", "image"):
            counters[ctype] += 1
            idx = counters[ctype]

            # Name based on type + section + index
            if ctype == "heading":
                level = props.get("level", "h2")
                name = f"{section}_{ctype}_{idx}"
                current = props.get("content", "")
            elif ctype == "text":
                name = f"{section}_{ctype}_{idx}"
                current = props.get("content", "")
                # Clean HTML for display
                current = current.replace("&#10003;", "✓").replace("<strong>", "").replace("</strong>", "")
                current = current[:80]
            elif ctype == "button":
                name = f"{section}_{ctype}_{idx}"
                current = props.get("text", "")
            elif ctype == "image":
                name = f"{section}_{ctype}_{idx}"
                current = props.get("alt", "")

            slots[name] = {
                "type": ctype,
                "current_value": current[:80] if current else "",
                "path": list(path),
                "props_key": "content" if ctype in ("heading", "text") else ("text" if ctype == "button" else "src"),
            }

        for i, child in enumerate(comp.get("children", [])):
            if isinstance(child, dict):
                _walk(child, section, path + [i])

    total = len(components)
    for row_idx, row in enumerate(components):
        section = _section_name(row_idx, total)
        _walk(row, section, [row_idx])

    return slots


# ─── LLM content generation ───

def generate_slot_content(user_request, brand, template_slots_map):
    """ONE LLM call fills all slots for all 5 templates."""

    # Brand context
    brand_section = ""
    if brand:
        features_list = brand.get("features", [])
        features_str = ", ".join(f[:50] for f in features_list[:5]) if features_list else "not specified"
        brand_section = f"""
## Brand Profile (MUST use this information)
- Company Name: {brand.get('business_name', '')}
- Tagline: {brand.get('tagline', '')}
- Industry: {brand.get('industry', 'other')}
- Tone of Voice: {brand.get('tone', 'professional')}
- Website: {brand.get('website_url', '')}
- Key Features/Services: {features_str}

IMPORTANT: Use the company name "{brand.get('business_name', '')}" in the hero heading and footer.
Use the tagline "{brand.get('tagline', '')}" as hero subtitle or incorporate it naturally.
Write all content in a {brand.get('tone', 'professional')} tone.
Reference the company's features/services in checklist items and body text.
"""
    else:
        brand_section = "\nNo brand profile available. Use details from the user's request.\n"

    # Template slots
    templates_section = ""
    for slug, slots in template_slots_map.items():
        templates_section += f'\n### Template: "{slug}"\n'
        for slot_name, info in slots.items():
            if info["type"] == "image":
                templates_section += f'  {slot_name}: [IMAGE — suggest alt text]\n'
            else:
                current = info.get("current_value", "")
                templates_section += f'  {slot_name} ({info["type"]}): "{current}"\n'

    prompt = f"""You are an expert email copywriter. Write compelling content for email templates.

## User Request
"{user_request}"
{brand_section}
## Templates to Fill

For each template, fill EVERY slot with specific, relevant content.
{templates_section}

## Writing Rules
1. Hero heading: Include the company name. Make it exciting and specific to the email purpose.
2. Hero subtitle: Use the tagline or write a compelling one-liner that supports the heading.
3. Stat values: Use realistic, impressive numbers relevant to the business.
4. Stat labels: Short (2-3 words) describing what the number represents.
5. Checklist items: Specific benefits/features of the company, not generic text. Full sentences.
6. CTA buttons: Action verbs, max 4 words (e.g., "Start Free Trial", "Book Your Class").
7. Body text: 1-2 sentences, specific to the business, not filler.
8. Footer company: ALWAYS use the brand company name.
9. Footer address: Use a realistic address.
10. Image slots: Write descriptive alt text for the image.
11. Every piece of content must feel custom-written for THIS specific business.

## Response Format
Respond with ONLY valid JSON (no markdown, no code fences):
{{
  "templates": {{
    "<slug>": {{
      "<slot_name>": "content value",
      ...for every slot listed above
    }},
    ...for each template
  }},
  "image_queries": ["specific query 1", "specific query 2", "specific query 3"]
}}"""

    client = _get_llm()
    response = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=6000,
        temperature=0.7,
        messages=[
            {"role": "system", "content": "You are an expert email copywriter. Output ONLY valid JSON. No markdown fences, no explanation, just the JSON object."},
            {"role": "user", "content": prompt},
        ],
    )

    content = (response.choices[0].message.content or "{}").strip()

    # Clean markdown fences
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
    if content.endswith("```"):
        content = content[:-3].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"LLM JSON parse failed: {e}\nContent: {content[:500]}")
        return {"templates": {}, "image_queries": []}


# ─── Unsplash images ───

def fetch_unsplash_images(queries, per_query=2):
    if not UNSPLASH_KEY:
        return {}
    images = {}
    for q in queries[:3]:
        try:
            url = f"{UNSPLASH_API}/search/photos?{urlencode({'query': q, 'per_page': str(per_query)})}"
            req = Request(url, headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"})
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            results = data.get("results", [])
            for i, r in enumerate(results):
                img_url = r.get("urls", {}).get("regular", "")
                if img_url:
                    images[f"{q}_{i}"] = img_url
        except Exception as e:
            logger.warning(f"Unsplash failed for '{q}': {e}")
    return images


# ─── Fill slots into template ───

def fill_slots(components, slot_values, slots_meta, images, brand, company_override=None):
    """Fill slots with LLM content + images + brand colors + logo/tagline."""
    components = copy.deepcopy(components)
    image_urls = list(images.values())
    image_idx = [0]

    primary = (brand or {}).get("primary_color", "#2563EB")
    secondary = (brand or {}).get("secondary_color", "#1E40AF")
    company = company_override or (brand or {}).get("business_name", "")
    logo_url = (brand or {}).get("logo_url", "")
    tagline = (brand or {}).get("tagline", "")

    # Build path → slot_name lookup
    path_to_slot = {}
    for slot_name, meta in slots_meta.items():
        path_key = tuple(meta["path"])
        path_to_slot[path_key] = slot_name

    def _walk(comp, path):
        ctype = comp.get("type", "")
        props = comp.get("props", {})
        path_key = tuple(path)

        # Fill slot content
        slot_name = path_to_slot.get(path_key)
        if slot_name and slot_name in slot_values:
            value = slot_values[slot_name]
            if ctype == "heading":
                props["content"] = value
            elif ctype == "text":
                current = props.get("content", "")
                if "&#10003;" in current or "✓" in current:
                    props["content"] = f'<span style="color:{primary};font-weight:bold;font-size:16px;">&#10003;</span>&nbsp;&nbsp;{value}'
                elif "<a" in current and "nsubscribe" in current.lower():
                    pass  # Keep unsubscribe
                else:
                    props["content"] = value
            elif ctype == "button":
                props["text"] = value
            elif ctype == "image":
                # Use Unsplash image if available
                if image_urls and image_idx[0] < len(image_urls):
                    props["src"] = image_urls[image_idx[0]]
                    props["alt"] = value if isinstance(value, str) else props.get("alt", "")
                    image_idx[0] += 1

        # Apply brand colors — dark backgrounds become primary
        if ctype == "row":
            bg = props.get("backgroundColor", "")
            if _is_dark_color(bg):
                props["backgroundColor"] = primary

        if ctype == "column":
            bg = props.get("backgroundColor", "")
            if _is_dark_color(bg):
                props["backgroundColor"] = primary

        if ctype == "button":
            bg = props.get("backgroundColor", "")
            if bg and bg not in ("#FFFFFF", "#ffffff", "#6B7280", "#9CA3AF", "transparent"):
                props["backgroundColor"] = primary

        if ctype == "heading":
            color = props.get("color", "")
            if color and color not in ("#FFFFFF", "#ffffff", "#1a1a1a", "#333333",
                                       "#000000", "#1C1917", "#18181B", "#292524"):
                props["color"] = primary

        # Footer company name — always override
        if ctype == "text" and company:
            content = props.get("content", "")
            if "<strong>" in content:
                props["content"] = f"<strong>{company}</strong>"

        # Recurse
        for i, child in enumerate(comp.get("children", [])):
            if isinstance(child, dict):
                _walk(child, path + [i])

    for i, comp in enumerate(components):
        _walk(comp, [i])

    # Add brand header row if logo exists
    if logo_url:
        logo_row = {
            "id": _id(), "type": "row",
            "props": {"backgroundColor": "#FFFFFF", "padding": "0"},
            "styles": {}, "parentId": None, "visibility": True, "locked": False,
            "children": [{
                "id": _id(), "type": "column",
                "props": {"width": "100%", "padding": "15px 20px", "backgroundColor": "#FFFFFF"},
                "styles": {}, "parentId": None, "visibility": True, "locked": False,
                "children": [{
                    "id": _id(), "type": "image",
                    "props": {"src": logo_url, "alt": f"{company} logo", "width": "150px", "height": "auto"},
                    "styles": {}, "parentId": None, "children": [], "visibility": True, "locked": False,
                }],
            }],
        }
        components.insert(0, logo_row)

    # Remap all IDs
    def _remap(items):
        for comp in items:
            comp["id"] = _id()
            for child in comp.get("children", []):
                if isinstance(child, dict):
                    _remap([child])
    _remap(components)

    return components


def _is_dark_color(hex_color):
    """Check if a hex color is dark (for background replacement)."""
    if not hex_color or hex_color in ("transparent", "", "#FFFFFF", "#ffffff"):
        return False
    try:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return False
        r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance < 0.45
    except (ValueError, IndexError):
        return False


# ─── Main: Generate Suggestions ───

def generate_suggestions(user_id, user_request, status_callback=None):
    """Generate 5 customized template suggestions."""
    if isinstance(user_request, dict):
        request_text = user_request.get("purpose", user_request.get("user_request", str(user_request)))
    else:
        request_text = str(user_request)

    def _status(msg):
        if status_callback:
            status_callback(msg)

    # 1. Brand
    _status("Loading your brand profile...")
    brand = get_brand_context(user_id)

    # 2. Pinecone search
    _status("Finding matching template layouts...")
    query_text = build_query(request_text, brand)
    matches = search_templates(query_text, top_k=5)

    # 3. Fetch templates
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

    # 4. Extract slots
    _status("Analyzing template structures...")
    template_slots_map = {}
    for match in matches:
        t = template_map.get(match["slug"])
        if t:
            template_slots_map[match["slug"]] = extract_slots(t.components)

    if not template_slots_map:
        return [], query_text

    # 5. LLM fills slots
    _status("Writing personalized content for your brand...")
    llm_result = generate_slot_content(request_text, brand, template_slots_map)
    template_contents = llm_result.get("templates", {})
    image_queries = llm_result.get("image_queries", [])

    # 6. Fetch images
    _status("Finding perfect images...")
    images = fetch_unsplash_images(image_queries) if image_queries else {}

    # 7. Fill slots
    _status("Applying your brand to templates...")
    suggestions = []
    for match in matches:
        slug = match["slug"]
        t = template_map.get(slug)
        if not t:
            continue

        slot_values = template_contents.get(slug, {})
        slots_meta = template_slots_map.get(slug, {})

        customized = fill_slots(t.components, slot_values, slots_meta, images, brand)

        suggestions.append({
            "slug": slug,
            "name": t.name,
            "description": t.description,
            "industry": t.industry,
            "purpose": t.purpose,
            "tone": t.tone,
            "score": match["score"],
            "components": customized,
        })

    return suggestions, query_text
