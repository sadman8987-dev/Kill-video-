"""ffmpeg helpers: thumbnails, duration probe and splitting oversized files (stdlib only)."""
from __future__ import annotations

import asyncio
import math
import shutil
from pathlib import Path


async def _run(*cmd: str, timeout: float = 600) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    return proc.returncode or 0, out.decode(errors="ignore"), err.decode(errors="ignore")


async def make_thumbnail(src: Path, dst: Path) -> Path | None:
    """Telegram wants a JPEG <= 200KB and <= 320px."""
    try:
        rc, _, _ = await _run(
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
            "-vf", "scale=w=320:h=-2", "-frames:v", "1", "-q:v", "4", str(dst), timeout=60,
        )
    except (asyncio.TimeoutError, OSError):
        return None
    if rc == 0 and dst.exists() and 0 < dst.stat().st_size < 200 * 1024:
        return dst
    return None


async def probe_duration(path: Path) -> float | None:
    try:
        rc, out, _ = await _run(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path), timeout=60,
        )
        return float(out.strip()) if rc == 0 and out.strip() else None
    except (asyncio.TimeoutError, OSError, ValueError):
        return None


async def split_file(path: Path, max_bytes: int, duration: float | None = None) -> list[Path]:
    """Split by time with stream copy (fast, no re-encode). Retries with more parts if a part is still too big."""
    size = path.stat().st_size
    dur = duration or await probe_duration(path)
    if not dur:
        raise RuntimeError("cannot determine duration for splitting")
    factor = 1.15
    for attempt in range(3):
        parts = max(2, math.ceil(size * factor / max_bytes))
        outdir = path.parent / f"parts{attempt}"
        outdir.mkdir(exist_ok=True)
        pattern = outdir / f"{path.stem}_%03d{path.suffix}"
        rc, _, err = await _run(
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
            "-map", "0:v?", "-map", "0:a?", "-c", "copy",
            "-f", "segment", "-segment_time", f"{dur / parts:.2f}", "-reset_timestamps", "1",
            str(pattern), timeout=1800,
        )
        files = sorted(outdir.glob(f"{path.stem}_*{path.suffix}"))
        if rc == 0 and files and all(f.stat().st_size <= max_bytes for f in files):
            return files
        shutil.rmtree(outdir, ignore_errors=True)
        factor *= 1.4
    raise RuntimeError("splitting failed")