#!/bin/sh
set -e
if [ "${AUTO_UPDATE_YTDLP:-1}" = "1" ]; then
  pip install --user --no-cache-dir -U "yt-dlp[default]" >/dev/null 2>&1 \
    && echo "yt-dlp updated" || echo "yt-dlp update skipped"
fi
exec python -m bot
