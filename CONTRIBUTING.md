# Contributing

1. `make install` — install runtime + dev dependencies (needs ffmpeg on your PATH)
2. `make test` and `make lint` must pass before opening a pull request
3. Add a unit test for any new pure logic (see `tests/`); keep Telegram/yt-dlp calls in `jobs.py`, `downloader.py` and `handlers/`
4. New UI text goes in `bot/i18n.py` for **both** languages (a test checks they match)

If a site stops working, first update yt-dlp (`pip install -U yt-dlp`) and retry before filing an issue.
