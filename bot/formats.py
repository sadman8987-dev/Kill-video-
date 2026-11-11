"""Pure helpers about formats / errors (no third-party imports, easy to unit-test)."""
from __future__ import annotations

HEIGHT_LADDER = (360, 480, 720, 1080, 1440, 2160)
MP3_BYTES_PER_SEC = 24_000  # 192 kbps


def _has(codec: str | None) -> bool:
    return codec not in (None, "none")


def _fsize(f: dict) -> int | None:
    return f.get("filesize") or f.get("filesize_approx")


def video_selector(height: int) -> str:
    """yt-dlp format selector. Prefers H.264/AAC (plays everywhere in Telegram), falls back gracefully."""
    h = f"[height<={height}]" if height else ""
    return f"bv*{h}[vcodec^=avc1]+ba[acodec^=mp4a]/bv*{h}+ba/b{h}/b"


def ladder_from_formats(formats: list[dict], limit: int = 4) -> list[int]:
    heights = {f["height"] for f in formats if f.get("height") and _has(f.get("vcodec"))}
    max_h = max(heights, default=0)
    if not max_h:
        return []
    ladder = [h for h in HEIGHT_LADDER if h <= max_h]
    if not ladder:  # tiny videos (<360p)
        return [max_h]
    return ladder[-limit:]


def estimate_sizes(formats: list[dict], ladder: list[int]) -> dict[int, int | None]:
    vfmts = [f for f in formats if f.get("height") and _has(f.get("vcodec"))]
    afmts = [f for f in formats if _has(f.get("acodec")) and not _has(f.get("vcodec"))]
    best_a = max(afmts, key=lambda f: f.get("abr") or 0, default=None)
    audio = (_fsize(best_a) or 0) if best_a else 0
    out: dict[int, int | None] = {}
    for h in ladder:
        cands = [f for f in vfmts if f["height"] <= h]
        if not cands:
            out[h] = None
            continue
        top = max(f["height"] for f in cands)
        sizes = []
        for f in cands:
            if f["height"] != top or not _fsize(f):
                continue
            sizes.append(_fsize(f) + (0 if _has(f.get("acodec")) else audio))
        out[h] = max(sizes) if sizes else None
    return out


def pick_height(available: list[int], wanted: int) -> int:
    """Nearest available height not above `wanted` (or the lowest one). 0 = let yt-dlp choose best."""
    if not available:
        return 0
    below = [h for h in available if h <= wanted]
    return max(below) if below else min(available)


def estimate_mp3_size(duration: int | None) -> int | None:
    return int(duration * MP3_BYTES_PER_SEC) if duration else None


def cache_key(base: str, mode: str, height: int) -> str:
    return f"{base}:{'a' if mode == 'audio' else f'v{height}'}"


_ERRORS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("err_login", ("sign in", "log in", "login", "cookies", "confirm your age", "age-restricted",
                   "private video", "members-only", "authentication", "this video is private")),
    ("err_geo", ("not available in your country", "geo restrict", "geo-restrict", "blocked in your country",
                 "not made this video available in your country")),
    ("err_unsupported", ("unsupported url", "no video formats found", "no suitable extractor")),
    ("err_unavailable", ("video unavailable", "has been removed", "been deleted", "does not exist",
                         "http error 404", "no longer available", "account associated with this video has been terminated")),
    ("err_rate", ("http error 429", "too many requests", "rate-limit", "rate limit")),
)


def classify_error(message: str) -> str:
    m = (message or "").lower()
    for key, needles in _ERRORS:
        if any(n in m for n in needles):
            return key
    return "failed"