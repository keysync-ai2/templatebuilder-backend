"""Build and manipulate emailBuilder component trees programmatically.

All functions operate on the nested format (children = inline dicts).
"""

import uuid
import copy

from engine.schema import find_in_tree, _is_nested, to_frontend_format


def _new_id(prefix: str = "comp") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _remap_ids(components: list[dict]) -> list[dict]:
    """Deep-copy nested components and assign new unique IDs throughout the tree."""
    components = copy.deepcopy(components)
    old_to_new = {}

    def _collect_ids(items):
        for comp in items:
            old_id = comp["id"]
            new_id = _new_id(comp.get("type", "comp"))
            old_to_new[old_id] = new_id
            comp["id"] = new_id
            # Update parentId if it maps
            if comp.get("parentId") in old_to_new:
                comp["parentId"] = old_to_new[comp["parentId"]]
            for child in comp.get("children", []):
                if isinstance(child, dict):
                    _collect_ids([child])

    _collect_ids(components)

    # Second pass: fix parentId references that were collected after the parent
    def _fix_parent_ids(items):
        for comp in items:
            if comp.get("parentId") in old_to_new:
                comp["parentId"] = old_to_new[comp["parentId"]]
            for child in comp.get("children", []):
                if isinstance(child, dict):
                    _fix_parent_ids([child])

    _fix_parent_ids(components)
    return components


def get_root_components(template: dict) -> list[dict]:
    """Get top-level components, ordered by appearance."""
    return template.get("components", [])


def get_children(template: dict, parent_id: str) -> list[dict]:
    """Get ordered children of a component."""
    comp, _, _ = find_in_tree(template.get("components", []), parent_id)
    if not comp:
        return []
    return [c for c in comp.get("children", []) if isinstance(c, dict)]


def get_subtree(template: dict, component_id: str) -> list[dict]:
    """Get a component and all its descendants as a flat list."""
    comp, _, _ = find_in_tree(template.get("components", []), component_id)
    if not comp:
        return []

    result = []

    def _collect(c):
        result.append(c)
        for child in c.get("children", []):
            if isinstance(child, dict):
                _collect(child)

    _collect(comp)
    return result


def add_component(template: dict, parent_id: str, component: dict, position: int = -1) -> dict:
    """Add a component to the tree under a parent. Returns updated template."""
    template = copy.deepcopy(template)
    component = copy.deepcopy(component)
    component["parentId"] = parent_id

    if parent_id is None:
        # Add as root component
        if position < 0:
            template["components"].append(component)
        else:
            template["components"].insert(position, component)
    else:
        parent, _, _ = find_in_tree(template["components"], parent_id)
        if not parent:
            raise ValueError(f"Parent '{parent_id}' not found")
        children = parent.get("children", [])
        if position < 0:
            children.append(component)
        else:
            children.insert(position, component)
        parent["children"] = children

    return template


def remove_component(template: dict, component_id: str) -> dict:
    """Remove a component and its descendants from the tree. Returns updated template."""
    template = copy.deepcopy(template)
    comp, parent, children_list = find_in_tree(template["components"], component_id)

    if not comp:
        return template

    # Remove from whichever list it lives in (parent's children or root components)
    children_list[:] = [c for c in children_list if not (isinstance(c, dict) and c.get("id") == component_id)]

    return template


def inject_preset(template: dict, preset_json: dict, position: int = -1) -> dict:
    """Inject a pre-built block's rows into a template at a given row position.

    Handles both flat and nested preset formats. The preset's components get
    new IDs to avoid conflicts.

    Args:
        template: The target template dict (nested format)
        preset_json: Preset dict with a "components" array
        position: Row index to insert at (0-based). -1 = append at end.

    Returns:
        Updated template with preset injected.
    """
    template = copy.deepcopy(template)
    preset_components = preset_json.get("components", [])

    # If preset is flat format, convert to nested first
    if preset_components and not _is_nested(preset_components):
        nested_preset = to_frontend_format({"components": preset_components})
        preset_components = nested_preset.get("components", [])

    preset_components = _remap_ids(preset_components)

    # Set root preset components to parentId=None
    for comp in preset_components:
        comp["parentId"] = None

    # Apply variable substitution
    variables = preset_json.get("variables", {})
    defaults = {k: v.get("default", "") for k, v in variables.items() if isinstance(v, dict)}
    customizations = preset_json.get("customizations", {})
    merged_vars = {**defaults, **customizations}

    if merged_vars:
        def _substitute(items):
            for comp in items:
                props = comp.get("props", {})
                for key, val in props.items():
                    if isinstance(val, str):
                        for var_name, var_val in merged_vars.items():
                            val = val.replace("{{" + var_name + "}}", str(var_val))
                        props[key] = val
                for child in comp.get("children", []):
                    if isinstance(child, dict):
                        _substitute([child])
        _substitute(preset_components)

    # Insert preset root components into template
    if position < 0:
        template["components"].extend(preset_components)
    else:
        for i, comp in enumerate(preset_components):
            template["components"].insert(position + i, comp)

    return template
