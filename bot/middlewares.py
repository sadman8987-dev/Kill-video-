from __future__ import annotations

import logging
import time

from aiogram import BaseMiddleware, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message

from .config import settings
from .context import db
from .i18n import normalize_lang, tr
from .keyboards import join_kb

log = logging.getLogger(__name__)

_MEMBER_STATUSES = {"creator", "administrator", "member", "restricted"}
_member_cache: dict[int, float] = {}  # user_id -> time of last positive check
_last_msg: dict[int, float] = {}


async def is_member(bot: Bot, user_id: int) -> bool:
    if not settings.force_sub:
        return True
    if time.time() - _member_cache.get(user_id, 0) < 120:
        return True
    try:
        member = await bot.get_chat_member(settings.force_sub, user_id)
    except TelegramAPIError:
        log.warning("force-sub check failed (is the bot an admin of %s?)", settings.force_sub)
        return True  # fail open so a misconfiguration never locks everybody out
    status = getattr(member.status, "value", member.status)
    ok = status in _MEMBER_STATUSES
    if ok:
        _member_cache[user_id] = time.time()
    return ok


class CoreMiddleware(BaseMiddleware):
    """Access list -> user registration -> ban -> flood control -> forced subscription."""

    async def __call__(self, handler, event, data):
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        lang_guess = normalize_lang(tg_user.language_code)
        is_admin = tg_user.id in settings.admin_ids

        if settings.allowed_users and tg_user.id not in settings.allowed_users and not is_admin:
            await self._notify(event, tr(lang_guess, "private"))
            return None

        user = await db.upsert_user(tg_user.id, tg_user.username, tg_user.first_name, lang_guess)
        lang = user["lang"]

        if user["banned"] and not is_admin:
            await self._notify(event, tr(lang, "banned"))
            return None

        if isinstance(event, Message) and not is_admin and settings.cooldown:
            now = time.monotonic()
            if now - _last_msg.get(tg_user.id, 0) < settings.cooldown:
                return None  # drop flood silently
            _last_msg[tg_user.id] = now
            if len(_last_msg) > 20000:
                _last_msg.clear()

        if settings.force_sub and not is_admin:
            bot: Bot = data["bot"]
            if isinstance(event, CallbackQuery) and event.data == "fs:check":
                if await is_member(bot, tg_user.id):
                    await event.answer(tr(lang, "thanks"), show_alert=True)
                    if isinstance(event.message, Message):
                        try:
                            await event.message.delete()
                        except TelegramAPIError:
                            pass
                else:
                    await event.answer(tr(lang, "not_joined"), show_alert=True)
                return None
            if not await is_member(bot, tg_user.id):
                if isinstance(event, Message):
                    await event.answer(tr(lang, "force_sub"), reply_markup=join_kb(lang))
                elif isinstance(event, CallbackQuery):
                    await event.answer(tr(lang, "force_sub"), show_alert=True)
                return None

        data["db_user"] = user
        data["lang"] = lang
        return await handler(event, data)

    @staticmethod
    async def _notify(event, text: str) -> None:
        try:
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
        except TelegramAPIError:
            pass