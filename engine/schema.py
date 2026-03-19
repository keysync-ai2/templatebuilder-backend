"""Validate emailBuilder component tree JSON against the expected schema.

The canonical format is nested: children contain inline component objects.
This matches the frontend and DB storage format.

normalize_tree() and to_frontend_format() remain for backward compatibility.
"""

import copy

VALID_COMPONENT_TYPES = {
    "row", "column", "text", "heading", "button",
    "image", "divider", "spacer", "section", "container",
}

CONTENT_TYPES = {"text", "heading", "button", "image", "divider", "spacer"}
LAYOUT_TYPES = {"row", "column", "section", "container"}

# Which parent types are allowed for each component type
VALID_PARENTS = {
    "row": {None, "section", "container"},
    "column": {"row"},
    "text": {"column", "section", "container"},
    "heading": {"column", "section", "container"},
    "button": {"column", "section", "container"},
    "image": {"column", "section", "container"},
    "divider": {"column", "section", "container"},
    "spacer": {"column", "section", "container"},
    "section": {None, "column", "container"},
    "container": {None, "section"},
}

REQUIRED_FIELDS = {"id", "type", "props", "children"}


def find_in_tree(components: list, target_id: str):
    """Find a component by ID in a nested tree.

    Returns (component, parent, children_list) where:
        - component: the matched dict
        - parent: the parent dict (None if root)
        - children_list: the list the component lives in (for mutation)

    Returns (None, None, None) if not found.
    """
    def _search(items, parent):
        for comp in items:
            if not isinstance(comp, dict):
                continue
            if comp.get("id") == target_id:
                return (comp, parent, items)
            children = comp.get("children", [])
            if isinstance(children, list):
                result = _search(children, comp)
                if result[0] is not None:
                    return result
        return (None, None, None)

    return _search(components, None)


def _is_nested(components: list) -> bool:
    """Check if any component has inline objects in its children array."""
    for comp in components:
        if not isinstance(comp, dict):
            continue
        children = comp.get("children", [])
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    return True
    return False


def normalize_tree(template: dict) -> dict:
    """Normalize a component tree to flat format.

    If components use nested children (inline objects), flatten them to a
    flat array with string ID references. Sets parentId on each child.

    Returns a new dict (does not mutate input).
    """
    if not isinstance(template, dict):
        return template

    components = template.get("components")
    if not isinstance(components, list):
        return template

    if not _is_nested(components):
        return template  # already flat

    template = copy.deepcopy(template)
    flat = []

    def _flatten(comp: dict, parent_id=None):
        comp = dict(comp)  # shallow copy
        if parent_id is not None:
            comp["parentId"] = parent_id
        elif "parentId" not in comp:
            comp["parentId"] = None

        children = comp.get("children", [])
        child_ids = []

        for child in children:
            if isinstance(child, dict):
                # Inline child object — extract and recurse
                child_id = child.get("id")
                if child_id:
                    child_ids.append(child_id)
                    _flatten(child, comp["id"])
            elif isinstance(child, str):
                child_ids.append(child)

        comp["children"] = child_ids

        # Ensure required fields exist
        comp.setdefault("styles", {})
        comp.setdefault("visibility", True)
        comp.setdefault("locked", False)

        flat.append(comp)

    for comp in components:
        if not isinstance(comp, dict):
            continue
        parent_id = comp.get("parentId")
        _flatten(comp, parent_id)

    template["components"] = flat
    return template


def to_frontend_format(template: dict) -> dict:
    """Convert a flat component tree to the nested frontend format.

    This is the reverse of normalize_tree(). The frontend expects:
    - children: inline component objects (not string IDs)
    - columns: count of column children on rows
    - styles: {} on every component
    - visibility: true on every component
    - locked: false on every component
    - parentId on every component

    Returns a new dict (does not mutate input).
    """
    if not isinstance(template, dict):
        return template

    components = template.get("components")
    if not isinstance(components, list) or len(components) == 0:
        return template

    # If already nested, just ensure required fields
    if _is_nested(components):
        template = copy.deepcopy(template)
        _ensure_frontend_fields(template["components"])
        return template

    template = copy.deepcopy(template)
    by_id = {c["id"]: c for c in template["components"]}

    def _build_nested(comp: dict) -> dict:
        node = dict(comp)
        child_ids = node.get("children", [])
        nested_children = []
        for cid in child_ids:
            if isinstance(cid, str) and cid in by_id:
                nested_children.append(_build_nested(by_id[cid]))
        node["children"] = nested_children

        # Add columns count for rows
        if node["type"] == "row":
            col_count = sum(1 for c in nested_children if c.get("type") == "column")
            node["props"].setdefault("columns", col_count or 1)

        # Ensure required frontend fields
        node.setdefault("styles", {})
        node.setdefault("visibility", True)
        node.setdefault("locked", False)
        node.setdefault("parentId", None)

        return node

    # Build nested tree from roots
    roots = [c for c in template["components"] if c.get("parentId") is None]
    nested = [_build_nested(comp) for comp in roots]

    template["components"] = nested
    return template


def _ensure_frontend_fields(components: list):
    """Recursively ensure all components have styles, visibility, locked, columns."""
    for comp in components:
        if not isinstance(comp, dict):
            continue
        comp.setdefault("styles", {})
        comp.setdefault("visibility", True)
        comp.setdefault("locked", False)
        comp.setdefault("parentId", None)
        if comp.get("type") == "row":
            children = comp.get("children", [])
            col_count = sum(
                1 for c in children
                if isinstance(c, dict) and c.get("type") == "column"
            )
            comp["props"].setdefault("columns", col_count or 1)
        children = comp.get("children", [])
        if isinstance(children, list):
            nested_children = [c for c in children if isinstance(c, dict)]
            if nested_children:
                _ensure_frontend_fields(nested_children)


def validate_tree(template: dict) -> list[str]:
    """Validate a nested component tree. Returns list of error strings (empty = valid).

    Walks the tree recursively. Checks:
    - components array exists and is non-empty
    - All required fields present on each component
    - Valid component types
    - Parent-child hierarchy rules
    - No duplicate IDs
    - Children must be inline dicts (string IDs = error)
    """
    errors = []

    if not isinstance(template, dict):
        return ["Template must be a dict"]

    components = template.get("components")
    if not isinstance(components, list):
        return ["Template must have a 'components' array"]

    if len(components) == 0:
        return ["Template has no components"]

    seen_ids = set()

    def _validate_component(comp, parent_type, depth):
        if not isinstance(comp, dict):
            errors.append(f"Component is not a dict: {comp}")
            return

        cid = comp.get("id")
        if not cid:
            errors.append(f"Component missing 'id': {comp}")
            return

        if cid in seen_ids:
            errors.append(f"Duplicate component id: {cid}")
            return
        seen_ids.add(cid)

        # Required fields
        missing = REQUIRED_FIELDS - set(comp.keys())
        if missing:
            errors.append(f"[{cid}] Missing fields: {missing}")
            return

        ctype = comp["type"]
        if ctype not in VALID_COMPONENT_TYPES:
            errors.append(f"[{cid}] Invalid type: {ctype}")
            return

        # Parent type valid
        allowed = VALID_PARENTS.get(ctype, set())
        if parent_type not in allowed:
            errors.append(
                f"[{cid}] type '{ctype}' cannot be child of '{parent_type}'"
            )

        # Children must be a list of dicts (nested), not string IDs
        children = comp.get("children", [])
        if not isinstance(children, list):
            errors.append(f"[{cid}] 'children' must be a list")
            return

        for child in children:
            if isinstance(child, str):
                errors.append(
                    f"[{cid}] child is a string ID '{child}' — expected nested object"
                )
                continue
            _validate_component(child, ctype, depth + 1)

    for comp in components:
        _validate_component(comp, None, 0)

    return errors
