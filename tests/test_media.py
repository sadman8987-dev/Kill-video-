import asyncio
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bot.media import make_thumbnail, probe_duration, split_file

HAVE_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not installed")
class MediaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = self.tmp / "v.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=15",
             "-f", "lavfi", "-i", "sine=frequency=440", "-t", "20", "-g", "15", "-pix_fmt", "yuv420p",
             "-c:v", "libx264", "-c:a", "aac", "-shortest", str(self.video)], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_probe(self):
        d = asyncio.run(probe_duration(self.video))
        self.assertTrue(19 < d < 21)

    def test_split(self):
        size = self.video.stat().st_size
        limit = size // 3
        parts = asyncio.run(split_file(self.video, limit, 20))
        self.assertGreaterEqual(len(parts), 3)
        self.assertTrue(all(p.stat().st_size <= limit for p in parts))
        total = sum(asyncio.run(probe_duration(p)) for p in parts)
        self.assertTrue(18 < total < 22)

    def test_thumbnail(self):
        src = self.tmp / "t.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720",
                        "-frames:v", "1", str(src)], check=True)
        out = asyncio.run(make_thumbnail(src, self.tmp / "thumb.jpg"))
        self.assertIsNotNone(out)
        self.assertLess(out.stat().st_size, 200 * 1024)


if __name__ == "__main__":
    unittest.main()
