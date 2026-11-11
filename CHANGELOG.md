# Changelog

## 2.0.0
- Search by name (`/search`, or just type text) and `/mp3` shortcut
- Playlist support (first N items), live-stream rejection, max-duration guard
- File-ID cache: previously downloaded media is re-sent instantly
- Automatic splitting of files larger than the Telegram limit
- Live progress with speed/ETA and a Cancel button
- Per-user settings (language, default quality), Arabic/English UI
- SQLite storage, daily limits, anti-flood, forced channel subscription
- Admin panel: `/stats`, `/broadcast`, `/ban`, `/unban`, `/user`, `/restart`
- Webhook mode + `/health` endpoint, Docker/compose, CI, unit tests

## 1.0.0
- Basic link downloader (video quality / MP3)
