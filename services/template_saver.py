"""Auto-save template JSON to S3 + DB for MCP server.

Creates a template_saver callable that can be injected into EmailEngineMCPServer.
"""

import json
import logging

from config.s3 import upload_to_s3
from config.database import get_session
from config.settings import FRONTEND_URL
from models.template import Template

logger = logging.getLogger(__name__)


def create_template_saver(user_id: str = "mcp-anonymous"):
    """Create a template_saver callback bound to a user_id.

    Args:
        user_id: The user who owns the template. Defaults to "mcp-anonymous"
                 for standalone MCP usage without auth context.

    Returns:
        Callable(template_id, template_dict) -> {"template_id", "editor_link"}
    """

    def _save(template_id: str, template_dict: dict) -> dict:
        """Upload template JSON to S3 and create a DB record.

        Args:
            template_id: UUID for the template
            template_dict: The full template dict (nested format with components)

        Returns:
            {"template_id": str, "editor_link": str}
        """
        s3_key = f"templates/{template_id}.json"

        # Upload JSON to S3
        template_json = json.dumps(template_dict, ensure_ascii=False)
        upload_to_s3(s3_key, template_json.encode("utf-8"), "application/json")

        # Create DB record
        session = get_session()
        try:
            t = Template(
                id=template_id,
                user_id=user_id,
                name=template_dict.get("templateName", "Untitled"),
                subject=template_dict.get("templateSubject", ""),
                components=template_dict.get("components", []),
                s3_key=s3_key,
            )
            session.add(t)
            session.commit()
        finally:
            session.close()

        editor_link = f"{FRONTEND_URL.rstrip('/')}/editor/{template_id}"

        logger.info(f"Template saved: {template_id} → s3://{s3_key}")

        return {
            "template_id": template_id,
            "editor_link": editor_link,
        }

    return _save
