import os
import time
import unittest

os.environ.setdefault("BOT_TOKEN", "123:test")

from bot.config import parse_ids  # noqa: E402
from bot.state import TokenStore  # noqa: E402


class StateConfigTest(unittest.TestCase):
    def test_token_store(self):
        s = TokenStore(ttl=100)
        t = s.put({"a": 1})
        self.assertEqual(s.get(t), {"a": 1})
        self.assertIsNone(s.get("nope"))

    def test_token_expiry_and_cap(self):
        s = TokenStore(ttl=0.05, max_items=2)
        t = s.put("x")
        time.sleep(0.1)
        self.assertIsNone(s.get(t))
        s = TokenStore(ttl=100, max_items=2)
        a, b, c = s.put(1), s.put(2), s.put(3)
        s.put(4)
        self.assertLessEqual(len(s._data), 3)

    def test_parse_ids(self):
        self.assertEqual(parse_ids("1, 2;3,x, -4"), frozenset({1, 2, 3, -4}))
        self.assertEqual(parse_ids(""), frozenset())


if __name__ == "__main__":
    unittest.main()
