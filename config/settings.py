"""Environment variable loader — single source of truth for all config."""

import os


DATABASE_URL = os.environ.get("DATABASE_URL", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ACCESS_TTL = int(os.environ.get("JWT_ACCESS_TTL", "900"))       # 15 min
JWT_REFRESH_TTL = int(os.environ.get("JWT_REFRESH_TTL", "604800"))  # 7 days
S3_BUCKET = os.environ.get("S3_BUCKET", "")
CF_DISTRIBUTION_DOMAIN = os.environ.get("CF_DISTRIBUTION_DOMAIN", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
