from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional at import time (tests)
    pass


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    return float(raw) if raw else default


def _str(name: str) -> str | None:
    return os.getenv(name, "").strip() or None


def parse_ids(value: str) -> frozenset[int]:
    out: set[int] = set()
    for part in value.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.add(int(part))
    return frozenset(out)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    local_api_url: str | None
    max_file_mb: int
    download_dir: Path
    db_path: str
    allowed_users: frozenset[int]
    admin_ids: frozenset[int]
    max_concurrent: int
    daily_limit: int
    cooldown: float
    max_playlist_items: int
    max_duration: int
    search_results: int
    cookies_file: str | None
    proxy: str | None
    upload_timeout: int
    download_timeout: int
    force_sub: str | None
    force_sub_link: str | None
    webhook_url: str | None
    webhook_secret: str
    port: int
    log_level: str

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is missing. Copy .env.example to .env and fill it.")
    local_api = _str("LOCAL_API_URL")
    default_limit = 1900 if local_api else 50  # cloud Bot API: 50MB, local server: up to 2000MB
    return Settings(
        bot_token=token,
        local_api_url=local_api,
        max_file_mb=_int("MAX_FILE_MB", default_limit),
        download_dir=Path(os.getenv("DOWNLOAD_DIR", "downloads")),
        db_path=os.getenv("DB_PATH", "data/bot.db"),
        allowed_users=parse_ids(os.getenv("ALLOWED_USERS", "")),
        admin_ids=parse_ids(os.getenv("ADMIN_IDS", "")),
        max_concurrent=max(1, _int("MAX_CONCURRENT", 3)),
        daily_limit=_int("DAILY_LIMIT", 0),
        cooldown=_float("COOLDOWN", 1.0),
        max_playlist_items=max(1, _int("MAX_PLAYLIST_ITEMS", 10)),
        max_duration=_int("MAX_DURATION", 10800),
        search_results=min(10, max(1, _int("SEARCH_RESULTS", 5))),
        cookies_file=_str("COOKIES_FILE"),
        proxy=_str("PROXY"),
        upload_timeout=_int("UPLOAD_TIMEOUT", 900),
        download_timeout=_int("DOWNLOAD_TIMEOUT", 1800),
        force_sub=_str("FORCE_SUB"),
        force_sub_link=_str("FORCE_SUB_LINK"),
        webhook_url=(_str("WEBHOOK_URL") or "").rstrip("/") or None,
        webhook_secret=_str("WEBHOOK_SECRET") or secrets.token_urlsafe(24),
        port=_int("PORT", 8080),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


settings = load_settings()