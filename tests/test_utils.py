import unittest

from bot.utils import extract_url, fmt_duration, human_size, progress_bar, safe_filename, truncate


class UtilsTest(unittest.TestCase):
    def test_extract_url(self):
        self.assertEqual(extract_url("شوف ده https://youtu.be/abc123?t=5)."), "https://youtu.be/abc123?t=5")
        self.assertIsNone(extract_url("no link here"))
        self.assertIsNone(extract_url(None))

    def test_human_size(self):
        self.assertEqual(human_size(500), "500 B")
        self.assertEqual(human_size(1536), "1.5 KB")
        self.assertEqual(human_size(50 * 1024 * 1024), "50.0 MB")
        self.assertEqual(human_size(None), "?")

    def test_fmt_duration(self):
        self.assertEqual(fmt_duration(65), "01:05")
        self.assertEqual(fmt_duration(3725), "1:02:05")
        self.assertEqual(fmt_duration(None), "--:--")

    def test_progress_bar(self):
        self.assertEqual(progress_bar(0), "░" * 10)
        self.assertEqual(progress_bar(100), "█" * 10)
        self.assertEqual(len(progress_bar(55)), 10)
        self.assertEqual(progress_bar(500), "█" * 10)

    def test_truncate(self):
        self.assertEqual(truncate("abcdef", 4), "abc…")
        self.assertEqual(truncate("abc", 4), "abc")

    def test_safe_filename(self):
        self.assertEqual(safe_filename('a/b:c*"d?', ".mp4"), "abcd.mp4")
        self.assertEqual(safe_filename("", "mp3"), "media.mp3")
        self.assertTrue(safe_filename("x" * 300, "mp4").endswith(".mp4"))


if __name__ == "__main__":
    unittest.main()
