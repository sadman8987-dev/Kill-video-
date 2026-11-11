from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from ..config import settings
from ..context import db
from ..downloader import MediaInfo, get_info, search
from ..formats import classify_error, pick_height
from ..i18n import TEXTS, tr
from ..jobs import cancel_job, is_busy, run_job, safe_edit
from ..keyboards import format_kb, playlist_kb, search_kb, settings_kb
from ..state import store
from ..utils import extract_url, fmt_duration, human_size, truncate

log = logging.getLogger(__name__)
router = Router(name="user")


def _maxdur(lang: str) -> str:
    return fmt_duration(settings.max_duration) if settings.max_duration else tr(lang, "unlimited")


def _default_choice(db_user: dict, info: MediaInfo) -> tuple[str, int] | None:
    """Return (mode, height) when the user configured a default quality, else None (= ask)."""
    pref = db_user["default_quality"]
    if pref == "ask":
        return None
    if pref == "mp3" or not info.has_video:
        return "audio", 0
    return "video", pick_height(info.heights, int(pref))


# ------------------------------------------------------------------ commands
@router.message(CommandStart())
async def cmd_start(message: Message, lang: str) -> None:
    name = html.escape(message.from_user.first_name if message.from_user else "")
    await message.answer(tr(lang, "start", name=name))


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str) -> None:
    await message.answer(tr(lang, "help", limit=human_size(settings.max_file_bytes),
                            pl=settings.max_playlist_items, maxdur=_maxdur(lang)))


@router.message(Command("settings"))
async def cmd_settings(message: Message, lang: str, db_user: dict) -> None:
    await message.answer(_settings_text(db_user, lang), reply_markup=settings_kb(db_user, lang))


@router.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject, lang: str) -> None:
    if not command.args:
        await message.answer(tr(lang, "search_usage"))
        return
    await handle_search(message, command.args.strip(), lang)


@router.message(Command("dl"))
async def cmd_dl(message: Message, command: CommandObject, lang: str, db_user: dict) -> None:
    url = extract_url(command.args)
    if not url:
        await message.answer(tr(lang, "dl_usage"))
        return
    await handle_url(message, url, lang, db_user)


@router.message(Command("mp3"))
async def cmd_mp3(message: Message, command: CommandObject, lang: str, db_user: dict) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer(tr(lang, "mp3_usage"))
        return
    url = extract_url(arg)
    if url:
        await handle_url(message, url, lang, db_user, force_audio=True)
        return
    status = await message.answer(tr(lang, "searching"))
    try:
        results = await search(arg, 1)
    except Exception:
        log.exception("search failed")
        await safe_edit(status, tr(lang, "failed"))
        return
    if not results:
        await safe_edit(status, tr(lang, "no_results"))
        return
    await run_job(message.bot, status, db_user, lang, results[:1], "audio", 0)


# ------------------------------------------------------------------ plain text
@router.message(F.text, F.chat.type == ChatType.PRIVATE, ~F.text.startswith("/"))
async def on_text(message: Message, lang: str, db_user: dict) -> None:
    text = message.text.strip()
    url = extract_url(text)
    if url:
        await handle_url(message, url, lang, db_user)
    elif len(text) >= 2:
        await handle_search(message, text, lang)


# ------------------------------------------------------------------ flows
async def handle_search(message: Message, query: str, lang: str) -> None:
    status = await message.answer(tr(lang, "searching"))
    try:
        results = await search(query, settings.search_results)
    except Exception:
        log.exception("search failed for %r", query)
        await safe_edit(status, tr(lang, "failed"))
        return
    if not results:
        await safe_edit(status, tr(lang, "no_results"))
        return
    token = store.put(results)
    await safe_edit(status, tr(lang, "search_pick", q=html.escape(truncate(query, 60))),
                    reply_markup=search_kb(token, results))


async def handle_url(message: Message, url: str, lang: str, db_user: dict, force_audio: bool = False) -> None:
    status = await message.answer(tr(lang, "analyzing"))
    try:
        info = await get_info(url, settings.max_playlist_items)
    except Exception as e:
        log.warning("info failed for %s: %s", url, e)
        await safe_edit(status, tr(lang, classify_error(str(e))))
        return

    if info.is_live:
        await safe_edit(status, tr(lang, "live"))
        return
    if settings.max_duration and info.duration and info.duration > settings.max_duration:
        await safe_edit(status, tr(lang, "too_long", max=_maxdur(lang)))
        return

    if force_audio:
        await run_job(message.bot, status, db_user, lang, info.items, "audio", 0)
        return

    token = store.put(info)
    if info.is_playlist:
        text = tr(lang, "playlist", title=html.escape(truncate(info.title, 80)), n=info.total, m=len(info.items))
        await safe_edit(status, text, reply_markup=playlist_kb(token, lang))
        return

    choice = _default_choice(db_user, info)
    if choice:
        await run_job(message.bot, status, db_user, lang, info.items, choice[0], choice[1])
        return

    dur = fmt_duration(info.duration)
    text = f"<b>{html.escape(truncate(info.title, 200))}</b>\n⏱ {dur}\n\n{tr(lang, 'choose')}"
    await safe_edit(status, text, reply_markup=format_kb(token, info, lang))


# ------------------------------------------------------------------ callbacks
@router.callback_query(F.data.startswith("dl:"))
async def cb_download(cb: CallbackQuery, lang: str, db_user: dict) -> None:
    try:
        _, token, mode_key, height_s = (cb.data or "").split(":")
        height = int(height_s)
    except ValueError:
        await cb.answer()
        return
    info = store.get(token)
    if not isinstance(info, MediaInfo) or not isinstance(cb.message, Message):
        await cb.answer(tr(lang, "expired"), show_alert=True)
        return
    if is_busy(cb.from_user.id):
        await cb.answer(tr(lang, "busy"), show_alert=True)
        return
    await cb.answer()
    mode = "audio" if mode_key == "a" else "video"
    await run_job(cb.bot, cb.message, db_user, lang, info.items, mode, height)


@router.callback_query(F.data.startswith("pl:"))
async def cb_playlist(cb: CallbackQuery, lang: str, db_user: dict) -> None:
    try:
        _, token, mode_key = (cb.data or "").split(":")
    except ValueError:
        await cb.answer()
        return
    info = store.get(token)
    if not isinstance(info, MediaInfo) or not isinstance(cb.message, Message):
        await cb.answer(tr(lang, "expired"), show_alert=True)
        return
    if is_busy(cb.from_user.id):
        await cb.answer(tr(lang, "busy"), show_alert=True)
        return
    await cb.answer()
    mode = "audio" if mode_key == "a" else "video"
    await run_job(cb.bot, cb.message, db_user, lang, info.items, mode, 0 if mode == "audio" else 720)


@router.callback_query(F.data.startswith("sr:"))
async def cb_search_pick(cb: CallbackQuery, lang: str, db_user: dict) -> None:
    try:
        _, token, idx_s = (cb.data or "").split(":")
        idx = int(idx_s)
    except ValueError:
        await cb.answer()
        return
    results = store.get(token)
    if not isinstance(results, list) or not isinstance(cb.message, Message) or not 0 <= idx < len(results):
        await cb.answer(tr(lang, "expired"), show_alert=True)
        return
    await cb.answer()
    await handle_url(cb.message, results[idx].url, lang, db_user)


@router.callback_query(F.data.startswith("cx:"))
async def cb_cancel(cb: CallbackQuery) -> None:
    job_id = (cb.data or "").split(":", 1)[1]
    cancel_job(job_id, cb.from_user.id)
    await cb.answer()


def _settings_text(db_user: dict, lang: str) -> str:
    q = db_user["default_quality"]
    label = tr(lang, "quality_ask") if q == "ask" else ("MP3" if q == "mp3" else f"{q}p")
    return tr(lang, "settings", lang=tr(db_user["lang"], "lang_name"), quality=label)


@router.callback_query(F.data.startswith("st:"))
async def cb_settings(cb: CallbackQuery, db_user: dict) -> None:
    parts = (cb.data or "").split(":")
    if len(parts) != 3 or not isinstance(cb.message, Message):
        await cb.answer()
        return
    _, kind, value = parts
    if kind == "lang" and value in TEXTS:
        await db.set_lang(db_user["id"], value)
    elif kind == "q" and value in ("ask", "360", "480", "720", "1080", "mp3"):
        await db.set_quality(db_user["id"], value)
    else:
        await cb.answer()
        return
    fresh = await db.get_user(db_user["id"])
    lang = fresh["lang"]
    await cb.answer(tr(lang, "saved"))
    await safe_edit(cb.message, _settings_text(fresh, lang), reply_markup=settings_kb(fresh, lang))