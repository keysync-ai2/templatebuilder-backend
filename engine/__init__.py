"""Email HTML Engine — Convert emailBuilder JSON to production-ready email HTML.

Public API:
    build_html(template) → str     — JSON component tree → email HTML with MSO
    validate_tree(template) → list  — Validate component tree, returns errors
"""

from engine.renderer import render_html
from engine.schema import validate_tree, normalize_tree, to_frontend_format, find_in_tree
from engine.builder import (
    get_root_components,
    get_children,
    get_subtree,
    add_component,
    remove_component,
    inject_preset,
)


def build_html(template: dict) -> str:
    """Convert emailBuilder component tree JSON to production-ready email HTML.

    Args:
        template: Dict with "components" array and optional metadata
                  (templateName, templateSubject, etc.)

    Returns:
        Complete HTML string ready for email sending.

    Raises:
        ValueError: If the component tree has validation errors.
    """
    errors = validate_tree(template)
    if errors:
        raise ValueError(f"Invalid component tree: {'; '.join(errors)}")
    return render_html(template)


__all__ = [
    "build_html",
    "validate_tree",
    "render_html",
    "get_root_components",
    "get_children",
    "get_subtree",
    "add_component",
    "remove_component",
    "inject_preset",
    "normalize_tree",
    "to_frontend_format",
    "find_in_tree",
]
