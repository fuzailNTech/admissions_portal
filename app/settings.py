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


MAIL_USERNAME=os.getenv("MAIL_USERNAME")
MAIL_PASSWORD=os.getenv("MAIL_PASSWORD")
MAIL_FROM=os.getenv("MAIL_FROM")
MAIL_PORT=int(os.getenv("MAIL_PORT"))
MAIL_SERVER=os.getenv("MAIL_SERVER")
MAIL_STARTTLS=os.getenv("MAIL_STARTTLS") == "True"
MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS") == "True"