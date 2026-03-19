from sqlalchemy import Column, String, Integer, ForeignKey
from models.base import Base, TimestampMixin, _new_uuid


class Image(Base, TimestampMixin):
    __tablename__ = "images"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    s3_key = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, default=0)
