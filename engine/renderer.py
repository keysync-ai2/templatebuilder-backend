"""Render emailBuilder component tree JSON to production-ready email HTML.

Generates HTML compatible with:
- Gmail (Web + Mobile)
- Outlook 2007-2021 (Desktop) — via MSO conditional comments + VML
- Outlook.com / 365 (Web)
- Apple Mail (macOS + iOS)
- Yahoo Mail
- Samsung Mail

All styles are inlined. MSO conditionals handle Outlook desktop quirks.
"""

import html as html_module

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMAIL_WIDTH = 600  # px — standard email width

# Default prop values per component type (mirrors frontend componentLibrary.js)
DEFAULTS = {
    "text": {
        "content": "",
        "fontSize": 14,
        "color": "#000000",
        "fontFamily": "Arial, sans-serif",
        "textAlign": "left",
        "padding": "10px",
    },
    "heading": {
        "content": "Heading",
        "level": "h2",
        "fontSize": 24,
        "color": "#000000",
        "fontFamily": "Arial, sans-serif",
        "textAlign": "left",
        "padding": "10px",
    },
    "button": {
        "text": "Click Me",
        "href": "#",
        "backgroundColor": "#2563EB",
        "color": "#FFFFFF",
        "padding": "12px 24px",
        "borderRadius": "4px",
        "textAlign": "center",
        "fontSize": 16,
        "fontFamily": "Arial, sans-serif",
    },
    "image": {
        "src": "",
        "alt": "Image",
        "width": "100%",
        "height": "auto",
    },
    "divider": {
        "borderColor": "#E5E7EB",
        "borderWidth": "1px",
        "margin": "20px 0",
    },
    "spacer": {
        "height": "20px",
    },
    "row": {
        "backgroundColor": "transparent",
        "padding": "0",
    },
    "column": {
        "width": "100%",
        "backgroundColor": "transparent",
        "padding": "0",
    },
    "section": {
        "backgroundColor": "#FFFFFF",
        "padding": "20px",
    },
    "container": {
        "maxWidth": "600px",
        "padding": "20px",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prop(comp: dict, key: str, default=None):
    """Get a prop value with fallback to component-type defaults."""
    props = comp.get("props", {})
    val = props.get(key)
    if val is not None and val != "":
        return val
    type_defaults = DEFAULTS.get(comp.get("type", ""), {})
    if key in type_defaults:
        return type_defaults[key]
    return default


def _esc(text: str) -> str:
    """HTML-escape text."""
    return html_module.escape(str(text)) if text else ""


def _px(value) -> str:
    """Normalize a size value to px string."""
    if value is None:
        return "0"
    if isinstance(value, (int, float)):
        return f"{int(value)}px"
    s = str(value).strip()
    if s.isdigit():
        return f"{s}px"
    return s


def _parse_border_radius(value) -> int:
    """Extract numeric px value from borderRadius for VML arcsize calc."""
    if not value:
        return 0
    s = str(value).replace("px", "").strip()
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _border_style(comp: dict) -> str:
    """Generate border CSS if borderWidth is set and > 0."""
    bw = _prop(comp, "borderWidth")
    bc = _prop(comp, "borderColor", "#E5E7EB")
    if not bw or bw == "0" or bw == "0px":
        return ""
    return f"border:{_px(bw)} solid {bc};"


def _is_visible(comp: dict) -> bool:
    """Check if component is visible."""
    return comp.get("visibility", True) is not False


# ---------------------------------------------------------------------------
# Component renderers
# ---------------------------------------------------------------------------

def _render_text(comp: dict, depth: int = 0) -> str:
    content = _prop(comp, "content", "")
    font_size = _px(_prop(comp, "fontSize", 14))
    color = _prop(comp, "color", "#000000")
    font_family = _prop(comp, "fontFamily", "Arial, sans-serif")
    text_align = _prop(comp, "textAlign", "left")
    padding = _prop(comp, "padding", "10px")
    border = _border_style(comp)

    style = (
        f"margin:0;padding:{padding};font-size:{font_size};"
        f"color:{color};font-family:{font_family};"
        f"text-align:{text_align};line-height:1.5;"
        f"mso-line-height-rule:exactly;{border}"
    )

    # Text content can contain HTML (rich text from editor)
    return f'<div style="{style}">{content}</div>\n'


def _render_heading(comp: dict, depth: int = 0) -> str:
    content = _esc(_prop(comp, "content", "Heading"))
    level = _prop(comp, "level", "h2")
    if level not in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = "h2"
    font_size = _px(_prop(comp, "fontSize", 24))
    color = _prop(comp, "color", "#000000")
    font_family = _prop(comp, "fontFamily", "Arial, sans-serif")
    text_align = _prop(comp, "textAlign", "left")
    padding = _prop(comp, "padding", "10px")
    border = _border_style(comp)

    style = (
        f"margin:0;padding:{padding};font-size:{font_size};"
        f"color:{color};font-family:{font_family};"
        f"text-align:{text_align};font-weight:bold;"
        f"line-height:1.3;mso-line-height-rule:exactly;{border}"
    )

    return f'<{level} style="{style}">{content}</{level}>\n'


def _render_button(comp: dict, depth: int = 0) -> str:
    text = _esc(_prop(comp, "text", "Click Me"))
    href = _prop(comp, "href", "#")
    bg_color = _prop(comp, "backgroundColor", "#2563EB")
    color = _prop(comp, "color", "#FFFFFF")
    padding = _prop(comp, "padding", "12px 24px")
    border_radius = _prop(comp, "borderRadius", "4px")
    text_align = _prop(comp, "textAlign", "center")
    font_size = _px(_prop(comp, "fontSize", 16))
    font_family = _prop(comp, "fontFamily", "Arial, sans-serif")

    radius_px = _parse_border_radius(border_radius)

    # Parse padding for VML height calculation
    padding_parts = padding.replace("px", "").split()
    try:
        pad_v = int(padding_parts[0]) if len(padding_parts) >= 1 else 12
    except (ValueError, IndexError):
        pad_v = 12
    try:
        font_size_num = int(font_size.replace("px", ""))
    except ValueError:
        font_size_num = 16
    vml_height = font_size_num + (pad_v * 2) + 4  # approximate

    # VML arcsize: percentage based on height
    arcsize = f"{int((radius_px / max(vml_height, 1)) * 100)}%" if radius_px > 0 else "0%"

    link_style = (
        f"background-color:{bg_color};color:{color};display:inline-block;"
        f"font-family:{font_family};font-size:{font_size};"
        f"padding:{padding};text-decoration:none;"
        f"border-radius:{border_radius};-webkit-border-radius:{border_radius};"
        f"mso-hide:all;"
    )

    lines = []
    lines.append(f'<div style="text-align:{text_align};padding:10px 0;">')

    # VML button for Outlook
    lines.append('  <!--[if mso]>')
    lines.append(f'  <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"')
    lines.append(f'    xmlns:w="urn:schemas-microsoft-com:office:word"')
    lines.append(f'    href="{_esc(href)}"')
    lines.append(f'    style="height:{vml_height}px;v-text-anchor:middle;width:200px;"')
    lines.append(f'    arcsize="{arcsize}"')
    lines.append(f'    strokecolor="{bg_color}"')
    lines.append(f'    fillcolor="{bg_color}">')
    lines.append(f'    <w:anchorlock/>')
    lines.append(f'    <center style="color:{color};font-family:{font_family};font-size:{font_size};font-weight:bold;">')
    lines.append(f'      {text}')
    lines.append(f'    </center>')
    lines.append(f'  </v:roundrect>')
    lines.append(f'  <![endif]-->')

    # Standard button for all other clients
    lines.append('  <!--[if !mso]><!-->')
    lines.append(f'  <a href="{_esc(href)}" style="{link_style}" target="_blank">{text}</a>')
    lines.append('  <!--<![endif]-->')

    lines.append('</div>')

    return "\n".join(lines) + "\n"


def _render_image(comp: dict, depth: int = 0) -> str:
    src = _prop(comp, "src", "")
    alt = _esc(_prop(comp, "alt", "Image"))
    width = _prop(comp, "width", "100%")
    height = _prop(comp, "height", "auto")
    border = _border_style(comp)

    if not src:
        return '<!-- empty image: no src -->\n'

    # Calculate width attr for img tag
    width_attr = ""
    if width == "100%":
        width_attr = f'width="{EMAIL_WIDTH}"'
        width_style = "width:100%;max-width:100%;"
    elif width.endswith("px"):
        w_num = width.replace("px", "")
        width_attr = f'width="{w_num}"'
        width_style = f"width:{width};max-width:100%;"
    else:
        width_style = f"width:{width};max-width:100%;"

    height_attr = ""
    if height and height != "auto":
        h = height.replace("px", "")
        height_attr = f'height="{h}"'

    style = (
        f"display:block;{width_style}height:{height};"
        f"outline:none;text-decoration:none;border:0;"
        f"-ms-interpolation-mode:bicubic;{border}"
    )

    return (
        f'<div style="text-align:center;">'
        f'<img src="{_esc(src)}" alt="{alt}" {width_attr} {height_attr} '
        f'style="{style}" />'
        f'</div>\n'
    )


def _render_divider(comp: dict, depth: int = 0) -> str:
    border_color = _prop(comp, "borderColor", "#E5E7EB")
    border_width = _prop(comp, "borderWidth", "1px")
    margin = _prop(comp, "margin", "20px 0")

    style = (
        f"border:0;border-top:{border_width} solid {border_color};"
        f"margin:{margin};padding:0;"
    )

    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="padding:0;">'
        f'<hr style="{style}" />'
        f'</td></tr></table>\n'
    )


def _render_spacer(comp: dict, depth: int = 0) -> str:
    height = _prop(comp, "height", "20px")

    return (
        f'<div style="height:{height};line-height:{height};'
        f'font-size:1px;mso-line-height-rule:exactly;">&nbsp;</div>\n'
    )


# ---------------------------------------------------------------------------
# Layout renderers (Row + Column)
# ---------------------------------------------------------------------------

def _render_column(comp: dict, col_width_pct: float, is_last: bool, depth: int = 0) -> str:
    """Render a column as a <td> in the row table."""
    bg_color = _prop(comp, "backgroundColor", "transparent")
    padding = _prop(comp, "padding", "0")
    border = _border_style(comp)
    width_px = int(EMAIL_WIDTH * col_width_pct / 100)

    bg_style = f"background-color:{bg_color};" if bg_color != "transparent" else ""

    style = (
        f"width:{width_px}px;{bg_style}padding:{padding};"
        f"vertical-align:top;{border}"
    )

    lines = []
    lines.append(
        f'<td class="stack-column" style="{style}" width="{width_px}" valign="top">'
    )

    # Render inline children
    for child in comp.get("children", []):
        if isinstance(child, dict) and _is_visible(child):
            lines.append(_render_component(child, depth + 1))

    lines.append('</td>')
    return "\n".join(lines)


def _render_row(comp: dict, depth: int = 0) -> str:
    """Render a row as a full-width <table> with MSO conditionals."""
    bg_color = _prop(comp, "backgroundColor", "transparent")
    padding = _prop(comp, "padding", "0")
    border = _border_style(comp)

    bg_style = f"background-color:{bg_color};" if bg_color != "transparent" else ""
    row_style = f"{bg_style}{border}"

    columns = [c for c in comp.get("children", []) if isinstance(c, dict) and _is_visible(c)]

    if not columns:
        return '<!-- empty row -->\n'

    # Calculate column widths
    col_widths = []
    for col in columns:
        w = _prop(col, "width", "")
        if w and w.endswith("%"):
            try:
                col_widths.append(float(w.replace("%", "")))
            except ValueError:
                col_widths.append(100.0 / len(columns))
        else:
            col_widths.append(100.0 / len(columns))

    # Normalize to 100%
    total = sum(col_widths)
    if total > 0 and abs(total - 100) > 0.1:
        col_widths = [w / total * 100 for w in col_widths]

    lines = []

    # Outer table for full-width background
    lines.append(
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'border="0" style="{row_style}">'
    )
    lines.append(f'<tr><td style="padding:{padding};" align="center">')

    # Inner table for content width
    lines.append(
        f'<table role="presentation" width="{EMAIL_WIDTH}" cellpadding="0" '
        f'cellspacing="0" border="0" class="email-container" '
        f'style="margin:0 auto;">'
    )

    # MSO conditional for multi-column layout
    if len(columns) > 1:
        lines.append('<!--[if mso]>')
        lines.append('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">')
        lines.append('<tr>')
        lines.append('<![endif]-->')

    lines.append('<tr>')
    for i, col in enumerate(columns):
        is_last = (i == len(columns) - 1)

        if len(columns) > 1:
            # Multi-column: each column wrapped in MSO td
            col_width_px = int(EMAIL_WIDTH * col_widths[i] / 100)
            lines.append(f'<!--[if mso]><td width="{col_width_px}" valign="top"><![endif]-->')

        lines.append(_render_column(col, col_widths[i], is_last, depth))

        if len(columns) > 1:
            lines.append('<!--[if mso]></td><![endif]-->')

    lines.append('</tr>')

    if len(columns) > 1:
        lines.append('<!--[if mso]>')
        lines.append('</tr></table>')
        lines.append('<![endif]-->')

    lines.append('</table>')
    lines.append('</td></tr>')
    lines.append('</table>')

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Section + Container
# ---------------------------------------------------------------------------

def _render_section(comp: dict, depth: int = 0) -> str:
    bg_color = _prop(comp, "backgroundColor", "#FFFFFF")
    padding = _prop(comp, "padding", "20px")
    border = _border_style(comp)

    style = f"background-color:{bg_color};padding:{padding};{border}"

    lines = []
    lines.append(f'<div style="{style}">')
    for child in comp.get("children", []):
        if isinstance(child, dict) and _is_visible(child):
            lines.append(_render_component(child, depth + 1))
    lines.append('</div>')
    return "\n".join(lines) + "\n"


def _render_container(comp: dict, depth: int = 0) -> str:
    max_width = _prop(comp, "maxWidth", "600px")
    padding = _prop(comp, "padding", "20px")
    border = _border_style(comp)

    style = f"max-width:{max_width};margin:0 auto;padding:{padding};{border}"

    lines = []
    lines.append(f'<div style="{style}">')
    for child in comp.get("children", []):
        if isinstance(child, dict) and _is_visible(child):
            lines.append(_render_component(child, depth + 1))
    lines.append('</div>')
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

CONTENT_RENDERERS = {
    "text": _render_text,
    "heading": _render_heading,
    "button": _render_button,
    "image": _render_image,
    "divider": _render_divider,
    "spacer": _render_spacer,
}


def _render_component(comp: dict, depth: int = 0) -> str:
    """Render a single component to HTML. Dispatches by type."""
    ctype = comp.get("type", "")

    if ctype in CONTENT_RENDERERS:
        return CONTENT_RENDERERS[ctype](comp, depth)
    elif ctype == "row":
        return _render_row(comp, depth)
    elif ctype == "column":
        # Columns are rendered by their parent row — should not be called directly
        return ""
    elif ctype == "section":
        return _render_section(comp, depth)
    elif ctype == "container":
        return _render_container(comp, depth)
    else:
        return f'<!-- unknown component type: {_esc(ctype)} -->\n'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_html(template: dict) -> str:
    """Convert an emailBuilder component tree to production-ready email HTML.

    Args:
        template: Dict with at minimum a "components" array.
                  Optionally: templateName, templateSubject, etc.
                  Expects nested format (children = inline dicts).

    Returns:
        Complete HTML document string ready for email sending.
    """
    components = template.get("components", [])

    # Render body content from root components
    body_parts = []
    for comp in components:
        if isinstance(comp, dict) and _is_visible(comp):
            body_parts.append(_render_component(comp, 0))

    body_html = "\n".join(body_parts)

    # Build full email HTML document
    subject = _esc(template.get("templateSubject", ""))
    preheader = ""  # Can be extended later

    return _wrap_document(body_html, subject, preheader)


def _wrap_document(body_html: str, subject: str = "", preheader: str = "") -> str:
    """Wrap rendered components in a full email HTML document with MSO support."""

    preheader_html = ""
    if preheader:
        preheader_html = (
            f'<div style="display:none;font-size:1px;color:#ffffff;'
            f'line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">'
            f'{_esc(preheader)}</div>\n'
        )

    return f'''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml"
  xmlns:o="urn:schemas-microsoft-com:office:office" lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{subject}</title>
  <!--[if !mso]><!-->
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  <!--<![endif]-->
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:AllowPNG/>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <style type="text/css">
    table {{border-collapse:collapse;border-spacing:0;mso-table-lspace:0pt;mso-table-rspace:0pt;}}
    td {{border-collapse:collapse;}}
  </style>
  <![endif]-->
  <style type="text/css">
    /* Reset */
    body {{
      margin: 0;
      padding: 0;
      width: 100%;
      -webkit-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
    }}
    table {{
      border-collapse: collapse;
      mso-table-lspace: 0pt;
      mso-table-rspace: 0pt;
    }}
    img {{
      border: 0;
      line-height: 100%;
      outline: none;
      text-decoration: none;
      -ms-interpolation-mode: bicubic;
    }}
    a {{
      text-decoration: none;
    }}
    /* Mobile responsive */
    @media only screen and (max-width: 620px) {{
      .email-container {{
        width: 100% !important;
        max-width: 100% !important;
      }}
      .stack-column {{
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
      }}
      .stack-column img {{
        width: 100% !important;
        height: auto !important;
      }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;width:100%;">
  {preheader_html}
  <!--[if mso]>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
    style="background-color:#f4f4f4;">
  <tr><td align="center">
  <![endif]-->

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
    style="background-color:#f4f4f4;">
    <tr>
      <td align="center" style="padding:20px 0;">
{body_html}
      </td>
    </tr>
  </table>

  <!--[if mso]>
  </td></tr></table>
  <![endif]-->
</body>
</html>'''
