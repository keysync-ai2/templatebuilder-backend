"""Command Lambda — /api/chat/command route.

Handles slash commands instantly (no LLM call).
POST /api/chat/command { command, args }
"""

import json
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from models.brand_profile import BrandProfile


VALID_TONES = {"professional", "casual", "friendly", "urgent", "playful", "minimal"}
VALID_INDUSTRIES = {"saas", "ecommerce", "health", "food", "education", "events", "real_estate", "agency", "other"}


def handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    body = json.loads(event.get("body") or "{}")
    headers = event.get("headers") or {}

    if method == "OPTIONS":
        return options_response()

    payload = verify_token(headers)
    if not payload:
        return error(401, "UNAUTHORIZED", "Invalid or missing token")
    user_id = payload["sub"]

    if method == "POST":
        return _handle_command(body, user_id)

    return error(404, "NOT_FOUND", "Route not found")


def _handle_command(body: dict, user_id: str):
    command = (body.get("command") or "").strip().lower()
    args = (body.get("args") or "").strip()

    if not command:
        return error(400, "VALIDATION_ERROR", "command is required")

    # Route commands
    if command == "presets":
        return _cmd_presets(args)
    elif command == "brand_show" or command == "brand show":
        return _cmd_brand_show(user_id)
    elif command == "suggest":
        return _cmd_suggest(args, user_id)
    elif command == "tone":
        return _cmd_tone(args, user_id)
    elif command == "industry":
        return _cmd_industry(args, user_id)
    elif command == "export":
        return _cmd_export(user_id)
    else:
        return success(200, {
            "message": f"Unknown command: `/{command}`. Type `/help` to see available commands.",
            "widget_type": None,
            "widget_data": None,
        })


def _cmd_presets(category):
    """List available presets, optionally filtered by category."""
    from engine.presets import local_preset_loader

    presets = local_preset_loader("__list__", category=category if category else None)

    if not presets:
        return success(200, {
            "message": f"No presets found{' for category: ' + category if category else ''}.",
            "widget_type": None,
            "widget_data": None,
        })

    # Format as markdown table
    msg = f"## Available Presets ({len(presets)})\n\n"
    msg += "| Name | Category | Description |\n"
    msg += "|------|----------|-------------|\n"
    for p in presets:
        msg += f"| **{p['name']}** | {p['category']} | {p['description'][:60]}... |\n"
    msg += f"\nUse these presets in the editor's **Blocks** tab, or ask me to create a template."

    return success(200, {
        "message": msg,
        "widget_type": None,
        "widget_data": None,
    })


def _cmd_brand_show(user_id):
    """Show the user's brand profile."""
    session = get_session()
    try:
        brand = session.query(BrandProfile).filter_by(user_id=user_id).first()
        if not brand:
            return success(200, {
                "message": "No brand profile set up yet. Go to **/brand** to create one, or type `/brand` to open the editor.",
                "widget_type": None,
                "widget_data": None,
            })

        d = brand.to_dict()
        features = ", ".join(d.get("features", [])[:5]) or "None set"

        msg = f"## Your Brand Profile\n\n"
        msg += f"| Field | Value |\n"
        msg += f"|-------|-------|\n"
        msg += f"| **Company** | {d.get('business_name', '—')} |\n"
        msg += f"| **Tagline** | {d.get('tagline', '—')} |\n"
        msg += f"| **Industry** | {d.get('industry', '—')} |\n"
        msg += f"| **Tone** | {d.get('tone', '—')} |\n"
        msg += f"| **Primary Color** | {d.get('primary_color', '—')} |\n"
        msg += f"| **Secondary Color** | {d.get('secondary_color', '—')} |\n"
        msg += f"| **Website** | {d.get('website_url', '—')} |\n"
        msg += f"| **Features** | {features} |\n"
        msg += f"\nEdit your brand at [/brand](/brand)."

        return success(200, {
            "message": msg,
            "widget_type": None,
            "widget_data": None,
        })
    finally:
        session.close()


def _cmd_suggest(args, user_id):
    """Get template suggestions."""
    if not args:
        return success(200, {
            "message": "Please provide a description. Example: `/suggest welcome email for my SaaS product`",
            "widget_type": None,
            "widget_data": None,
        })

    from services.smart_suggest import generate_suggestions
    try:
        suggestions, query = generate_suggestions(user_id, args)
        return success(200, {
            "message": f"Found {len(suggestions)} templates matching: *{args}*",
            "widget_type": "suggestion-cards",
            "widget_data": {"suggestions": suggestions, "query": query},
        })
    except Exception as e:
        return success(200, {
            "message": f"Suggestion failed: {str(e)}",
            "widget_type": None,
            "widget_data": None,
        })


def _cmd_tone(args, user_id):
    """Set brand tone."""
    if not args or args.lower() not in VALID_TONES:
        return success(200, {
            "message": f"Please specify a valid tone: `{', '.join(sorted(VALID_TONES))}`. Example: `/tone casual`",
            "widget_type": None,
            "widget_data": None,
        })

    session = get_session()
    try:
        brand = session.query(BrandProfile).filter_by(user_id=user_id).first()
        if not brand:
            return success(200, {
                "message": "No brand profile set up yet. Create one first at [/brand](/brand).",
                "widget_type": None,
                "widget_data": None,
            })
        old_tone = brand.tone
        brand.tone = args.lower()
        session.commit()
        return success(200, {
            "message": f"Tone updated: **{old_tone}** → **{args.lower()}**. Future templates will use this tone.",
            "widget_type": None,
            "widget_data": None,
        })
    finally:
        session.close()


def _cmd_industry(args, user_id):
    """Set brand industry."""
    if not args or args.lower() not in VALID_INDUSTRIES:
        return success(200, {
            "message": f"Please specify a valid industry: `{', '.join(sorted(VALID_INDUSTRIES))}`. Example: `/industry saas`",
            "widget_type": None,
            "widget_data": None,
        })

    session = get_session()
    try:
        brand = session.query(BrandProfile).filter_by(user_id=user_id).first()
        if not brand:
            return success(200, {
                "message": "No brand profile set up yet. Create one first at [/brand](/brand).",
                "widget_type": None,
                "widget_data": None,
            })
        old = brand.industry
        brand.industry = args.lower()
        session.commit()
        return success(200, {
            "message": f"Industry updated: **{old}** → **{args.lower()}**. Template suggestions will now prioritize {args.lower()} templates.",
            "widget_type": None,
            "widget_data": None,
        })
    finally:
        session.close()


def _cmd_export(user_id):
    """Export current template — placeholder for now."""
    return success(200, {
        "message": "To export your template as HTML, open it in the editor and use the **Production HTML** tab in the bottom panel. You can copy or download the email-safe HTML from there.",
        "widget_type": None,
        "widget_data": None,
    })
