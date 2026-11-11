from __future__ import annotations

import asyncio
import logging
import shutil
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .config import settings
from .handlers import build_router
from .middlewares import CoreMiddleware

log = logging.getLogger("bot")

COMMANDS = {
    "en": [
        BotCommand(command="start", description="Start"),
        BotCommand(command="search", description="Search YouTube by name"),
        BotCommand(command="mp3", description="Download audio (name or link)"),
        BotCommand(command="settings", description="Language & default quality"),
        BotCommand(command="help", description="Help"),
    ],
    "ar": [
        BotCommand(command="start", description="ابدأ"),
        BotCommand(command="search", description="بحث بالاسم في يوتيوب"),
        BotCommand(command="mp3", description="تحميل صوت (اسم أو رابط)"),
        BotCommand(command="settings", description="اللغة والجودة الافتراضية"),
        BotCommand(command="help", description="مساعدة"),
    ],
}


def build_bot() -> Bot:
    session = None
    if settings.local_api_url:
        session = AiohttpSession(api=TelegramAPIServer.from_base(settings.local_api_url, is_local=True))
    return Bot(settings.bot_token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    mw = CoreMiddleware()
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)
    dp.include_router(build_router())

    @dp.errors()
    async def on_error(event) -> bool:
        log.exception("Unhandled error", exc_info=event.exception)
        return True

    return dp


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    path = "/webhook"
    app = web.Application()
    app.router.add_get("/health", lambda _r: web.json_response({"ok": True}))
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret).register(app, path=path)
    setup_application(app, dp, bot=bot)
    await bot.set_webhook(
        settings.webhook_url + path,
        secret_token=settings.webhook_secret,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", settings.port).start()
    log.info("Webhook mode on :%s -> %s", settings.port, settings.webhook_url + path)
    await asyncio.Event().wait()


async def main() -> None:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg/ffprobe are not installed or not in PATH.")

    shutil.rmtree(settings.download_dir, ignore_errors=True)  # leftovers from a previous run
    settings.download_dir.mkdir(parents=True, exist_ok=True)

    bot, dp = build_bot(), build_dispatcher()
    await bot.set_my_commands(COMMANDS["en"])
    await bot.set_my_commands(COMMANDS["ar"], language_code="ar")
    me = await bot.me()
    log.info("Started @%s (limit %s MB, local API: %s)", me.username, settings.max_file_mb, bool(settings.local_api_url))
    try:
        if settings.webhook_url:
            await run_webhook(bot, dp)
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)