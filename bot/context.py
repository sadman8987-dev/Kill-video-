"""Process-wide singletons."""
from .config import settings
from .db import Database

db = Database(settings.db_path)