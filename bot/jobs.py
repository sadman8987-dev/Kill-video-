"""Download job runner: cache lookup -> download (with progress/cancel) -> split -> upload -> cache."""
from __future__ import annotations

import asyncio
import html
import logging
import shutil
import threading
from dataclasses import dataclass, field
from uuid import uuid4

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import FSInputFile, Message

from .config import settings
from .context import db
from .downloader import DownloadCancelled, DownloadResult, Item, download
from .formats import cache_key, classify_error
from .i18n import tr
from .keyboards import cancel_kb
from .media import make_thumbnail, split_file
from .utils import fmt_duration, fmt_speed, progress_bar, safe_filename, truncate

log = logging.getLogger(__name__)

_semaphore = asyncio.Semaphore(settings.max_concurrent)
_active: dict[int, "Job"] = {}
_jobs: dict[str, "Job"] = {}


@dataclass
class Job:
    user_id: int
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    cancel: threading.Event = field(default_factory=threading.Event)


def is_busy(user_id: int) -> bool:
    return user_id in _active


def cancel_job(job_id: str, user_id: int) -> bool:
    job = _jobs.get(job_id)
    if job and job.user_id == user_id:
        job.cancel.set()
        return True
    return False


async def safe_edit(msg: Message, text: str, **kwargs) -> None:
    try:
        await msg.edit_text(text, **kwargs)
    except TelegramAPIError:
        pass  # not modified / deleted / flood-wait: harmless


def _caption(title: str, bot_username: str | None, part: tuple[int, int] | None = None) -> str:
    cap = f"<b>{html.escape(truncate(title, 180))}</b>"
    if part:
        cap += f"\n📦 {part[0]}/{part[1]}"
    if bot_username:
        cap += f"\n\n🤖 @{bot_username}"
    return cap


async def _send_cached(bot: Bot, chat_id: int, cached: dict, caption: str) -> None:
    kind = cached["kind"]
    if kind == "audio":
        await bot.send_audio(chat_id, cached["file_id"], caption=caption, request_timeout=settings.upload_timeout)
    elif kind == "video":
        await bot.send_video(chat_id, cached["file_id"], caption=caption, supports_streaming=True,
                             request_timeout=settings.upload_timeout)
    else:
        await bot.send_document(chat_id, cached["file_id"], caption=caption, request_timeout=settings.upload_timeout)


async def _send_file(bot: Bot, chat_id: int, path, mode: str, res: DownloadResult, caption: str,
                     thumb, single: bool) -> tuple[str | None, str]:
    media = FSInputFile(path, filename=safe_filename(res.title, path.suffix))
    thumbnail = FSInputFile(thumb) if thumb else None
    if mode == "audio":
        m = await bot.send_audio(
            chat_id, media, caption=caption, title=truncate(res.title, 100), performer=res.uploader,
            duration=res.duration if single else None, thumbnail=thumbnail,
            request_timeout=settings.upload_timeout,
        )
        return (m.audio.file_id if m.audio else None), "audio"
    m = await bot.send_video(
        chat_id, media, caption=caption, width=res.width, height=res.height,
        duration=res.duration if single else None, supports_streaming=True, thumbnail=thumbnail,
        request_timeout=settings.upload_timeout,
    )
    if m.video:
        return m.video.file_id, "video"
    return (m.document.file_id if m.document else None), "document"


async def _process_item(bot: Bot, status: Message, job: Job, user: dict, lang: str, bot_username: str | None,
                        item: Item, idx: int, total: int, mode: str, height: int) -> None:
    chat_id = status.chat.id
    idx_txt = f"({idx}/{total})" if total > 1 else ""
    key = cache_key(item.key, mode, height) if item.key else None
    quality = "audio" if mode == "audio" else str(height or "best")

    # 1) instant path: already uploaded before -> reuse Telegram's file_id
    if key:
        cached = await db.cache_get(key)
        if cached:
            try:
                await _send_cached(bot, chat_id, cached, _caption(item.title, bot_username))
                await db.log_download(user["id"], item.url, item.title, mode, quality, 0)
                return
            except TelegramBadRequest:
                await db.cache_delete(key)  # stale file_id -> fall through to a normal download

    workdir = settings.download_dir / uuid4().hex
    loop = asyncio.get_running_loop()
    last_edit = 0.0
    finished_notified = False
    markup = cancel_kb(job.id, lang)

    def hook(d: dict) -> None:  # runs in the yt-dlp worker thread
        nonlocal last_edit, finished_notified
        if job.cancel.is_set():
            raise DownloadCancelled()
        status_name = d.get("status")
        if status_name == "downloading":
            now = loop.time()
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
            if not total_bytes or now - last_edit < 3:
                return
            last_edit = now
            pct = (d.get("downloaded_bytes") or 0) / total_bytes * 100
            text = tr(lang, "downloading", idx=idx_txt, title=html.escape(truncate(item.title, 60)),
                      bar=progress_bar(pct), pct=int(pct), speed=fmt_speed(d.get("speed")),
                      eta=fmt_duration(d.get("eta")))
            asyncio.run_coroutine_threadsafe(safe_edit(status, text, reply_markup=markup), loop)
        elif status_name == "finished" and not finished_notified:
            finished_notified = True
            asyncio.run_coroutine_threadsafe(
                safe_edit(status, tr(lang, "processing", idx=idx_txt), reply_markup=markup), loop)

    try:
        await safe_edit(status, tr(lang, "queued"), reply_markup=markup)
        async with _semaphore:
            await safe_edit(
                status,
                tr(lang, "downloading", idx=idx_txt, title=html.escape(truncate(item.title, 60)),
                   bar=progress_bar(0), pct=0, speed="-", eta="--:--"),
                reply_markup=markup,
            )
            try:
                res = await asyncio.wait_for(
                    download(item.url, mode, height, workdir, hook), timeout=settings.download_timeout)
            except asyncio.TimeoutError:
                job.cancel.set()  # tells the worker thread to stop
                raise
        if job.cancel.is_set():
            raise DownloadCancelled()

        thumb = await make_thumbnail(res.thumb_src, workdir / "thumb.jpg") if res.thumb_src else None
        files = [res.path]
        if res.size > settings.max_file_bytes:
            await safe_edit(status, tr(lang, "splitting"))
            files = await split_file(res.path, settings.max_file_bytes, res.duration)

        await safe_edit(status, tr(lang, "uploading", idx=idx_txt))
        file_id, kind = None, "document"
        for n, f in enumerate(files, 1):
            part = (n, len(files)) if len(files) > 1 else None
            file_id, kind = await _send_file(
                bot, chat_id, f, mode, res, _caption(res.title, bot_username, part), thumb, single=part is None)
        if key and len(files) == 1 and file_id:
            await db.cache_put(key, file_id, kind)
        await db.log_download(user["id"], item.url, res.title, mode, quality, res.size)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def run_job(bot: Bot, status: Message, user: dict, lang: str, items: list[Item], mode: str, height: int) -> None:
    uid = user["id"]
    if uid in _active:
        await safe_edit(status, tr(lang, "busy"))
        return
    if settings.daily_limit and uid not in settings.admin_ids:
        used = await db.count_downloads_today(uid)
        if used >= settings.daily_limit:
            await safe_edit(status, tr(lang, "daily_limit", n=settings.daily_limit))
            return
        items = items[: settings.daily_limit - used]

    job = Job(user_id=uid)
    _active[uid] = job
    _jobs[job.id] = job
    me = await bot.me()
    ok = 0
    try:
        for i, item in enumerate(items, 1):
            if job.cancel.is_set():
                break
            try:
                await _process_item(bot, status, job, user, lang, me.username, item, i, len(items), mode, height)
                ok += 1
            except Exception:
                if job.cancel.is_set() or len(items) == 1:
                    raise
                log.exception("playlist item failed: %s", item.url)  # skip a broken item, keep going
        if job.cancel.is_set():
            await safe_edit(status, tr(lang, "cancelled"), reply_markup=None)
        elif len(items) > 1:
            await safe_edit(status, tr(lang, "playlist_done", ok=ok, n=len(items)), reply_markup=None)
        else:
            try:
                await status.delete()
            except TelegramAPIError:
                pass
    except Exception as e:
        if job.cancel.is_set() or isinstance(e, DownloadCancelled):
            await safe_edit(status, tr(lang, "cancelled"), reply_markup=None)
        else:
            log.exception("job failed")
            await safe_edit(status, tr(lang, classify_error(str(e))), reply_markup=None)
    finally:
        _active.pop(uid, None)
        _jobs.pop(job.id, None)