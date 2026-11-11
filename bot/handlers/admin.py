from __future__ import annotations

import asyncio
import logging
import os
import signal

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ..config import settings
from ..context import db

log = logging.getLogger(__name__)
router = Router(name="admin")
router.message.filter(F.from_user.id.in_(settings.admin_ids))

_tasks: set[asyncio.Task] = set()

HELP = (
    "🛠 <b>Admin panel</b>\n"
    "/stats — usage statistics\n"
    "/broadcast text — send to all users (or reply to a message with /broadcast)\n"
    "/ban ID · /unban ID — block / unblock a user\n"
    "/user ID — user info\n"
    "/cleancache — forget cached file_ids\n"
    "/restart — restart the bot (Docker updates yt-dlp on start)"
)


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    s = await db.stats()
    await message.answer(
        "📊 <b>Statistics</b>\n"
        f"👥 Users: <b>{s['users']}</b> (new today {s['new_today']}, active today {s['active_today']}, banned {s['banned']})\n"
        f"⬇️ Downloads: <b>{s['downloads']}</b> (today {s['downloads_today']})\n"
        f"⚡ Cached files: <b>{s['cached_files']}</b>"
    )


def _uid(command: CommandObject) -> int | None:
    arg = (command.args or "").strip().split(" ")[0]
    return int(arg) if arg.lstrip("-").isdigit() else None


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject) -> None:
    uid = _uid(command)
    if uid is None:
        await message.answer("Usage: /ban USER_ID")
    elif uid in settings.admin_ids:
        await message.answer("Cannot ban an admin.")
    else:
        await message.answer("🚫 Banned." if await db.set_banned(uid, True) else "User not found.")


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject) -> None:
    uid = _uid(command)
    if uid is None:
        await message.answer("Usage: /unban USER_ID")
    else:
        await message.answer("✅ Unbanned." if await db.set_banned(uid, False) else "User not found.")


@router.message(Command("user"))
async def cmd_user(message: Message, command: CommandObject) -> None:
    uid = _uid(command)
    u = await db.get_user(uid) if uid is not None else None
    if not u:
        await message.answer("Usage: /user USER_ID (user must exist)")
        return
    await message.answer(
        f"👤 <code>{u['id']}</code> @{u['username'] or '-'}\n"
        f"Lang: {u['lang']} · Quality: {u['default_quality']} · Downloads: {u['downloads']} · Banned: {bool(u['banned'])}"
    )


@router.message(Command("cleancache"))
async def cmd_cleancache(message: Message) -> None:
    await message.answer(f"🧹 Removed {await db.cache_clear()} cached entries.")


@router.message(Command("restart"))
async def cmd_restart(message: Message) -> None:
    await message.answer("♻️ Restarting…")
    await asyncio.sleep(0.5)
    os.kill(os.getpid(), signal.SIGINT)


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject, bot: Bot) -> None:
    src = message.reply_to_message
    text = (command.args or "").strip()
    if not src and not text:
        await message.answer("Usage: /broadcast TEXT  — or reply to any message with /broadcast")
        return
    ids = await db.all_user_ids()
    await message.answer(f"📣 Sending to {len(ids)} users…")
    task = asyncio.create_task(_broadcast(bot, message.chat.id, ids, src, text))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _broadcast(bot: Bot, admin_chat: int, ids: list[int], src: Message | None, text: str) -> None:
    sent = blocked = failed = 0
    for uid in ids:
        for attempt in range(2):
            try:
                if src:
                    await bot.copy_message(uid, src.chat.id, src.message_id)
                else:
                    await bot.send_message(uid, text)
                sent += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except TelegramForbiddenError:
                blocked += 1
                break
            except TelegramAPIError:
                failed += 1
                break
        await asyncio.sleep(0.05)  # ~20 msg/s, below Telegram's limit
    await bot.send_message(admin_chat, f"✅ Broadcast finished.\nSent: {sent} · Blocked: {blocked} · Failed: {failed}")