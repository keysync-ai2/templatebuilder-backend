"""Preset CRUD — loads from DB, with S3 fallback for component JSON."""

from sqlalchemy.orm import Session
from models.preset import Preset


def list_presets(session: Session, category: str | None = None) -> list[dict]:
    query = session.query(Preset)
    if category:
        query = query.filter_by(category=category)
    presets = query.order_by(Preset.name).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "description": p.description,
            "thumbnail_url": p.thumbnail_url,
        }
        for p in presets
    ]


def get_preset(session: Session, preset_id: str) -> dict | None:
    p = session.query(Preset).filter_by(id=preset_id).first()
    if not p:
        return None
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "components": p.components,
        "variables": p.variables,
    }
