import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DIR = os.path.dirname(__file__)
BPMN_DIR = os.path.join(BASE_DIR, "bpm", "workflows")

# JWT Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days


MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
MAIL_PORT_RAW = os.getenv("MAIL_PORT")
MAIL_PORT = int(MAIL_PORT_RAW) if (MAIL_PORT_RAW is not None and MAIL_PORT_RAW != "") else 587
MAIL_SERVER = os.getenv("MAIL_SERVER")
MAIL_STARTTLS = os.getenv("MAIL_STARTTLS") == "True"
MAIL_SSL_TLS = os.getenv("MAIL_SSL_TLS") == "True"

# Use Postmark HTTP API instead of SMTP (avoids port 587 block on Render/Heroku).
# When True, MAIL_PASSWORD is used as the Postmark API token (same value as for SMTP).
MAIL_USE_API = os.getenv("MAIL_USE_API", "false").lower() in ("true", "1", "yes")