from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base, TimestampMixin, _new_uuid


class Preset(Base, TimestampMixin):
    __tablename__ = "presets"

    id = Column(String, primary_key=True, default=_new_uuid)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)  # hero, product, cta, footer, content
    description = Column(String, default="")
    thumbnail_url = Column(String, default="")
    components = Column(JSONB, nullable=False, default=list)
    variables = Column(JSONB, default=dict)  # variable definitions with defaults
