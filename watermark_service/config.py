import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
DATABASE_URL = BASE_DIR / "app" / "database.db"

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpg", ".ts", ".gif"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB

FFMPEG_TIMEOUT = 600  # seconds for video processing
