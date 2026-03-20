from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base, TimestampMixin, _new_uuid


class TemplateLibraryItem(Base, TimestampMixin):
    __tablename__ = "template_library"

    id = Column(String, primary_key=True, default=_new_uuid)
    slug = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False, default="")
    industry = Column(String, nullable=False, default="other")
    purpose = Column(String, nullable=False, default="welcome")
    tone = Column(String, nullable=False, default="professional")
    layout_style = Column(String, default="standard")
    components = Column(JSONB, nullable=False, default=list)
    s3_key = Column(String, default="")
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "industry": self.industry,
            "purpose": self.purpose,
            "tone": self.tone,
            "layout_style": self.layout_style,
            "components": self.components,
            "is_active": self.is_active,
        }

    def to_summary(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "industry": self.industry,
            "purpose": self.purpose,
            "tone": self.tone,
        }
