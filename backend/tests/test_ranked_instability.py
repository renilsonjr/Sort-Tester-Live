"""The connection instability counting rule (issue #25, slice 1).

Decision 7: four distinct losses qualify when each consecutive gap is under
five seconds; a gap of exactly five seconds or more starts a new sequence.
"""
from datetime import datetime, timedelta, timezone
import unittest

from backend.ranked import instability

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def at(seconds):
    return T0 + timedelta(seconds=seconds)


def flapping(*loss_seconds):
    """Losses at the given seconds, each followed by a recovery one second later."""
    events = []
    for seconds in loss_seconds:
        events.append(("loss", at(seconds)))
        events.append(("recovery", at(seconds + 1)))
    return events


class DistinctLossTests(unittest.TestCase):
    def test_each_loss_after_a_recovery_counts(self):
        self.assertEqual(
            instability.distinct_losses(flapping(0, 4, 8)), [at(0), at(4), at(8)]
        )

    def test_losses_without_a_recovery_between_them_count_once(self):
        events = [
            ("loss", at(0)), ("loss", at(1)), ("loss", at(2)),  # one interruption
            ("recovery", at(3)),
            ("loss", at(6)),
        ]
        self.assertEqual(instability.distinct_losses(events), [at(0), at(6)])

    def test_expiry_events_are_ignored(self):
        events = [("loss", at(0)), ("expiry", at(15))]
        self.assertEqual(instability.distinct_losses(events), [at(0)])

    def test_input_order_does_not_matter(self):
        events = list(reversed(flapping(0, 4, 8)))
        self.assertEqual(instability.distinct_losses(events), [at(0), at(4), at(8)])

    def test_recovery_at_the_same_instant_as_a_loss_follows_it(self):
        events = [("recovery", at(0)), ("loss", at(0)), ("loss", at(4))]
        self.assertEqual(instability.distinct_losses(events), [at(0), at(4)])

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            instability.distinct_losses([("glitch", at(0))])


class QualifyingRunTests(unittest.TestCase):
    def test_the_decision_example_qualifies(self):
        run = instability.qualifying_run(flapping(0, 4, 8, 12))
        self.assertEqual((run.first_loss_at, run.last_loss_at), (at(0), at(12)))

    def test_three_losses_do_not_qualify(self):
        self.assertIsNone(instability.qualifying_run(flapping(0, 4, 8)))

    def test_no_events_do_not_qualify(self):
        self.assertIsNone(instability.qualifying_run([]))

    def test_a_gap_of_exactly_five_seconds_resets_the_sequence(self):
        self.assertIsNone(instability.qualifying_run(flapping(0, 4, 8, 13)))

    def test_a_gap_just_under_five_seconds_qualifies(self):
        run = instability.qualifying_run(flapping(0, 4.999, 9.998, 14.997))
        self.assertIsNotNone(run)

    def test_a_longer_gap_resets_the_sequence(self):
        self.assertIsNone(instability.qualifying_run(flapping(0, 4, 8, 30)))

    def test_a_new_run_after_a_reset_can_qualify(self):
        run = instability.qualifying_run(flapping(0, 4, 8, 13, 17, 21, 25))
        self.assertEqual((run.first_loss_at, run.last_loss_at), (at(13), at(25)))

    def test_more_than_four_close_losses_report_the_first_run(self):
        run = instability.qualifying_run(flapping(0, 4, 8, 12, 16, 20))
        self.assertEqual((run.first_loss_at, run.last_loss_at), (at(0), at(12)))

    def test_repeated_notices_of_one_interruption_cannot_build_a_run(self):
        events = [("loss", at(0)), ("loss", at(1)), ("loss", at(2)), ("loss", at(3))]
        self.assertIsNone(instability.qualifying_run(events))

    def test_the_rule_constants(self):
        self.assertEqual((instability.RUN_LENGTH, instability.MAX_GAP_SECONDS), (4, 5))


if __name__ == "__main__":
    unittest.main()
