"""MCP tool definitions for the Email HTML Engine.

Each tool wraps an engine function and provides schema for LLM tool-use.
"""

TOOLS = [
    {
        "name": "build_email_html",
        "description": (
            "Convert an emailBuilder component tree JSON into production-ready "
            "email HTML with full MSO/Outlook VML support, responsive media queries, "
            "and inlined styles.\n\n"

            "## CRITICAL RULES — Read before building\n"
            "1. The ONLY way to put content in the email is through components in the JSON. "
            "The engine renders ONLY what is in the components array. Do NOT describe extra "
            "content in your chat response that is not in the JSON — the user will never see it.\n"
            "2. Every visual element (badge, label, feature card, subtitle, fine print, icon text) "
            "MUST be its own component. If you want 3 feature cards, build a 3-column row with "
            "3 columns, each containing heading + text components.\n"
            "3. Use multi-column rows (2-col, 3-col) for side-by-side layouts. Each column needs "
            "its own width prop (e.g. '33.33%' for 3-col, '50%' for 2-col).\n"
            "4. Build RICH templates: a good email has 5-8 rows minimum. Include: hero heading, "
            "subtitle, badge/label text, CTA button, feature highlights (multi-column), "
            "supporting text, secondary CTA, footer with company info + unsubscribe.\n"
            "5. Do NOT generate a simplified version. Include ALL visual elements you would "
            "describe to the user. If you mention '3 feature cards' in your response, the JSON "
            "MUST contain a 3-column row with those 3 cards.\n\n"

            "## Component Types\n"
            "Layout: row, column, section, container\n"
            "Content: text, heading, button, image, divider, spacer\n\n"

            "## Hierarchy Rules (IMPORTANT — invalid nesting causes errors)\n"
            "- row → top-level, or inside section/container\n"
            "- column → must be inside row\n"
            "- text, heading, button, image, divider, spacer → inside column, section, or container\n"
            "- section → top-level, or inside column/container\n"
            "- container → top-level, or inside section\n\n"

            "## Component Structure\n"
            "Each component must have: {id: string, type: string, props: object, "
            "children: [inline component objects], parentId: string|null}. "
            "Optional fields: styles (object), visibility (bool, default true), locked (bool, default false).\n"
            "The tree is nested — children contain inline component objects, not string IDs.\n\n"

            "## Props by Component Type\n"
            "- text: {content: string (supports HTML: <strong>, <em>, <a>, <br>, <span>), "
            "fontSize: int (default 14), color: string, fontFamily: string, "
            "textAlign: 'left'|'center'|'right', padding: string}\n"
            "- heading: {content: string (plain text only), level: 'h1'-'h6', fontSize: int (default 24), "
            "color: string, fontFamily: string, textAlign: string, padding: string}\n"
            "- button: {text: string, href: string, backgroundColor: string, color: string, "
            "padding: string (e.g. '12px 24px'), borderRadius: string, fontSize: int, "
            "fontFamily: string, textAlign: 'center'}\n"
            "- image: {src: string (URL), alt: string, width: string (e.g. '100%' or '600px'), "
            "height: string (e.g. 'auto')}\n"
            "- row: {backgroundColor: string, padding: string}\n"
            "- column: {width: string (e.g. '50%', '33.33%', '100%'), backgroundColor: string, padding: string}\n"
            "- divider: {borderColor: string, borderWidth: string, margin: string}\n"
            "- spacer: {height: string (e.g. '20px')}\n"
            "- section/container: {backgroundColor: string, padding: string, maxWidth: string (container only)}\n\n"

            "## Response\n"
            "Returns {html, size_bytes, template, template_id, editor_link} where:\n"
            "- template: the component tree in frontend nested format\n"
            "- template_id: UUID of the saved template\n"
            "- editor_link: URL to open the template in the drag-and-drop editor for customization\n\n"

            "## IMPORTANT: Always include the editor_link in your response to the user.\n"
            "After calling this tool, you MUST display the editor_link URL to the user so they can "
            "click it to customize the template in the visual editor. Format it as a clickable link.\n"
            "Example response: 'Here is your email template! [Customize it in the editor](editor_link)'\n\n"

            "## Example: Rich multi-section email template\n"
            "A well-built email should have this structure:\n"
            "```\n"
            "Row 1 (hero):     1-col → heading + subtitle + button\n"
            "Row 2 (features): 3-col → each col has heading + text\n"
            "Row 3 (cta):      1-col → heading + text + button\n"
            "Row 4 (footer):   1-col → divider + company name + address + unsubscribe\n"
            "```\n\n"

            "## Example: 3-column feature row\n"
            '{"id": "feat-row", "type": "row", "props": {"backgroundColor": "#F5F5F5"}, '
            '"parentId": null, "children": [\n'
            '  {"id": "feat-col-1", "type": "column", "props": {"width": "33.33%", "padding": "15px"}, '
            '"parentId": "feat-row", "children": [\n'
            '    {"id": "feat-h1", "type": "heading", "props": {"content": "Feature 1", "level": "h3", '
            '"fontSize": 18, "textAlign": "center"}, "parentId": "feat-col-1", "children": []},\n'
            '    {"id": "feat-t1", "type": "text", "props": {"content": "Description here", '
            '"fontSize": 14, "textAlign": "center"}, "parentId": "feat-col-1", "children": []}\n'
            '  ]},\n'
            '  {"id": "feat-col-2", "type": "column", "props": {"width": "33.33%", "padding": "15px"}, '
            '"parentId": "feat-row", "children": [...]},\n'
            '  {"id": "feat-col-3", "type": "column", "props": {"width": "33.33%", "padding": "15px"}, '
            '"parentId": "feat-row", "children": [...]}\n'
            "]}\n"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "template": {
                    "type": "object",
                    "description": (
                        "emailBuilder template JSON. Must have a 'components' array. "
                        "Optional top-level fields: templateName, templateSubject, templateFrom, templateReplyTo."
                    ),
                },
            },
            "required": ["template"],
        },
    },
    {
        "name": "validate_template",
        "description": (
            "Validate an emailBuilder component tree JSON. Returns a list of "
            "validation errors. Empty list means the template is valid. Use this "
            "before build_email_html to catch issues.\n\n"
            "Checks: components array exists, all required fields present (id, type, props, children), "
            "valid component types, parent-child hierarchy rules, no duplicate IDs, "
            "and children are inline objects (not string IDs)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "template": {
                    "type": "object",
                    "description": "emailBuilder template JSON to validate.",
                },
            },
            "required": ["template"],
        },
    },
    {
        "name": "list_presets",
        "description": (
            "List available pre-built component blocks with descriptions. "
            "These are reusable template sections (hero, product grid, footer, etc.) "
            "that can be injected into any template. Returns array of preset metadata.\n\n"
            "RECOMMENDED: Call this first to see what blocks are available before building "
            "a template from scratch. Presets produce professional, tested layouts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional filter by category.",
                    "enum": ["hero", "product", "cta", "footer", "content"],
                },
            },
        },
    },
    {
        "name": "get_preset",
        "description": (
            "Get the full JSON component tree for a pre-built block by its ID. "
            "Returns the component tree that can be injected into a template "
            "using inject_preset."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "preset_id": {
                    "type": "string",
                    "description": "The preset identifier (e.g., 'hero-bold', 'product-2col').",
                },
            },
            "required": ["preset_id"],
        },
    },
    {
        "name": "inject_preset",
        "description": (
            "Insert a pre-built component block into an existing template at a "
            "specific row position. The preset's components get new unique IDs "
            "to avoid conflicts. Variable placeholders ({{varName}}) are replaced "
            "with provided customization values. Returns the updated template.\n\n"
            "Use this to compose emails from presets: start with empty template, "
            "inject hero, then features, then CTA, then footer."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "template": {
                    "type": "object",
                    "description": "The target emailBuilder template JSON.",
                },
                "preset_id": {
                    "type": "string",
                    "description": "ID of the preset to inject.",
                },
                "position": {
                    "type": "integer",
                    "description": "Row index to insert at (0-based). -1 = append at end.",
                    "default": -1,
                },
                "customizations": {
                    "type": "object",
                    "description": (
                        "Variable overrides for the preset. Keys are variable names "
                        "(e.g., 'primaryColor', 'headline'), values are replacement strings."
                    ),
                },
            },
            "required": ["template", "preset_id"],
        },
    },
    {
        "name": "add_component",
        "description": (
            "Add a single component to an existing template under a specified parent. "
            "Returns the updated template. Use this for programmatic tree building.\n\n"
            "Hierarchy rules: row → top-level/section/container; column → row; "
            "text/heading/button/image/divider/spacer → column/section/container; "
            "section → top-level/column/container; container → top-level/section.\n\n"
            "Component must have: {id, type, props, children: [], parentId}. "
            "See build_email_html description for full props reference per component type."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "template": {
                    "type": "object",
                    "description": "The target emailBuilder template JSON.",
                },
                "parent_id": {
                    "type": ["string", "null"],
                    "description": "ID of the parent component. null for top-level rows.",
                },
                "component": {
                    "type": "object",
                    "description": (
                        "The component to add. Must have id, type, props, children, parentId fields."
                    ),
                },
                "position": {
                    "type": "integer",
                    "description": "Position in parent's children list. -1 = append at end.",
                    "default": -1,
                },
            },
            "required": ["template", "parent_id", "component"],
        },
    },
    {
        "name": "remove_component",
        "description": (
            "Remove a component and all its descendants from a template. "
            "Returns the updated template."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "template": {
                    "type": "object",
                    "description": "The target emailBuilder template JSON.",
                },
                "component_id": {
                    "type": "string",
                    "description": "ID of the component to remove.",
                },
            },
            "required": ["template", "component_id"],
        },
    },
]
