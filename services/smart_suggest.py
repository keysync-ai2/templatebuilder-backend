"""Smart Suggestion v2 — Slot-based LLM content filling.

Flow:
1. Pinecone finds top 5 matching template layouts
2. Extract named slots from each template's component tree
3. ONE LLM call fills all slots for all 5 templates with brand-aware content
4. Python injects content + Unsplash images + brand colors
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


# ─── Step 1: Fetch brand profile ───

def get_brand_context(user_id):
    session = get_session()
    try:
        brand = session.query(BrandProfile).filter_by(user_id=user_id).first()
        return brand.to_dict() if brand else None
    finally:
        session.close()


# ─── Step 2: Extract slots from template ───

def extract_slots(components):
    """Extract named content slots from a template's component tree.

    Returns dict of {slot_name: {type, current_value, path, description}}
    """
    slots = {}
    image_count = [0]
    heading_count = {"h1": 0, "h2": 0, "h3": 0}
    text_count = [0]
    button_count = [0]

    # Detect section type by row position and content
    def _guess_section(row_idx, total_rows, comp):
        if row_idx == 0:
            return "hero"
        if row_idx == total_rows - 1:
            return "footer"
        # Check children for clues
        children = comp.get("children", [])
        if len(children) >= 3:
            return "stats" if any(_has_type(c, "heading") for c in children) else "features"
        return "content"

    def _has_type(comp, ctype):
        if comp.get("type") == ctype:
            return True
        for child in comp.get("children", []):
            if isinstance(child, dict) and _has_type(child, ctype):
                return True
        return False

    def _walk(comp, section, path):
        ctype = comp.get("type", "")
        props = comp.get("props", {})

        if ctype == "heading":
            level = props.get("level", "h2")
            heading_count[level] = heading_count.get(level, 0) + 1
            idx = heading_count[level]

            if level == "h1":
                name = f"{section}_heading"
            elif section == "hero":
                name = f"{section}_subtitle_heading" if idx > 1 else f"{section}_heading"
            elif section == "stats":
                name = f"stat_{idx}_value"
            elif section == "footer":
                name = f"footer_heading"
            else:
                name = f"{section}_heading_{idx}"

            slots[name] = {
                "type": "heading",
                "level": level,
                "current_value": props.get("content", ""),
                "path": list(path),
            }

        elif ctype == "text":
            text_count[0] += 1
            content = props.get("content", "")

            if section == "stats":
                # Stats labels alternate with values
                stat_h = [k for k in slots if k.startswith("stat_") and k.endswith("_value")]
                idx = len(stat_h)
                name = f"stat_{idx}_label"
            elif section == "footer":
                if "<strong>" in content:
                    name = "footer_company"
                elif "unsubscribe" in content.lower() or "<a" in content.lower():
                    name = "footer_unsubscribe"
                else:
                    name = f"footer_text_{text_count[0]}"
            elif section == "hero":
                name = "hero_subtitle"
            elif "✓" in content or "&#10003;" in content or "check" in section:
                check_idx = len([k for k in slots if k.startswith("check_")]) + 1
                name = f"check_{check_idx}"
            else:
                name = f"{section}_text_{text_count[0]}"

            # Skip duplicates
            if name in slots:
                name = f"{name}_{text_count[0]}"

            slots[name] = {
                "type": "text",
                "current_value": content[:100],
                "path": list(path),
            }

        elif ctype == "button":
            button_count[0] += 1
            if section == "hero":
                name = "hero_button"
            elif button_count[0] <= 2 and section != "footer":
                name = f"cta_button_{button_count[0]}" if button_count[0] > 1 else "cta_button"
            else:
                name = f"{section}_button_{button_count[0]}"

            if name in slots:
                name = f"{name}_{button_count[0]}"

            slots[name] = {
                "type": "button",
                "current_value": props.get("text", ""),
                "path": list(path),
            }

        elif ctype == "image":
            image_count[0] += 1
            name = f"image_{image_count[0]}"
            slots[name] = {
                "type": "image",
                "current_value": props.get("alt", ""),
                "path": list(path),
            }

        # Recurse
        for i, child in enumerate(comp.get("children", [])):
            if isinstance(child, dict):
                child_section = section
                # Detect section changes at row level
                if ctype == "row" and comp.get("parentId") is None:
                    pass  # section already set
                _walk(child, child_section, path + [i])

    total_rows = len(components)
    for row_idx, row_comp in enumerate(components):
        section = _guess_section(row_idx, total_rows, row_comp)
        _walk(row_comp, section, [row_idx])

    return slots


# ─── Step 3: LLM fills all slots ───

def generate_slot_content(user_request, brand, template_slots_map):
    """Call LLM once to fill all slots for all templates.

    Args:
        user_request: raw user message
        brand: brand profile dict or None
        template_slots_map: {slug: {slot_name: {type, current_value}}}

    Returns: {slug: {slot_name: value}, "image_queries": [...]}
    """
    # Build brand context
    brand_text = "No brand profile set."
    if brand:
        features = ", ".join(brand.get("features", [])) or "not specified"
        brand_text = f"""Brand Profile:
- Company: {brand.get('business_name', 'Unknown')}
- Tagline: {brand.get('tagline', '')}
- Industry: {brand.get('industry', 'other')}
- Tone: {brand.get('tone', 'professional')}
- Primary Color: {brand.get('primary_color', '#2563EB')}
- Secondary Color: {brand.get('secondary_color', '#1E40AF')}
- Key Features: {features}
- Website: {brand.get('website_url', '')}"""

    # Build template slot descriptions
    templates_text = ""
    for slug, slots in template_slots_map.items():
        templates_text += f'\nTemplate: "{slug}"\nSlots to fill:\n'
        for slot_name, slot_info in slots.items():
            if slot_info["type"] == "image":
                continue  # Images handled separately
            stype = slot_info["type"]
            current = slot_info.get("current_value", "")[:60]
            templates_text += f'  - {slot_name} ({stype}): currently "{current}"\n'

    prompt = f"""You are an expert email content writer. A user wants to create an email.
Fill every slot below with compelling, on-brand content tailored to their request.

{brand_text}

User Request: "{user_request}"

{templates_text}

IMPORTANT:
- Write content that matches the user's specific request and brand
- Use the brand's company name in footers
- Match the brand's tone (professional/casual/friendly/urgent/playful/minimal)
- For stat values, use realistic impressive numbers
- For buttons, use action-oriented text (max 4 words)
- For headings, be concise and impactful
- Also suggest 3 Unsplash image search queries that would match this email's visual style

Respond ONLY with valid JSON in this exact format:
{{
  "templates": {{
    "{list(template_slots_map.keys())[0]}": {{
      "slot_name": "content value",
      ...
    }},
    ...
  }},
  "image_queries": ["query1", "query2", "query3"]
}}"""

    client = _get_llm()
    response = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=4096,
        messages=[
            {"role": "system", "content": "You are an email content writer. Respond only with valid JSON. No markdown, no code blocks, just raw JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content or "{}"

    # Clean up — remove markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}\nContent: {content[:500]}")
        return {"templates": {}, "image_queries": []}


# ─── Step 4: Fetch images ───

def fetch_unsplash_images(queries, per_query=1):
    if not UNSPLASH_KEY:
        return {}
    images = {}
    for q in queries[:3]:  # Max 3 queries
        try:
            url = f"{UNSPLASH_API}/search/photos?{urlencode({'query': q, 'per_page': str(per_query)})}"
            req = Request(url, headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"})
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            results = data.get("results", [])
            if results:
                images[q] = results[0].get("urls", {}).get("regular", "")
        except Exception as e:
            logger.warning(f"Unsplash failed for '{q}': {e}")
    return images


# ─── Step 5: Fill slots into template ───

def fill_slots(components, slot_values, slots_meta, images, brand):
    """Fill extracted slots with LLM content + images + brand colors."""
    components = copy.deepcopy(components)
    image_urls = list(images.values())
    image_idx = [0]

    primary = (brand or {}).get("primary_color", "#2563EB")
    secondary = (brand or {}).get("secondary_color", "#1E40AF")
    company = (brand or {}).get("business_name", "")

    # Build path → slot_name lookup
    path_to_slot = {}
    for slot_name, meta in slots_meta.items():
        path_key = tuple(meta["path"])
        path_to_slot[path_key] = slot_name

    def _walk(comp, path):
        ctype = comp.get("type", "")
        props = comp.get("props", {})
        path_key = tuple(path)

        slot_name = path_to_slot.get(path_key)
        if slot_name and slot_name in slot_values:
            value = slot_values[slot_name]

            if ctype == "heading":
                props["content"] = value
            elif ctype == "text":
                # Preserve HTML structure for footer/checklist
                current = props.get("content", "")
                if "&#10003;" in current or "✓" in current:
                    check_color = primary
                    props["content"] = f'<span style="color:{check_color};font-weight:bold;">&#10003;</span>&nbsp;&nbsp;{value}'
                elif "<strong>" in current and company:
                    props["content"] = f"<strong>{company}</strong>"
                elif "<a" in current and "unsubscribe" in current.lower():
                    pass  # Keep unsubscribe link
                else:
                    props["content"] = value
            elif ctype == "button":
                props["text"] = value

        # Apply brand colors
        if ctype == "row":
            bg = props.get("backgroundColor", "")
            if bg and bg not in ("#FFFFFF", "#F8F9FA", "#F0FDF4", "#ECFDF5", "#EFF6FF",
                                  "#FFF1F2", "#FEF2F2", "#FFFBEB", "#FEF9C3", "#E0F2FE",
                                  "#CFFAFE", "#EDE9FE", "#D1FAE5", "#FFE4E6", "#FDF2F8",
                                  "#FDF4FF", "#FEF3C7", "#F5F3FF", "#F3F4F6", "#F0FDF4",
                                  "#F0FDFA", "#FAFAF9", "#DCFCE7", "#FFF7ED",
                                  "transparent", "", "#FFFFFF"):
                props["backgroundColor"] = primary

        if ctype == "column":
            bg = props.get("backgroundColor", "")
            if bg and bg not in ("#FFFFFF", "transparent", "", "#FFFFFF") and bg == props.get("backgroundColor"):
                # Only override if it was a dark color (hero/footer)
                if bg.startswith("#0") or bg.startswith("#1") or bg.startswith("#2") or bg.startswith("#3") or bg.startswith("#4") or bg.startswith("#5"):
                    props["backgroundColor"] = primary

        if ctype == "button":
            bg = props.get("backgroundColor", "")
            if bg and bg not in ("#FFFFFF", "#ffffff", "#6B7280", "#9CA3AF"):
                props["backgroundColor"] = primary

        if ctype == "heading":
            color = props.get("color", "")
            # Only change accent-colored headings, keep white/dark as-is
            if color and color not in ("#FFFFFF", "#ffffff", "#1a1a1a", "#333333", "#000000", "#1C1917", "#18181B"):
                props["color"] = primary

        if ctype == "image":
            if image_urls and image_idx[0] < len(image_urls):
                props["src"] = image_urls[image_idx[0]]
                image_idx[0] += 1

        # Recurse
        for i, child in enumerate(comp.get("children", [])):
            if isinstance(child, dict):
                _walk(child, path + [i])

    for i, comp in enumerate(components):
        _walk(comp, [i])

    # Remap IDs
    def _remap(items):
        for comp in items:
            comp["id"] = f"sug-{uuid.uuid4().hex[:8]}"
            for child in comp.get("children", []):
                if isinstance(child, dict):
                    _remap([child])
    _remap(components)

    return components


# ─── Main: Generate Suggestions ───

def generate_suggestions(user_id, user_request, status_callback=None):
    """Generate 5 customized template suggestions using slot-based filling.

    Args:
        user_id: for brand profile
        user_request: raw user message (str) or dict with "purpose" key
        status_callback: optional fn(message) to update progress

    Returns: (suggestions_list, query_text)
    """
    # Handle both string and dict input
    if isinstance(user_request, dict):
        request_text = user_request.get("purpose", str(user_request))
    else:
        request_text = str(user_request)

    def _status(msg):
        if status_callback:
            status_callback(msg)

    # 1. Get brand
    _status("Loading your brand profile...")
    brand = get_brand_context(user_id)

    # 2. Pinecone search
    _status("Finding matching template layouts...")
    query_text = build_query(request_text, brand)
    matches = search_templates(query_text, top_k=5)

    # 3. Fetch templates from DB
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

    # 4. Extract slots from each template
    _status("Analyzing template structures...")
    template_slots_map = {}
    for match in matches:
        t = template_map.get(match["slug"])
        if t:
            template_slots_map[match["slug"]] = extract_slots(t.components)

    if not template_slots_map:
        return [], query_text

    # 5. LLM fills all slots
    _status("Writing customized content for your templates...")
    llm_result = generate_slot_content(request_text, brand, template_slots_map)
    template_contents = llm_result.get("templates", {})
    image_queries = llm_result.get("image_queries", [])

    # 6. Fetch images
    _status("Finding perfect images...")
    images = fetch_unsplash_images(image_queries) if image_queries else {}

    # 7. Fill slots into each template
    _status("Customizing your templates...")
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
