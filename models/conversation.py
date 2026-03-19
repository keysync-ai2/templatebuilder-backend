from sqlalchemy import Column, String, ForeignKey
from models.base import Base, TimestampMixin, _new_uuid


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, default="New Conversation")
