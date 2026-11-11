import string
import unittest

from bot.i18n import TEXTS, normalize_lang, tr


def fields(text):
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


class I18nTest(unittest.TestCase):
    def test_same_keys(self):
        self.assertEqual(set(TEXTS["ar"]), set(TEXTS["en"]))

    def test_same_placeholders(self):
        for key in TEXTS["en"]:
            self.assertEqual(fields(TEXTS["ar"][key]), fields(TEXTS["en"][key]), key)

    def test_tr_and_fallback(self):
        self.assertIn("Ali", tr("en", "start", name="Ali"))
        self.assertIn("Ali", tr("xx", "start", name="Ali"))  # unknown language -> default

    def test_normalize(self):
        self.assertEqual(normalize_lang("ar-EG"), "ar")
        self.assertEqual(normalize_lang("fr"), "en")
        self.assertEqual(normalize_lang(None), "ar")


if __name__ == "__main__":
    unittest.main()
