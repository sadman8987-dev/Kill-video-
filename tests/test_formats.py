import unittest

from bot.formats import (cache_key, classify_error, estimate_mp3_size, estimate_sizes, ladder_from_formats,
                         pick_height, video_selector)

FORMATS = [
    {"height": 360, "vcodec": "avc1", "acodec": "none", "filesize": 10_000_000},
    {"height": 720, "vcodec": "avc1", "acodec": "none", "filesize": 40_000_000},
    {"height": 1080, "vcodec": "avc1", "acodec": "none", "filesize_approx": 90_000_000},
    {"height": None, "vcodec": "none", "acodec": "mp4a", "abr": 128, "filesize": 3_000_000},
    {"height": None, "vcodec": "none", "acodec": "opus", "abr": 64, "filesize": 1_000_000},
]


class FormatsTest(unittest.TestCase):
    def test_ladder(self):
        self.assertEqual(ladder_from_formats(FORMATS), [360, 480, 720, 1080])
        self.assertEqual(ladder_from_formats([]), [])
        self.assertEqual(ladder_from_formats([{"height": 240, "vcodec": "avc1"}]), [240])
        many = [{"height": h, "vcodec": "avc1"} for h in (144, 360, 480, 720, 1080, 1440, 2160)]
        self.assertEqual(ladder_from_formats(many), [720, 1080, 1440, 2160])

    def test_sizes(self):
        sizes = estimate_sizes(FORMATS, [360, 480, 720, 1080])
        self.assertEqual(sizes[360], 13_000_000)
        self.assertEqual(sizes[480], 13_000_000)  # nearest lower format
        self.assertEqual(sizes[720], 43_000_000)
        self.assertEqual(sizes[1080], 93_000_000)

    def test_sizes_muxed_not_double_counted(self):
        muxed = [{"height": 480, "vcodec": "avc1", "acodec": "mp4a", "filesize": 5_000_000},
                 {"height": None, "vcodec": "none", "acodec": "mp4a", "abr": 128, "filesize": 3_000_000}]
        self.assertEqual(estimate_sizes(muxed, [480])[480], 5_000_000)

    def test_unknown_size(self):
        self.assertIsNone(estimate_sizes([{"height": 360, "vcodec": "avc1"}], [360])[360])

    def test_pick_height(self):
        self.assertEqual(pick_height([360, 720, 1080], 720), 720)
        self.assertEqual(pick_height([360, 720], 1080), 720)
        self.assertEqual(pick_height([720, 1080], 360), 720)
        self.assertEqual(pick_height([], 720), 0)

    def test_selector(self):
        self.assertIn("height<=720", video_selector(720))
        self.assertNotIn("height<=", video_selector(0))
        self.assertTrue(video_selector(0).endswith("/b"))

    def test_cache_key(self):
        self.assertEqual(cache_key("youtube:abc", "audio", 0), "youtube:abc:a")
        self.assertEqual(cache_key("youtube:abc", "video", 720), "youtube:abc:v720")

    def test_mp3_estimate(self):
        self.assertEqual(estimate_mp3_size(100), 2_400_000)
        self.assertIsNone(estimate_mp3_size(None))

    def test_classify_error(self):
        self.assertEqual(classify_error("ERROR: Sign in to confirm your age"), "err_login")
        self.assertEqual(classify_error("Video unavailable"), "err_unavailable")
        self.assertEqual(classify_error("Unsupported URL: http://x"), "err_unsupported")
        self.assertEqual(classify_error("HTTP Error 429: Too Many Requests"), "err_rate")
        self.assertEqual(classify_error("not available in your country"), "err_geo")
        self.assertEqual(classify_error("boom"), "failed")


if __name__ == "__main__":
    unittest.main()