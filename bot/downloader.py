from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yt_dlp
from yt_dlp.utils import DownloadCancelled

from .config import settings
from .formats import estimate_sizes, ladder_from_formats, video_selector

__all__ = ["DownloadCancelled", "Item", "MediaInfo", "DownloadResult", "get_info", "search", "download"]

log = logging.getLogger(__name__)

MEDIA_EXT = {".mp4", ".mp3", ".m4a", ".mkv", ".webm", ".opus", ".ogg", ".mov", ".aac", ".flac", ".wav"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class Item:
    url: str
    title: str
    duration: int | None = None
    uploader: str | None = None
    key: str | None = None  # "<extractor>:<id>" used for the file_id cache


@dataclass
class MediaInfo:
    title: str
    url: str
    items: list[Item]
    is_playlist: bool = False
    total: int = 1
    is_live: bool = False
    duration: int | None = None
    heights: list[int] = field(default_factory=list)
    sizes: dict[int, int | None] = field(default_factory=dict)
    has_video: bool = True


@dataclass
class DownloadResult:
    path: Path
    title: str
    duration: int | None
    uploader: str | None
    width: int | None
    height: int | None
    size: int
    thumb_src: Path | None


def _base_opts() -> dict:
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "concurrent_fragment_downloads": 4,
        "restrictfilenames": True,
        "geo_bypass": True,
    }
    if settings.cookies_file and Path(settings.cookies_file).is_file():
        opts["cookiefile"] = settings.cookies_file
    if settings.proxy:
        opts["proxy"] = settings.proxy
    return opts


def _is_single_video_url(url: str) -> bool:
    """A YouTube watch/short link carrying a list= param is treated as ONE video (not the whole mix)."""
    low = url.lower()
    return "list=" in low and ("v=" in low or "youtu.be/" in low)


def _entry_url(e: dict) -> str | None:
    url = e.get("url") or e.get("webpage_url")
    if url and url.startswith("http"):
        return url
    if e.get("id") and (e.get("ie_key") or "").lower() == "youtube":
        return f"https://www.youtube.com/watch?v={e['id']}"
    return None


def _key(info: dict) -> str | None:
    ext = (info.get("extractor_key") or info.get("ie_key") or "").lower()
    return f"{ext}:{info['id']}" if ext and info.get("id") else None


def _to_item(e: dict) -> Item | None:
    url = _entry_url(e)
    if not url:
        return None
    dur = e.get("duration")
    return Item(
        url=url,
        title=e.get("title") or "video",
        duration=int(dur) if dur else None,
        uploader=e.get("uploader") or e.get("channel"),
        key=_key(e),
    )


def _single(info: dict, url: str) -> MediaInfo:
    formats = info.get("formats") or []
    ladder = ladder_from_formats(formats)
    has_video = bool(ladder) or bool(info.get("height"))
    dur = int(info["duration"]) if info.get("duration") else None
    item = Item(
        url=info.get("webpage_url") or url,
        title=info.get("title") or "video",
        duration=dur,
        uploader=info.get("uploader") or info.get("channel"),
        key=_key(info),
    )
    return MediaInfo(
        title=item.title,
        url=item.url,
        items=[item],
        is_live=bool(info.get("is_live")),
        duration=dur,
        heights=ladder,
        sizes=estimate_sizes(formats, ladder),
        has_video=has_video,
    )


def _linkedin_direct_video(url: str) -> MediaInfo:
    """Fallback for publicly accessible LinkedIn posts, optionally using configured cookies/proxy."""
    import http.cookiejar
    from urllib.parse import urlparse

    handlers = []
    if settings.proxy:
        handlers.append(urllib.request.ProxyHandler({
            "http": settings.proxy,
            "https": settings.proxy,
        }))

    cookie_file = settings.cookies_file
    if cookie_file and Path(cookie_file).is_file():
        jar = http.cookiejar.MozillaCookieJar()
        try:
            jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
            handlers.append(urllib.request.HTTPCookieProcessor(jar))
        except (OSError, http.cookiejar.LoadError):
            log.warning("Could not load configured cookies file for LinkedIn fallback")

    opener = urllib.request.build_opener(*handlers)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    request = urllib.request.Request(url, headers=headers)
    with opener.open(request, timeout=30) as response:
        page = response.read().decode("utf-8", "ignore")
        final_url = response.geturl()

    sources: list[str] = []
    for match in re.finditer(r'data-sources="([^"]+)"', page):
        try:
            payload = json.loads(html.unescape(match.group(1)))
            for source in payload if isinstance(payload, list) else []:
                src = source.get("src") if isinstance(source, dict) else None
                if src and src.startswith("https://"):
                    sources.append(src)
        except (ValueError, TypeError):
            continue

    # Some public LinkedIn pages expose the media URL directly in page metadata.
    if not sources:
        candidates = re.findall(
            r'https?:\\?/\\?/dms\\.licdn\\.com[^"\\s<>]+',
            page,
        )
        sources = [html.unescape(value).replace("\\/", "/").replace("&amp;", "&") for value in candidates]

    # De-duplicate while preserving source order.
    sources = list(dict.fromkeys(sources))
    if not sources:
        raise RuntimeError(
            "LinkedIn video was not found. The post may be private, "
            "restricted, or require valid login cookies."
        )

    title_match = re.search(
        r'<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title)["\'][^>]+content=["\']([^"\']+)',
        page,
        re.I,
    )
    title = html.unescape(title_match.group(1)) if title_match else "LinkedIn video"
    direct_url = sources[0].replace("&amp;", "&")
    return MediaInfo(
        title=title,
        url=final_url or url,
        items=[Item(url=direct_url, title=title)],
        heights=[720],
        sizes={720: None},
        has_video=True,
    )

def _extract(url: str, max_items: int) -> MediaInfo:
    opts = {
        **_base_opts(),
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": _is_single_video_url(url),
        "playlistend": max_items,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        if "linkedin.com" not in url.lower():
            raise
        log.warning("yt-dlp extraction failed for LinkedIn; trying direct video fallback", exc_info=True)
        return _linkedin_direct_video(url)
    if info.get("_type") == "playlist":
        items = [i for i in (_to_item(e) for e in (info.get("entries") or []) if e) if i]
        if not items:
            raise ValueError("empty playlist")
        if len(items) == 1:
            return _extract_single(items[0].url)
        return MediaInfo(
            title=info.get("title") or "playlist",
            url=url,
            items=items,
            is_playlist=True,
            total=int(info.get("playlist_count") or len(items)),
        )
    return _single(info, url)


def _extract_single(url: str) -> MediaInfo:
    with yt_dlp.YoutubeDL({**_base_opts(), "skip_download": True, "noplaylist": True}) as ydl:
        return _single(ydl.extract_info(url, download=False), url)


def _search(query: str, n: int) -> list[Item]:
    opts = {**_base_opts(), "skip_download": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    items = [i for i in (_to_item({**e, "ie_key": e.get("ie_key") or "Youtube"}) for e in (info.get("entries") or []) if e) if i]
    return items


def _download(url: str, mode: str, height: int, workdir: Path, hook: Callable[[dict], None]) -> DownloadResult:
    opts = {
        **_base_opts(),
        "noplaylist": True,
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "progress_hooks": [hook],
        "writethumbnail": True,
    }
    if mode == "audio":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "FFmpegMetadata"},
        ]
    else:
        opts["format"] = video_selector(height)
        opts["merge_output_format"] = "mp4"
        opts["postprocessors"] = [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    if info.get("_type") == "playlist":
        info = (info.get("entries") or [info])[0]

    files = [p for p in workdir.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_EXT]
    if not files:
        raise RuntimeError("no output file produced")
    wanted = ".mp3" if mode == "audio" else ".mp4"
    path = next((p for p in files if p.suffix.lower() == wanted), max(files, key=lambda p: p.stat().st_size))
    thumbs = [p for p in workdir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXT]
    dur = info.get("duration")
    return DownloadResult(
        path=path,
        title=info.get("title") or "media",
        duration=int(dur) if dur else None,
        uploader=info.get("uploader") or info.get("channel"),
        width=info.get("width"),
        height=info.get("height"),
        size=path.stat().st_size,
        thumb_src=thumbs[0] if thumbs else None,
    )


async def get_info(url: str, max_items: int = 10) -> MediaInfo:
    return await asyncio.to_thread(_extract, url, max_items)


async def search(query: str, n: int = 5) -> list[Item]:
    return await asyncio.to_thread(_search, query, n)


async def download(url: str, mode: str, height: int, workdir: Path, hook: Callable[[dict], None]) -> DownloadResult:
    workdir.mkdir(parents=True, exist_ok=True)
    return await asyncio.to_thread(_download, url, mode, height, workdir, hook)