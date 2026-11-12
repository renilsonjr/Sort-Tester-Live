"""Rank caps and the promotion gate's pure rules (issue #8, slice 6)."""
import unittest

from backend.ranked import ranks


class BadgeTests(unittest.TestCase):
    def test_badge_brackets(self):
        cases = [
            (-250, "Iron"), (0, "Iron"), (999, "Iron"), (1000, "Iron"),
            (1001, "Bronze"), (2000, "Bronze"),
            (2001, "Silver"), (3000, "Silver"),
            (3001, "Gold"), (4000, "Gold"),
            (4001, "Challenger"), (9000, "Challenger"),
        ]
        for points, badge in cases:
            with self.subTest(points=points):
                self.assertEqual(ranks.badge_for(points), badge)


class EntryModeTests(unittest.TestCase):
    def test_exactly_at_a_cap_is_promotion(self):
        for cap in (1000, 2000, 3000, 4000):
            with self.subTest(cap=cap):
                self.assertEqual(ranks.entry_mode(cap), "promotion")

    def test_everywhere_else_is_normal(self):
        for points in (-250, 0, 999, 1001, 1999, 2001, 2999, 3001, 3999,
                       4001, 5000, 8000):
            with self.subTest(points=points):
                self.assertEqual(ranks.entry_mode(points), "normal")


if __name__ == "__main__":
    unittest.main()
