"""Tests for the email HTML engine."""

import json
import sys
import os
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import build_html, validate_tree
from engine.renderer import render_html
from engine.builder import (
    add_component,
    remove_component,
    inject_preset,
    get_root_components,
    get_children,
    get_subtree,
)
from engine.schema import validate_tree as schema_validate, find_in_tree


# ---------------------------------------------------------------------------
# Fixtures (nested format — children are inline dicts)
# ---------------------------------------------------------------------------

def _minimal_template():
    """Minimal valid template: 1 row → 1 column → 1 text."""
    return {
        "templateName": "Test",
        "templateSubject": "Test Subject",
        "components": [
            {
                "id": "row-1",
                "type": "row",
                "props": {"backgroundColor": "#FFFFFF"},
                "styles": {},
                "parentId": None,
                "children": [
                    {
                        "id": "col-1",
                        "type": "column",
                        "props": {"width": "100%", "backgroundColor": "#FFFFFF"},
                        "styles": {},
                        "parentId": "row-1",
                        "children": [
                            {
                                "id": "text-1",
                                "type": "text",
                                "props": {
                                    "content": "Hello World",
                                    "fontSize": 16,
                                    "color": "#333333",
                                },
                                "styles": {},
                                "parentId": "col-1",
                                "children": [],
                                "visibility": True,
                                "locked": False,
                            },
                        ],
                        "visibility": True,
                        "locked": False,
                    },
                ],
                "visibility": True,
                "locked": False,
            },
        ],
    }


def _multi_column_template():
    """Template with 2-column row."""
    return {
        "templateName": "Multi Column",
        "components": [
            {
                "id": "row-1",
                "type": "row",
                "props": {"backgroundColor": "#FF6B35"},
                "styles": {},
                "parentId": None,
                "children": [
                    {
                        "id": "col-1",
                        "type": "column",
                        "props": {"width": "50%", "backgroundColor": "#FF6B35"},
                        "styles": {},
                        "parentId": "row-1",
                        "children": [
                            {
                                "id": "heading-1",
                                "type": "heading",
                                "props": {
                                    "content": "Big Sale!",
                                    "level": "h1",
                                    "fontSize": 32,
                                    "color": "#FFFFFF",
                                    "textAlign": "center",
                                },
                                "styles": {},
                                "parentId": "col-1",
                                "children": [],
                                "visibility": True,
                                "locked": False,
                            },
                        ],
                        "visibility": True,
                        "locked": False,
                    },
                    {
                        "id": "col-2",
                        "type": "column",
                        "props": {"width": "50%", "backgroundColor": "#FFFFFF"},
                        "styles": {},
                        "parentId": "row-1",
                        "children": [
                            {
                                "id": "text-1",
                                "type": "text",
                                "props": {"content": "Check out our deals.", "fontSize": 14},
                                "styles": {},
                                "parentId": "col-2",
                                "children": [],
                                "visibility": True,
                                "locked": False,
                            },
                        ],
                        "visibility": True,
                        "locked": False,
                    },
                ],
                "visibility": True,
                "locked": False,
            },
        ],
    }


def _full_template():
    """Template with all component types."""
    return {
        "templateName": "Full Test",
        "templateSubject": "All Components",
        "components": [
            {
                "id": "row-1",
                "type": "row",
                "props": {"backgroundColor": "#2563EB"},
                "styles": {},
                "parentId": None,
                "children": [
                    {
                        "id": "col-1",
                        "type": "column",
                        "props": {"width": "100%", "backgroundColor": "#2563EB"},
                        "styles": {},
                        "parentId": "row-1",
                        "children": [
                            {
                                "id": "heading-1",
                                "type": "heading",
                                "props": {
                                    "content": "Welcome",
                                    "level": "h1",
                                    "fontSize": 36,
                                    "color": "#FFFFFF",
                                    "textAlign": "center",
                                    "padding": "20px",
                                },
                                "styles": {},
                                "parentId": "col-1",
                                "children": [],
                                "visibility": True,
                                "locked": False,
                            },
                            {
                                "id": "text-1",
                                "type": "text",
                                "props": {
                                    "content": "<strong>Bold</strong> and <em>italic</em> text",
                                    "fontSize": 14,
                                    "color": "#FFFFFF",
                                    "textAlign": "center",
                                },
                                "styles": {},
                                "parentId": "col-1",
                                "children": [],
                                "visibility": True,
                                "locked": False,
                            },
                            {
                                "id": "img-1",
                                "type": "image",
                                "props": {
                                    "src": "https://example.com/hero.jpg",
                                    "alt": "Hero image",
                                    "width": "100%",
                                    "height": "auto",
                                },
                                "styles": {},
                                "parentId": "col-1",
                                "children": [],
                                "visibility": True,
                                "locked": False,
                            },
                            {
                                "id": "btn-1",
                                "type": "button",
                                "props": {
                                    "text": "Shop Now",
                                    "href": "https://example.com/shop",
                                    "backgroundColor": "#E91E63",
                                    "color": "#FFFFFF",
                                    "padding": "14px 28px",
                                    "borderRadius": "6px",
                                    "fontSize": 18,
                                    "textAlign": "center",
                                },
                                "styles": {},
                                "parentId": "col-1",
                                "children": [],
                                "visibility": True,
                                "locked": False,
                            },
                            {
                                "id": "divider-1",
                                "type": "divider",
                                "props": {
                                    "borderColor": "#FFFFFF",
                                    "borderWidth": "2px",
                                    "margin": "20px 0",
                                },
                                "styles": {},
                                "parentId": "col-1",
                                "children": [],
                                "visibility": True,
                                "locked": False,
                            },
                            {
                                "id": "spacer-1",
                                "type": "spacer",
                                "props": {"height": "30px"},
                                "styles": {},
                                "parentId": "col-1",
                                "children": [],
                                "visibility": True,
                                "locked": False,
                            },
                        ],
                        "visibility": True,
                        "locked": False,
                    },
                ],
                "visibility": True,
                "locked": False,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_minimal(self):
        errors = validate_tree(_minimal_template())
        assert errors == []

    def test_valid_multi_column(self):
        errors = validate_tree(_multi_column_template())
        assert errors == []

    def test_valid_full(self):
        errors = validate_tree(_full_template())
        assert errors == []

    def test_missing_components(self):
        errors = validate_tree({"templateName": "Bad"})
        assert len(errors) > 0
        assert "components" in errors[0].lower()

    def test_empty_components(self):
        errors = validate_tree({"components": []})
        assert len(errors) > 0

    def test_invalid_type(self):
        template = _minimal_template()
        # Change the text component's type to invalid
        template["components"][0]["children"][0]["children"][0]["type"] = "foobar"
        errors = validate_tree(template)
        assert any("foobar" in e for e in errors)

    def test_duplicate_id(self):
        template = _minimal_template()
        # Give text the same ID as row
        template["components"][0]["children"][0]["children"][0]["id"] = "row-1"
        errors = validate_tree(template)
        assert any("Duplicate" in e for e in errors)

    def test_wrong_parent_type(self):
        """Row cannot be child of text."""
        template = _minimal_template()
        # Add a row as child of text-1 (invalid)
        text_comp = template["components"][0]["children"][0]["children"][0]
        text_comp["children"] = [{
            "id": "bad-row",
            "type": "row",
            "props": {},
            "styles": {},
            "parentId": "text-1",
            "children": [],
            "visibility": True,
            "locked": False,
        }]
        errors = validate_tree(template)
        assert len(errors) > 0

    def test_not_a_dict(self):
        errors = validate_tree("not a dict")
        assert len(errors) > 0

    def test_string_child_ids_rejected(self):
        """String IDs in children should produce an error."""
        template = {
            "components": [
                {
                    "id": "row-1",
                    "type": "row",
                    "props": {},
                    "parentId": None,
                    "children": ["col-1"],  # string ID — wrong format
                },
            ],
        }
        errors = validate_tree(template)
        assert any("string ID" in e for e in errors)


# ---------------------------------------------------------------------------
# Rendering tests
# ---------------------------------------------------------------------------

class TestRendering:
    def test_minimal_renders(self):
        html = build_html(_minimal_template())
        assert "<!DOCTYPE html>" in html
        assert "Hello World" in html

    def test_has_mso_conditionals(self):
        html = build_html(_minimal_template())
        assert "<!--[if mso]>" in html
        assert "<![endif]-->" in html

    def test_has_xmlns_vml(self):
        html = build_html(_minimal_template())
        assert 'xmlns:v="urn:schemas-microsoft-com:vml"' in html

    def test_has_office_settings(self):
        html = build_html(_minimal_template())
        assert "o:OfficeDocumentSettings" in html
        assert "o:AllowPNG" in html

    def test_has_mobile_responsive(self):
        html = build_html(_minimal_template())
        assert "@media only screen" in html
        assert "stack-column" in html

    def test_heading_renders(self):
        html = build_html(_full_template())
        assert "<h1" in html
        assert "Welcome" in html

    def test_text_preserves_html(self):
        html = build_html(_full_template())
        assert "<strong>Bold</strong>" in html
        assert "<em>italic</em>" in html

    def test_button_vml(self):
        html = build_html(_full_template())
        assert "v:roundrect" in html
        assert "Shop Now" in html
        assert "https://example.com/shop" in html

    def test_button_non_mso(self):
        html = build_html(_full_template())
        assert "<!--[if !mso]><!-->" in html

    def test_image_renders(self):
        html = build_html(_full_template())
        assert "https://example.com/hero.jpg" in html
        assert 'alt="Hero image"' in html

    def test_divider_renders(self):
        html = build_html(_full_template())
        assert "<hr" in html

    def test_spacer_renders(self):
        html = build_html(_full_template())
        assert "30px" in html
        assert "mso-line-height-rule:exactly" in html

    def test_multi_column_mso(self):
        html = build_html(_multi_column_template())
        assert "<!--[if mso]>" in html
        assert "Big Sale!" in html
        assert "Check out our deals." in html

    def test_background_colors(self):
        html = build_html(_multi_column_template())
        assert "#FF6B35" in html

    def test_subject_in_title(self):
        html = build_html(_full_template())
        assert "<title>All Components</title>" in html

    def test_invisible_component_hidden(self):
        template = _minimal_template()
        template["components"][0]["children"][0]["children"][0]["visibility"] = False
        html = build_html(template)
        assert "Hello World" not in html

    def test_empty_image_no_crash(self):
        """Image with no src should render a comment, not crash."""
        template = _minimal_template()
        template["components"][0]["children"][0]["children"][0] = {
            "id": "text-1",
            "type": "image",
            "props": {"src": "", "alt": "empty"},
            "styles": {},
            "parentId": "col-1",
            "children": [],
            "visibility": True,
            "locked": False,
        }
        html = build_html(template)
        assert "empty image" in html

    def test_build_html_validates(self):
        """build_html should raise ValueError on invalid tree."""
        with pytest.raises(ValueError):
            build_html({"components": []})


# ---------------------------------------------------------------------------
# Builder tests
# ---------------------------------------------------------------------------

class TestBuilder:
    def test_get_root_components(self):
        template = _multi_column_template()
        roots = get_root_components(template)
        assert len(roots) == 1
        assert roots[0]["id"] == "row-1"

    def test_get_children(self):
        template = _multi_column_template()
        children = get_children(template, "row-1")
        assert len(children) == 2
        assert children[0]["id"] == "col-1"
        assert children[1]["id"] == "col-2"

    def test_get_subtree(self):
        template = _multi_column_template()
        subtree = get_subtree(template, "col-1")
        ids = {c["id"] for c in subtree}
        assert "col-1" in ids
        assert "heading-1" in ids
        assert "text-1" not in ids  # text-1 is in col-2

    def test_add_component(self):
        template = _minimal_template()
        new_comp = {
            "id": "spacer-new",
            "type": "spacer",
            "props": {"height": "40px"},
            "styles": {},
            "parentId": None,  # will be set by add_component
            "children": [],
            "visibility": True,
            "locked": False,
        }
        updated = add_component(template, "col-1", new_comp)
        col, _, _ = find_in_tree(updated["components"], "col-1")
        child_ids = [c["id"] for c in col["children"] if isinstance(c, dict)]
        assert "spacer-new" in child_ids

    def test_remove_component(self):
        template = _multi_column_template()
        updated = remove_component(template, "col-2")
        # col-2 and its children should be gone
        comp, _, _ = find_in_tree(updated["components"], "col-2")
        assert comp is None
        comp, _, _ = find_in_tree(updated["components"], "text-1")
        assert comp is None  # child of col-2 is also removed (inline)
        # row should no longer have col-2
        row, _, _ = find_in_tree(updated["components"], "row-1")
        child_ids = [c["id"] for c in row["children"] if isinstance(c, dict)]
        assert "col-2" not in child_ids

    def test_inject_preset(self):
        template = _minimal_template()
        preset = {
            "preset_id": "test-preset",
            "components": [
                {
                    "id": "preset-row",
                    "type": "row",
                    "props": {"backgroundColor": "{{primaryColor}}"},
                    "styles": {},
                    "parentId": None,
                    "children": [
                        {
                            "id": "preset-col",
                            "type": "column",
                            "props": {"width": "100%"},
                            "styles": {},
                            "parentId": "preset-row",
                            "children": [],
                            "visibility": True,
                            "locked": False,
                        },
                    ],
                    "visibility": True,
                    "locked": False,
                },
            ],
            "variables": {
                "primaryColor": {"type": "color", "default": "#FF0000"},
            },
        }
        updated = inject_preset(template, preset)
        # Should have original 1 root + 1 preset root = 2 root components
        assert len(updated["components"]) == 2
        # Preset IDs should be remapped (not "preset-row")
        root_ids = {c["id"] for c in updated["components"]}
        assert "preset-row" not in root_ids  # remapped to new ID

    def test_inject_preset_with_customizations(self):
        template = _minimal_template()
        preset = {
            "preset_id": "test",
            "components": [
                {
                    "id": "p-row",
                    "type": "row",
                    "props": {"backgroundColor": "{{color}}"},
                    "styles": {},
                    "parentId": None,
                    "children": [],
                    "visibility": True,
                    "locked": False,
                },
            ],
            "variables": {
                "color": {"type": "color", "default": "#000"},
            },
            "customizations": {
                "color": "#00FF00",
            },
        }
        updated = inject_preset(template, preset)
        new_rows = [c for c in updated["components"] if c["id"] != "row-1" and c["type"] == "row"]
        assert len(new_rows) == 1
        assert new_rows[0]["props"]["backgroundColor"] == "#00FF00"

    def test_add_remove_doesnt_mutate_original(self):
        """Builder functions should return new dicts, not mutate input."""
        template = _minimal_template()
        original_count = len(template["components"])

        new_comp = {
            "id": "sp-1",
            "type": "spacer",
            "props": {"height": "10px"},
            "styles": {},
            "parentId": None,
            "children": [],
            "visibility": True,
            "locked": False,
        }
        add_component(template, "col-1", new_comp)
        assert len(template["components"]) == original_count  # unchanged

        remove_component(template, "text-1")
        assert len(template["components"]) == original_count  # unchanged


# ---------------------------------------------------------------------------
# MCP Server tests
# ---------------------------------------------------------------------------

class TestMCPServer:
    def test_build_html_tool(self):
        from mcp.server import EmailEngineMCPServer

        server = EmailEngineMCPServer()
        result = server.handle_tool_call("build_email_html", {
            "template": _minimal_template(),
        })
        assert "html" in result
        assert "Hello World" in result["html"]
        assert "size_bytes" in result

    def test_validate_tool_valid(self):
        from mcp.server import EmailEngineMCPServer

        server = EmailEngineMCPServer()
        result = server.handle_tool_call("validate_template", {
            "template": _minimal_template(),
        })
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_tool_invalid(self):
        from mcp.server import EmailEngineMCPServer

        server = EmailEngineMCPServer()
        result = server.handle_tool_call("validate_template", {
            "template": {"components": []},
        })
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_unknown_tool(self):
        from mcp.server import EmailEngineMCPServer

        server = EmailEngineMCPServer()
        result = server.handle_tool_call("nonexistent_tool", {})
        assert "error" in result

    def test_add_component_tool(self):
        from mcp.server import EmailEngineMCPServer

        server = EmailEngineMCPServer()
        result = server.handle_tool_call("add_component", {
            "template": _minimal_template(),
            "parent_id": "col-1",
            "component": {
                "id": "sp-1",
                "type": "spacer",
                "props": {"height": "20px"},
                "styles": {},
                "parentId": None,
                "children": [],
                "visibility": True,
                "locked": False,
            },
        })
        assert "template" in result
        # Result is in frontend format (nested), find col-1 and check children
        col, _, _ = find_in_tree(result["template"]["components"], "col-1")
        child_ids = [c["id"] for c in col["children"] if isinstance(c, dict)]
        assert "sp-1" in child_ids

    def test_remove_component_tool(self):
        from mcp.server import EmailEngineMCPServer

        server = EmailEngineMCPServer()
        result = server.handle_tool_call("remove_component", {
            "template": _minimal_template(),
            "component_id": "text-1",
        })
        assert "template" in result
        comp, _, _ = find_in_tree(result["template"]["components"], "text-1")
        assert comp is None

    def test_preset_tools_without_loader(self):
        from mcp.server import EmailEngineMCPServer

        server = EmailEngineMCPServer()
        result = server.handle_tool_call("list_presets", {})
        assert "error" in result
        assert "not configured" in result["error"]

    def test_build_html_without_saver(self):
        """Without template_saver, build_email_html should still work — no template_id."""
        from mcp.server import EmailEngineMCPServer

        server = EmailEngineMCPServer()
        result = server.handle_tool_call("build_email_html", {
            "template": _minimal_template(),
        })
        assert "html" in result
        assert "template_id" not in result
        assert "editor_link" not in result

    def test_build_html_with_saver(self):
        """With template_saver, build_email_html should return template_id + editor_link."""
        from mcp.server import EmailEngineMCPServer

        saved = {}

        def mock_saver(template_id, template_dict):
            saved["id"] = template_id
            saved["template"] = template_dict
            return {
                "template_id": template_id,
                "editor_link": f"http://localhost:3000/editor/{template_id}",
            }

        server = EmailEngineMCPServer(template_saver=mock_saver)
        result = server.handle_tool_call("build_email_html", {
            "template": _minimal_template(),
        })
        assert "html" in result
        assert "template_id" in result
        assert "editor_link" in result
        assert result["template_id"] == saved["id"]
        assert "/editor/" in result["editor_link"]
        assert saved["template"]["components"]  # template was passed to saver

    def test_build_html_saver_failure_non_fatal(self):
        """If template_saver raises, build should still return html (non-fatal)."""
        from mcp.server import EmailEngineMCPServer

        def failing_saver(template_id, template_dict):
            raise RuntimeError("S3 is down")

        server = EmailEngineMCPServer(template_saver=failing_saver)
        result = server.handle_tool_call("build_email_html", {
            "template": _minimal_template(),
        })
        assert "html" in result
        assert "Hello World" in result["html"]
        # No template_id/editor_link since saver failed
        assert "template_id" not in result


# ---------------------------------------------------------------------------
# Integration: Render real template
# ---------------------------------------------------------------------------

class TestRealTemplate:
    """Test rendering with the actual holi_sale_template.json if available."""

    @pytest.fixture
    def holi_template(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "examples",
            "holi_sale_template.json"
        )
        if not os.path.exists(path):
            pytest.skip("holi_sale_template.json not found")
        with open(path) as f:
            return json.load(f)

    def test_holi_validates(self, holi_template):
        errors = validate_tree(holi_template)
        assert errors == [], f"Validation errors: {errors}"

    def test_holi_renders(self, holi_template):
        html = build_html(holi_template)
        assert "<!DOCTYPE html>" in html
        assert len(html) > 1000  # should be a substantial HTML document

    def test_holi_has_mso(self, holi_template):
        html = build_html(holi_template)
        assert "v:roundrect" in html  # buttons should have VML
        assert "mso-line-height-rule" in html
