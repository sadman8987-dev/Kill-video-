from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import settings
from .downloader import Item, MediaInfo
from .formats import estimate_mp3_size
from .i18n import LANGS, tr
from .utils import fmt_duration, human_size, truncate

QUALITY_CHOICES = ("ask", "360", "480", "720", "1080", "mp3")


def format_kb(token: str, info: MediaInfo, lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if info.has_video:
        for h in info.heights or [0]:
            label = f"🎬 {h}p" if h else "🎬 Best"
            if info.sizes.get(h):
                label += f" · ~{human_size(info.sizes[h])}"
            kb.button(text=label, callback_data=f"dl:{token}:v:{h}")
    mp3 = estimate_mp3_size(info.duration)
    kb.button(text="🎵 MP3" + (f" · ~{human_size(mp3)}" if mp3 else ""), callback_data=f"dl:{token}:a:0")
    kb.adjust(2)
    return kb.as_markup()


def playlist_kb(token: str, lang: str, quality: int = 720) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, "pl_video", q=quality), callback_data=f"pl:{token}:v")
    kb.button(text=tr(lang, "pl_audio"), callback_data=f"pl:{token}:a")
    kb.adjust(2)
    return kb.as_markup()


def search_kb(token: str, items: list[Item]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, it in enumerate(items):
        kb.button(text=f"{truncate(it.title, 48)} · {fmt_duration(it.duration)}", callback_data=f"sr:{token}:{i}")
    kb.adjust(1)
    return kb.as_markup()


def cancel_kb(job_id: str, lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, "cancel"), callback_data=f"cx:{job_id}")
    return kb.as_markup()


def settings_kb(user: dict, lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code in LANGS:
        mark = "✅ " if user["lang"] == code else ""
        kb.button(text=mark + tr(code, "lang_name"), callback_data=f"st:lang:{code}")
    kb.adjust(2)
    for q in QUALITY_CHOICES:
        label = tr(lang, "quality_ask") if q == "ask" else ("🎵 MP3" if q == "mp3" else f"{q}p")
        mark = "✅ " if user["default_quality"] == q else ""
        kb.button(text=mark + label, callback_data=f"st:q:{q}")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup()


def join_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    link = settings.force_sub_link
    if not link and settings.force_sub and settings.force_sub.startswith("@"):
        link = f"https://t.me/{settings.force_sub[1:]}"
    rows = []
    if link:
        rows.append([InlineKeyboardButton(text=tr(lang, "join_btn"), url=link)])
    rows.append([InlineKeyboardButton(text=tr(lang, "joined_btn"), callback_data="fs:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)