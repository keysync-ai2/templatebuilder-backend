from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from models.base import Base, TimestampMixin, _new_uuid


class BrandProfile(Base, TimestampMixin):
    __tablename__ = "brand_profiles"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, nullable=False, unique=True, index=True)
    business_name = Column(String, nullable=False, default="")
    tagline = Column(String, default="")
    description = Column(Text, default="")
    website_url = Column(String, default="")
    logo_url = Column(String, default="")
    features = Column(ARRAY(String), default=list)
    primary_color = Column(String, default="#2563EB")
    secondary_color = Column(String, default="#1E40AF")
    industry = Column(String, default="other")  # saas, ecommerce, health, food, education, events, real_estate, agency, other
    tone = Column(String, default="professional")  # professional, casual, friendly, urgent, playful, minimal

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "business_name": self.business_name,
            "tagline": self.tagline,
            "description": self.description,
            "website_url": self.website_url,
            "logo_url": self.logo_url,
            "features": self.features or [],
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "industry": self.industry,
            "tone": self.tone,
        }
