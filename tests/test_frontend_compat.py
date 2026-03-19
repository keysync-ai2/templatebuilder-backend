"""Test that backend-generated JSON is compatible with frontend htmlGenerator.js.

Simulates the frontend's componentToHTML() and generateEmailHTML() logic
exactly as written in frontend/components/email-builder/htmlGenerator.js.

Run: python -m tests.test_frontend_compat
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Replicate frontend htmlGenerator.js logic exactly in Python
# ---------------------------------------------------------------------------

def component_to_html(component):
    """Exact port of frontend componentToHTML(component)."""
    if not component:
        return ""

    ctype = component.get("type", "")
    props = component.get("props", {})
    children = component.get("children", [])

    if ctype == "text":
        return (
            f'<div style="font-size: {props.get("fontSize")}px; '
            f'color: {props.get("color")}; '
            f'font-family: {props.get("fontFamily")}; '
            f'text-align: {props.get("textAlign")}; '
            f'padding: {props.get("padding")};">\n'
            f'  {props.get("content")}\n'
            f'</div>'
        )

    elif ctype == "heading":
        tag = props.get("level", "h2")
        return (
            f'<{tag} style="font-size: {props.get("fontSize")}px; '
            f'color: {props.get("color")}; '
            f'font-family: {props.get("fontFamily")}; '
            f'text-align: {props.get("textAlign")}; '
            f'padding: {props.get("padding")}; margin: 0;">\n'
            f'  {props.get("content")}\n'
            f'</{tag}>'
        )

    elif ctype == "button":
        return (
            f'<div style="text-align: {props.get("textAlign", "center")}; padding: 10px;">\n'
            f'  <a href="{props.get("href")}" style="display: inline-block; '
            f'background-color: {props.get("backgroundColor")}; '
            f'color: {props.get("color")}; '
            f'padding: {props.get("padding")}; '
            f'border-radius: {props.get("borderRadius")}; '
            f'text-decoration: none; font-family: Arial, sans-serif;">\n'
            f'    {props.get("text")}\n'
            f'  </a>\n'
            f'</div>'
        )

    elif ctype == "image":
        return (
            f'<div style="text-align: center;">\n'
            f'  <img src="{props.get("src")}" alt="{props.get("alt")}" '
            f'style="width: {props.get("width")}; height: {props.get("height")}; '
            f'max-width: 100%;" />\n'
            f'</div>'
        )

    elif ctype == "divider":
        return (
            f'<hr style="border-color: {props.get("borderColor")}; '
            f'border-width: {props.get("borderWidth")}; '
            f'border-style: solid; margin: {props.get("margin")};" />'
        )

    elif ctype == "spacer":
        return f'<div style="height: {props.get("height")};"></div>'

    elif ctype == "row":
        # This is the critical test — frontend accesses column.props.width
        # and column.children directly. Children MUST be inline objects.
        if children and len(children) > 0:
            columns_html_parts = []
            for column in children:
                # Frontend does: column.props.width and column.children
                assert isinstance(column, dict), (
                    f"ROW child must be an object, got {type(column).__name__}: {column}"
                )
                assert "props" in column, f"Column missing 'props': {column.get('id')}"
                assert "width" in column.get("props", {}), (
                    f"Column missing 'props.width': {column.get('id')}"
                )

                col_children = column.get("children", [])
                if col_children and len(col_children) > 0:
                    col_children_html = "\n    ".join(
                        component_to_html(child) for child in col_children
                    )
                else:
                    col_children_html = (
                        '<div style="text-align: center; color: #9CA3AF; '
                        'padding: 20px;">Empty column</div>'
                    )

                columns_html_parts.append(
                    f'  <td style="width: {column["props"]["width"]}; '
                    f'vertical-align: top; padding: 10px; '
                    f'border: 1px solid #E5E7EB;">\n'
                    f'    {col_children_html}\n'
                    f'  </td>'
                )
            columns_html = "\n".join(columns_html_parts)
        else:
            columns_html = ""

        return (
            f'<table role="presentation" style="width: 100%; border-collapse: collapse;">\n'
            f'  <tr>\n'
            f'{columns_html}\n'
            f'  </tr>\n'
            f'</table>'
        )

    elif ctype == "section":
        if children and len(children) > 0:
            section_html = "\n".join(component_to_html(c) for c in children)
        else:
            section_html = (
                '<div style="text-align: center; color: #9CA3AF; '
                'padding: 20px;">Empty section</div>'
            )
        return (
            f'<div style="background-color: {props.get("backgroundColor")}; '
            f'padding: {props.get("padding")};">\n'
            f'  {section_html}\n'
            f'</div>'
        )

    elif ctype == "container":
        if children and len(children) > 0:
            container_html = "\n".join(component_to_html(c) for c in children)
        else:
            container_html = (
                '<div style="text-align: center; color: #9CA3AF; '
                'padding: 20px;">Empty container</div>'
            )
        return (
            f'<div style="max-width: {props.get("maxWidth")}; '
            f'margin: 0 auto; padding: {props.get("padding")};">\n'
            f'  {container_html}\n'
            f'</div>'
        )

    else:
        return f'<!-- Unknown component: {ctype} -->'


def generate_email_html(components, metadata=None):
    """Exact port of frontend generateEmailHTML()."""
    metadata = metadata or {}
    template_name = metadata.get("templateName", "Email Template")

    if components and len(components) > 0:
        components_html = "\n\n".join(component_to_html(c) for c in components)
    else:
        components_html = (
            '<div style="text-align: center; color: #9CA3AF; '
            'padding: 40px;">No components added yet</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{template_name}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f4f4;">
  <table role="presentation" style="width: 100%; background-color: #f4f4f4;">
    <tr>
      <td align="center" style="padding: 20px 0;">
        <table role="presentation" style="width: 600px; background-color: #ffffff;">
          <tr>
            <td style="padding: 20px;">
{components_html}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def validate_frontend_compat(component, path="root"):
    """Recursively validate a component tree matches frontend expectations."""
    errors = []

    if not isinstance(component, dict):
        errors.append(f"[{path}] Component is not a dict: {type(component).__name__}")
        return errors

    ctype = component.get("type")
    cid = component.get("id", "?")
    props = component.get("props", {})
    children = component.get("children", [])

    if not ctype:
        errors.append(f"[{path}/{cid}] Missing 'type'")
    if not isinstance(props, dict):
        errors.append(f"[{path}/{cid}] 'props' is not a dict")

    # Check children are all inline objects (not string IDs)
    for i, child in enumerate(children):
        if isinstance(child, str):
            errors.append(
                f"[{path}/{cid}] children[{i}] is a string ID '{child}' — "
                f"must be inline object for frontend"
            )
        elif isinstance(child, dict):
            errors.extend(validate_frontend_compat(child, f"{path}/{cid}"))

    # Row-specific: children must be columns with props.width
    if ctype == "row":
        for i, child in enumerate(children):
            if isinstance(child, dict):
                if child.get("type") != "column":
                    errors.append(
                        f"[{path}/{cid}] row child[{i}] type is '{child.get('type')}', "
                        f"expected 'column'"
                    )
                if "width" not in child.get("props", {}):
                    errors.append(
                        f"[{path}/{cid}] row child[{i}] column missing props.width"
                    )

    return errors


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def test_template(filepath):
    """Test a template file for frontend compatibility."""
    name = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")

    with open(filepath) as f:
        template = json.load(f)

    components = template.get("components", [])
    print(f"  templateName: {template.get('templateName', '(none)')}")
    print(f"  Root components: {len(components)}")

    # Step 1: Structural validation
    all_errors = []
    for comp in components:
        all_errors.extend(validate_frontend_compat(comp))

    if all_errors:
        print(f"\n  STRUCTURAL ERRORS ({len(all_errors)}):")
        for e in all_errors:
            print(f"    ✗ {e}")
        return False

    print(f"  Structure: OK (all children are inline objects)")

    # Step 2: Try generating HTML with frontend logic
    try:
        html = generate_email_html(components, template)
        print(f"  Frontend HTML generation: OK ({len(html)} bytes)")
    except (AssertionError, KeyError, TypeError) as e:
        print(f"  Frontend HTML generation: FAILED — {e}")
        return False

    # Step 3: Check required frontend fields
    missing_fields = []
    def check_fields(comp, path=""):
        cid = comp.get("id", "?")
        p = f"{path}/{cid}"
        if "styles" not in comp:
            missing_fields.append(f"{p} missing 'styles'")
        if "visibility" not in comp:
            missing_fields.append(f"{p} missing 'visibility'")
        if "locked" not in comp:
            missing_fields.append(f"{p} missing 'locked'")
        if comp.get("type") == "row" and "columns" not in comp.get("props", {}):
            missing_fields.append(f"{p} row missing 'props.columns'")
        for child in comp.get("children", []):
            if isinstance(child, dict):
                check_fields(child, p)

    for comp in components:
        check_fields(comp)

    if missing_fields:
        print(f"\n  MISSING FRONTEND FIELDS ({len(missing_fields)}):")
        for m in missing_fields[:10]:
            print(f"    ✗ {m}")
        if len(missing_fields) > 10:
            print(f"    ... and {len(missing_fields) - 10} more")
        return False

    print(f"  Frontend fields (styles/visibility/locked/columns): OK")
    print(f"\n  ✓ PASS — Compatible with frontend")
    return True


def main():
    templates_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "templates"
    )

    if not os.path.isdir(templates_dir):
        print(f"Templates directory not found: {templates_dir}")
        sys.exit(1)

    files = sorted(f for f in os.listdir(templates_dir) if f.endswith(".json"))
    if not files:
        print("No .json files found in templates/")
        sys.exit(1)

    results = {}
    for fname in files:
        filepath = os.path.join(templates_dir, fname)
        results[fname] = test_template(filepath)

    # Also test the holi template (canonical frontend example)
    holi_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "frontend", "examples", "holi_sale_template.json"
    )
    if os.path.exists(holi_path):
        results["holi_sale_template.json (canonical)"] = test_template(holi_path)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status}  {name}")
    print(f"\n  {passed}/{total} passed")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
