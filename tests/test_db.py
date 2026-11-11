import asyncio
import unittest

from bot.db import Database


def run(coro):
    return asyncio.run(coro)


class DbTest(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_users(self):
        u = run(self.db.upsert_user(1, "ali", "Ali", "ar"))
        self.assertEqual((u["id"], u["lang"], u["default_quality"], u["banned"]), (1, "ar", "ask", 0))
        # second upsert must not overwrite lang chosen at creation
        run(self.db.set_lang(1, "en"))
        u = run(self.db.upsert_user(1, "ali2", "Ali", "ar"))
        self.assertEqual((u["lang"], u["username"]), ("en", "ali2"))
        run(self.db.set_quality(1, "720"))
        self.assertEqual(run(self.db.get_user(1))["default_quality"], "720")

    def test_ban_and_broadcast_ids(self):
        run(self.db.upsert_user(1, None, "A", "en"))
        run(self.db.upsert_user(2, None, "B", "en"))
        self.assertTrue(run(self.db.set_banned(2, True)))
        self.assertEqual(run(self.db.all_user_ids()), [1])
        self.assertFalse(run(self.db.set_banned(999, True)))

    def test_downloads_and_limits(self):
        run(self.db.upsert_user(1, None, "A", "en"))
        run(self.db.log_download(1, "u", "t", "video", "720", 10))
        run(self.db.log_download(1, "u2", "t2", "audio", "audio", 5))
        self.assertEqual(run(self.db.count_downloads_today(1)), 2)
        self.assertEqual(run(self.db.get_user(1))["downloads"], 2)

    def test_cache(self):
        self.assertIsNone(run(self.db.cache_get("k")))
        run(self.db.cache_put("k", "FILEID", "video"))
        run(self.db.cache_put("k", "FILEID2", "video"))  # upsert
        self.assertEqual(run(self.db.cache_get("k")), {"file_id": "FILEID2", "kind": "video"})
        run(self.db.cache_delete("k"))
        self.assertIsNone(run(self.db.cache_get("k")))
        run(self.db.cache_put("a", "x", "audio"))
        self.assertEqual(run(self.db.cache_clear()), 1)

    def test_stats(self):
        run(self.db.upsert_user(1, None, "A", "en"))
        run(self.db.log_download(1, "u", "t", "video", "720", 10))
        s = run(self.db.stats())
        self.assertEqual((s["users"], s["downloads"], s["downloads_today"], s["new_today"]), (1, 1, 1, 1))


if __name__ == "__main__":
    unittest.main()
