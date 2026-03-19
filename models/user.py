from sqlalchemy import Column, String, Boolean
from models.base import Base, TimestampMixin, _new_uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_new_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, server_default="staff")
    is_active = Column(Boolean, server_default="true")
    phone = Column(String, nullable=True)
    name = Column(String, default="")
