from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base, TimestampMixin, _new_uuid


class ChatTask(Base, TimestampMixin):
    __tablename__ = "chat_tasks"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, nullable=False, index=True)
    conversation_id = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed
    message = Column(Text, default="")  # user's input message
    result_content = Column(Text, default="")  # assistant's text response
    result_widgets = Column(JSONB, default=list)  # assistant's widgets
    error_message = Column(Text, default="")
