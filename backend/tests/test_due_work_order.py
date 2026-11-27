"""The game's clock work runs in one fixed order.

A round cannot close for a season that has not finished, and prizes
cannot be final while a round is still open, so the order is the rule.
"""
import unittest
from types import SimpleNamespace
from unittest import mock

from backend.ranked import due_work


class DueWorkOrderTests(unittest.TestCase):
    def _run(self, launch):
        calls = []
        with mock.patch.object(
            due_work.season_close, "finish_due_seasons",
            side_effect=lambda *a, **k: calls.append("season"),
        ), mock.patch.object(
            due_work.tiebreaks, "close_due_rounds",
            side_effect=lambda *a, **k: calls.append("rounds"),
        ), mock.patch.object(
            due_work.tiebreaks, "finalize_prizes",
            side_effect=lambda *a, **k: calls.append("prizes"),
        ), mock.patch.object(due_work.seasons, "official_launch", return_value=launch):
            due_work.run(object(), clock=object(), bank=object())
        return calls

    def test_season_then_rounds_then_prizes(self):
        launch = SimpleNamespace(season_id=7)
        self.assertEqual(self._run(launch), ["season", "rounds", "prizes"])

    def test_no_prizes_are_settled_before_there_is_an_official_season(self):
        self.assertEqual(self._run(None), ["season", "rounds"])


if __name__ == "__main__":
    unittest.main()
