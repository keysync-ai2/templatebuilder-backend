from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base, TimestampMixin, _new_uuid


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_new_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    widgets = Column(JSONB, default=list)  # widget payloads returned by assistant
