# config.py
import os
from dotenv import load_dotenv

# Load sensitive data from a .env file
load_dotenv()

def _clean(val):
    if val:
        return val.strip().strip("'").strip('"')
    return val

# ==========================================
# 1. PASSWORDS & SECURITY (via Environment)
# ==========================================
DB_NAME = _clean(os.getenv("DB_NAME"))
DB_USER = _clean(os.getenv("DB_USER"))
DB_PASSWORD = _clean(os.getenv("DB_PASSWORD"))
DB_HOST = _clean(os.getenv("DB_HOST"))
DB_PORT = _clean(os.getenv("DB_PORT"))

# Build connection string (PostgreSQL)
DB_CONNECTION_STRING = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    if all([DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT])
    else None
)
# LLM
# LLM_API_KEY = _clean(os.getenv("LLM_API_KEY"))
MODEL_NAME = 'aya'

# ==========================================
# 2. APPLICATION VARIABLES & THRESHOLDS
# ==========================================
DEFAULT_MODEL = "aya"
SIMILARITY_THRESHOLD = 0.85
MOOD_SENSITIVITY = 1.2

# ==========================================
# 3. TASK DEFINITIONS & REQUIRED VARIABLES
# ==========================================
TASKS_CONFIG = {
    "schedule_meeting": {
        "required_vars": ["meeting_subject", "date", "time"],
        "optional_vars": ["location", "participants"],
        "initial_state": "COLLECTING_DATA"
    },
    "file_search": {
        "required_vars": ["search_query"],
        "optional_vars": ["file_type", "date_range"],
        "initial_state": "SEARCHING"
    }
}