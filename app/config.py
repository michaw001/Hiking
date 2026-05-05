import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'hiking.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    UPLOAD_EXTENSIONS = {".gpx"}
    USER_DATA_DIR = BASE_DIR / "user_data"
    WTF_CSRF_ENABLED = True
