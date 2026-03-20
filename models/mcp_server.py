from sqlalchemy import Column, String, Text, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from models.base import Base, TimestampMixin, _new_uuid


class MCPServer(Base, TimestampMixin):
    __tablename__ = "mcp_servers"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, index=True, nullable=True)  # NULL = system-wide
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    transport = Column(String(20), nullable=False, default="http")  # http | stdio | embedded
    url = Column(String(500), default="")
    command = Column(String(500), default="")
    api_key = Column(String(500), default="")
    headers = Column(JSONB, default=dict)
    is_enabled = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    tools_cache = Column(JSONB, default=list)
    last_connected_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self, hide_key=True):
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "transport": self.transport,
            "url": self.url,
            "is_enabled": self.is_enabled,
            "is_system": self.is_system,
            "tools": self.tools_cache or [],
            "tools_count": len(self.tools_cache or []),
            "last_connected_at": self.last_connected_at.isoformat() if self.last_connected_at else None,
        }
        if not hide_key:
            d["api_key"] = self.api_key
        return d
