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
