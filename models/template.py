from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base, TimestampMixin, _new_uuid


class Template(Base, TimestampMixin):
    __tablename__ = "templates"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, default="Untitled")
    subject = Column(String, default="")
    components = Column(JSONB, nullable=False, default=list)  # component tree
    thumbnail_url = Column(String, default="")
