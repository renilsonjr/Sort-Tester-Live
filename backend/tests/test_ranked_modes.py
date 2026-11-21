"""Per-mode attempt settings (issue #8, slice 9)."""
import unittest

from backend.ranked import modes


class ModeSettingsTests(unittest.TestCase):
    def test_normal_and_promotion_are_fifteen_questions_of_ten_seconds(self):
        for mode in ("normal", "promotion"):
            with self.subTest(mode=mode):
                settings = modes.settings_for(mode)
                self.assertEqual(settings.question_count, 15)
                self.assertEqual(settings.question_seconds, 10)

    def test_a_mode_without_settings_is_refused(self):
        # tie-break settings arrive with #24, not here
        for mode in ("tiebreak", "practice", ""):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    modes.settings_for(mode)


if __name__ == "__main__":
    unittest.main()
