from __future__ import annotations

import re

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_BAD_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def extract_url(text: str | None) -> str | None:
    if not text:
        return None
    m = URL_RE.search(text)
    return m.group(0).rstrip(").,،;") if m else None


def human_size(n: float | None) -> str:
    if n is None:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def fmt_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "--:--"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def fmt_speed(bps: float | None) -> str:
    return f"{human_size(bps)}/s" if bps else "-"


def progress_bar(pct: float, width: int = 10) -> str:
    filled = max(0, min(width, int(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def truncate(text: str, n: int) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


def safe_filename(title: str, ext: str, limit: int = 80) -> str:
    base = _BAD_FILENAME.sub("", title or "").strip(" .") or "media"
    return f"{base[:limit].strip()}.{ext.lstrip('.')}"