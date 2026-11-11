FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# JS runtime required by yt-dlp for some sites (YouTube)
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

RUN useradd -m -u 1000 app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot ./bot
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh \
    && mkdir -p /app/data /app/downloads \
    && chown -R app:app /app

USER app
ENV PATH="/home/app/.local/bin:${PATH}"
VOLUME ["/app/data"]
EXPOSE 8080
ENTRYPOINT ["./entrypoint.sh"]
