import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
TEXTBOOKS_DIR = DATA_DIR / "textbooks"
PAGE_IMAGES_DIR = DATA_DIR / "page_images"
SUBMISSIONS_DIR = DATA_DIR / "submissions"
CACHE_DIR = DATA_DIR / "cache"
DATABASE_URL = f"sqlite:///{DATA_DIR}/mathtutor.db"

for _d in [DATA_DIR, TEXTBOOKS_DIR, PAGE_IMAGES_DIR, SUBMISSIONS_DIR, CACHE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

SECRET_KEY: str = os.environ.get("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

DEFAULT_LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
DEFAULT_LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
DEFAULT_LLM_MODEL = os.environ.get("LLM_MODEL_NAME", "gpt-4o")
DEFAULT_LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
DEFAULT_OCR_MODE = os.environ.get("OCR_MODE", "hybrid")
LAN_ONLY_MODE = os.environ.get("LAN_ONLY_MODE", "1")
DEBUG = os.environ.get("DEBUG", "0") == "1"

ALLOWED_TEXTBOOK_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_SIZE_MB = 100

GRADE_LEVEL = 8

# Fix #4: Multi-subject support
SUPPORTED_SUBJECTS = [
    "Mathematics",
    "Science",
    "Physics",
    "Chemistry",
    "Biology",
    "Social Science",
    "English",
    "History",
    "Geography",
]
