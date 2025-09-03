import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DIR = os.path.dirname(__file__)
BPMN_DIR = os.path.join(BASE_DIR, "bpm", "workflows")
