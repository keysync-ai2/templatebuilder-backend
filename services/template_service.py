"""Template CRUD helpers — uses engine/ for rendering."""

from sqlalchemy.orm import Session
from models.template import Template
from engine import build_html, validate_tree


def create_template(session: Session, user_id: str, name: str, components: list) -> Template:
    t = Template(user_id=user_id, name=name, components=components)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def get_template(session: Session, template_id: str, user_id: str) -> Template | None:
    return session.query(Template).filter_by(id=template_id, user_id=user_id).first()


def list_templates(session: Session, user_id: str) -> list[Template]:
    return session.query(Template).filter_by(user_id=user_id).order_by(Template.updated_at.desc()).all()


def update_template(session: Session, template_id: str, user_id: str, updates: dict) -> Template | None:
    t = get_template(session, template_id, user_id)
    if not t:
        return None
    for key, val in updates.items():
        if hasattr(t, key) and key not in ("id", "user_id", "created_at", "updated_at"):
            setattr(t, key, val)
    session.commit()
    session.refresh(t)
    return t


def delete_template(session: Session, template_id: str, user_id: str) -> bool:
    t = get_template(session, template_id, user_id)
    if not t:
        return False
    session.delete(t)
    session.commit()
    return True


def render_template(template_data: dict) -> dict:
    """Validate and render a template to HTML.

    Returns:
        {"html": str, "size_bytes": int} or {"errors": list}
    """
    errors = validate_tree(template_data)
    if errors:
        return {"errors": errors}

    html = build_html(template_data)
    return {"html": html, "size_bytes": len(html.encode("utf-8"))}
