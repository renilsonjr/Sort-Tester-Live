"""The load simulator's own rules (issue #13, load item).

The tool plays real attempts, so the parts that decide when it stops,
which accounts it may touch and whether a balance reconciles are checked
here without any network.
"""
import contextlib
import importlib.util
import io
import os
import stat
import tempfile
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "infra/azure/diagnostics/ranked-load-sim.py"
_spec = importlib.util.spec_from_file_location("ranked_load_sim", _PATH)
sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sim)


def _entry(attempt_id, before, adjustment):
    return {"attempt_id": attempt_id, "points_before": before,
            "points_after": before + adjustment, "adjustment": adjustment}


class StopRuleTests(unittest.TestCase):
    def test_a_quiet_run_goes_on(self):
        events = [(100.0 + i, 0.05, False) for i in range(100)]
        self.assertIsNone(sim.stop_reason(200.0, 0.0, events))

    def test_a_burst_of_failures_stops_it(self):
        events = [(190.0 + i, 0.05, True) for i in range(10)]
        self.assertIn("failed requests", sim.stop_reason(200.0, 0.0, events))

    def test_old_failures_do_not_count(self):
        events = [(100.0 + i, 0.05, True) for i in range(10)]
        self.assertIsNone(sim.stop_reason(200.0, 0.0, events))

    def test_nine_failures_are_not_a_burst(self):
        events = [(190.0 + i, 0.05, True) for i in range(9)]
        self.assertIsNone(sim.stop_reason(200.0, 0.0, events))

    def test_a_slow_minute_stops_it(self):
        events = [(150.0 + i, 0.05, False) for i in range(40)]
        events += [(195.0, 4.0, False)] * 5
        self.assertIn("slowest 5%", sim.stop_reason(200.0, 0.0, events))

    def test_a_few_slow_requests_do_not(self):
        events = [(150.0 + i * 0.4, 0.05, False) for i in range(120)] + [(195.0, 4.0, False)]
        self.assertIsNone(sim.stop_reason(200.0, 0.0, events))

    def test_slowness_is_not_judged_in_the_first_minute(self):
        events = [(30.0, 4.0, False)] * 40
        self.assertIsNone(sim.stop_reason(40.0, 0.0, events))


class ReconcileTests(unittest.TestCase):
    def test_a_clean_history_reconciles(self):
        history = [_entry("c", 30, -10), _entry("b", 10, 20), _entry("a", 0, 10)]
        self.assertEqual(sim.history_problems(history, 20, ["a", "c"]), [])

    def test_an_account_that_never_played_reconciles_at_zero(self):
        self.assertEqual(sim.history_problems([], 0), [])

    def test_a_balance_that_differs_from_the_history_is_reported(self):
        history = [_entry("a", 0, 10)]
        self.assertIn("balance is 20", " ".join(sim.history_problems(history, 20)))

    def test_an_attempt_counted_twice_is_reported(self):
        history = [_entry("a", 10, 10), _entry("a", 0, 10)]
        found = " ".join(sim.history_problems(history, 20, ["a"]))
        self.assertIn("twice", found)
        self.assertIn("2 times", found)

    def test_a_gap_in_the_chain_is_reported(self):
        history = [_entry("b", 50, 10), _entry("a", 0, 10)]
        self.assertIn("jumps", " ".join(sim.history_problems(history, 60)))

    def test_a_finished_attempt_missing_from_the_history_is_reported(self):
        history = [_entry("a", 0, 10)]
        self.assertIn("0 times", " ".join(sim.history_problems(history, 10, ["a", "zz"])))

    def test_a_move_that_is_not_the_adjustment_is_reported(self):
        history = [{"attempt_id": "a", "points_before": 0, "points_after": 15, "adjustment": 10}]
        self.assertIn("other than its adjustment", " ".join(sim.history_problems(history, 15)))


class GuardTests(unittest.TestCase):
    def _refused(self, argv):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            sim._arguments(argv)

    def test_every_step_refuses_another_machine(self):
        for step in ("create", "run", "reconcile", "cleanup"):
            argv = [step, "--base", "https://example.org", "--accounts", "x.json"]
            if step == "run":
                argv += ["--out", "r.json"]
            with self.subTest(step=step):
                self._refused(argv)

    def test_this_machine_is_accepted(self):
        args = sim._arguments(["cleanup", "--base", "http://127.0.0.1:8094", "--accounts", "x.json"])
        self.assertEqual(args.prefix, "loadtest_")

    def test_an_empty_prefix_is_refused(self):
        # an empty prefix would match every username, real players included
        self._refused(["cleanup", "--base", "http://127.0.0.1:8094", "--accounts", "x.json", "--prefix", ""])

    def test_the_accounts_file_is_readable_by_its_owner_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "accounts.json")
            sim.write_accounts(path, [{"username": "loadtest_01", "login_id": "x"}])
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            self.assertEqual(sim.read_accounts(path)[0]["username"], "loadtest_01")


if __name__ == "__main__":
    unittest.main()
