from pathlib import Path

from django.test import TestCase, override_settings

from api.connect.profanity_filter import (
    clear_profanity_cache,
    contains_profanity,
)


class ConnectProfanityFilterTests(TestCase):
    def tearDown(self):
        clear_profanity_cache()
        super().tearDown()

    def test_clean_message_allowed(self):
        self.assertFalse(contains_profanity("Namaste, vehicle parked safely."))

    def test_classic_does_not_false_positive(self):
        self.assertFalse(contains_profanity("This is a classic example."))

    def test_blocks_en_word_from_file(self):
        self.assertTrue(contains_profanity("That is utter shit behaviour"))

    @override_settings(CONNECT_PROFANITY_EXTRA_TERMS="zzzpytestbadtoken")
    def test_extra_terms_setting(self):
        clear_profanity_cache()
        self.assertTrue(contains_profanity("hello zzzpytestbadtoken please"))

    def test_custom_english_file(self):
        path = Path(self._create_custom_en_file())
        try:
            clear_profanity_cache()
            with override_settings(CONNECT_PROFANITY_CUSTOM_FILE=str(path)):
                clear_profanity_cache()
                self.assertTrue(contains_profanity("prefix xyzcustomprofpytest suffix"))
        finally:
            clear_profanity_cache()
            path.unlink(missing_ok=True)

    def _create_custom_en_file(self) -> str:
        import tempfile

        fd, name = tempfile.mkstemp(suffix=".txt", text=True)
        import os

        with os.fdopen(fd, "w") as fh:
            fh.write("# comment\nxyzcustomprofpytest\n")
        return name
