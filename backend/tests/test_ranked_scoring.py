"""Ranked points maths (issue #9, slice 1).

The numbered examples are the owner-confirmed worked examples in
docs/superpowers/specs/2026-11-07-ranked-worked-examples.md.
"""
import unittest

from backend.ranked import ranks, scoring


def answers(**counts):
    """Build an answer list, e.g. answers(easy_correct=5, hard_wrong=1)."""
    result = []
    for key, count in counts.items():
        difficulty, outcome = key.split("_")
        result.extend([(difficulty, outcome)] * count)
    return result


PERFECT = answers(easy_correct=5, medium_correct=5, hard_correct=5)      # +300
ALL_WRONG = answers(easy_wrong=5, medium_wrong=5, hard_wrong=5)          # -150
ONE_EASY_MISTAKE = answers(                                              # +275
    easy_correct=4, easy_wrong=1, medium_correct=5, hard_correct=5
)
PARTIAL_PLUS_100 = answers(hard_correct=3, easy_correct=1)
PARTIAL_PLUS_80 = answers(hard_correct=2, medium_correct=1)
PARTIAL_MINUS_40 = answers(easy_wrong=2, medium_wrong=1)


class AnswerPointsTests(unittest.TestCase):
    def test_values_for_every_difficulty_and_result(self):
        cases = {
            ("easy", "correct"): 10, ("easy", "wrong"): -15, ("easy", "timeout"): -15,
            ("medium", "correct"): 20, ("medium", "wrong"): -10, ("medium", "timeout"): -10,
            ("hard", "correct"): 30, ("hard", "wrong"): -5, ("hard", "timeout"): -5,
        }
        for (difficulty, result), points in cases.items():
            with self.subTest(difficulty=difficulty, result=result):
                self.assertEqual(scoring.answer_points(difficulty, result), points)

    def test_an_unanswered_question_scores_nothing(self):
        for difficulty in ("easy", "medium", "hard"):
            self.assertEqual(scoring.answer_points(difficulty, None), 0)

    def test_unknown_difficulty_or_result_is_refused(self):
        with self.assertRaises(ValueError):
            scoring.answer_points("extreme", "correct")
        with self.assertRaises(ValueError):
            scoring.answer_points("easy", "skipped")


class RawScoreTests(unittest.TestCase):
    def test_complete_attempt_range(self):
        self.assertEqual(scoring.raw_score(PERFECT), 300)
        self.assertEqual(scoring.raw_score(ALL_WRONG), -150)

    def test_no_answers_is_zero(self):
        self.assertEqual(scoring.raw_score([]), 0)

    def test_unanswered_questions_do_not_count(self):
        self.assertEqual(
            scoring.raw_score(PARTIAL_PLUS_80 + [("hard", None)]), 80
        )


class CapForTests(unittest.TestCase):
    def test_caps(self):
        self.assertEqual(ranks.cap_for("Iron"), 1000)
        self.assertEqual(ranks.cap_for("Bronze"), 2000)
        self.assertEqual(ranks.cap_for("Silver"), 3000)
        self.assertEqual(ranks.cap_for("Gold"), 4000)
        self.assertIsNone(ranks.cap_for("Challenger"))


class WorkedExampleTests(unittest.TestCase):
    def check(self, result, *, raw, adjustment, after, badge):
        self.assertEqual(result.raw_score, raw)
        self.assertEqual(result.adjustment, adjustment)
        self.assertEqual(result.points_after, after)
        self.assertEqual(result.badge_after, badge)

    def test_example_1_overflow_is_discarded_at_the_cap(self):
        result = scoring.settle(950, "normal", "completed", PERFECT)
        self.check(result, raw=300, adjustment=50, after=1000, badge="Iron")

    def test_example_2_quit_penalty_applies_before_the_cap(self):
        result = scoring.settle(990, "normal", "quit", PARTIAL_PLUS_100)
        self.check(result, raw=100, adjustment=10, after=1000, badge="Iron")

    def test_example_3_promotion_mistake_only_deducts(self):
        result = scoring.settle(1000, "promotion", "completed", ONE_EASY_MISTAKE)
        self.check(result, raw=275, adjustment=-15, after=985, badge="Iron")

    def test_example_4_perfect_promotion_sets_cap_plus_one(self):
        result = scoring.settle(1000, "promotion", "completed", PERFECT)
        self.check(result, raw=300, adjustment=1, after=1001, badge="Bronze")
        self.assertEqual(result.badge_before, "Iron")

    def test_example_5_losses_demote(self):
        result = scoring.settle(1010, "normal", "completed", ALL_WRONG)
        self.check(result, raw=-150, adjustment=-150, after=860, badge="Iron")
        self.assertEqual(result.badge_before, "Bronze")

    def test_example_6_disconnect_is_partial_without_penalty(self):
        result = scoring.settle(500, "normal", "disconnect", PARTIAL_MINUS_40)
        self.check(result, raw=-40, adjustment=-40, after=460, badge="Iron")

    def test_example_8_outage_void_changes_nothing(self):
        result = scoring.settle(500, "normal", "outage_void", PARTIAL_PLUS_80)
        self.check(result, raw=80, adjustment=0, after=500, badge="Iron")

    def test_example_9_season_close_is_partial_without_penalty(self):
        result = scoring.settle(500, "normal", "season_close", PARTIAL_PLUS_80)
        self.check(result, raw=80, adjustment=80, after=580, badge="Iron")

    def test_example_10_launch_reset_changes_nothing(self):
        result = scoring.settle(850, "normal", "launch_reset", PARTIAL_PLUS_80)
        self.check(result, raw=80, adjustment=0, after=850, badge="Iron")

    def test_example_11_challenger_is_uncapped(self):
        promoted = scoring.settle(4000, "promotion", "completed", PERFECT)
        self.check(promoted, raw=300, adjustment=1, after=4001, badge="Challenger")
        nxt = scoring.settle(4001, "normal", "completed", PERFECT)
        self.check(nxt, raw=300, adjustment=300, after=4301, badge="Challenger")

    def test_example_13_promotion_mistake_then_quit(self):
        one_mistake = answers(easy_wrong=1)
        quit_result = scoring.settle(1000, "promotion", "quit", one_mistake)
        self.check(quit_result, raw=-15, adjustment=-25, after=975, badge="Iron")
        lost = scoring.settle(1000, "promotion", "disconnect", one_mistake)
        self.check(lost, raw=-15, adjustment=-15, after=985, badge="Iron")


class NormalEdgeTests(unittest.TestCase):
    def test_quit_away_from_a_cap(self):
        self.assertEqual(
            scoring.settle(500, "normal", "quit", PARTIAL_PLUS_80).adjustment, 70
        )
        self.assertEqual(
            scoring.settle(500, "normal", "quit", PARTIAL_MINUS_40).adjustment, -50
        )

    def test_quit_with_no_answers_costs_ten(self):
        result = scoring.settle(500, "normal", "quit", [("easy", None)])
        self.assertEqual((result.raw_score, result.points_after), (0, 490))

    def test_landing_exactly_on_and_just_under_a_cap(self):
        on = scoring.settle(920, "normal", "completed", PARTIAL_PLUS_80)
        self.assertEqual((on.points_after, on.adjustment), (1000, 80))
        under = scoring.settle(919, "normal", "completed", PARTIAL_PLUS_80)
        self.assertEqual((under.points_after, under.badge_after), (999, "Iron"))

    def test_each_capped_badge_stops_at_its_own_cap(self):
        for before, cap in ((1900, 2000), (2900, 3000), (3900, 4000)):
            with self.subTest(before=before):
                result = scoring.settle(before, "normal", "completed", PERFECT)
                self.assertEqual(result.points_after, cap)
                self.assertEqual(result.badge_after, result.badge_before)

    def test_totals_can_go_negative_and_stay_iron(self):
        result = scoring.settle(-100, "normal", "completed", ALL_WRONG)
        self.assertEqual((result.points_after, result.badge_after), (-250, "Iron"))

    def test_demotion_across_each_bracket(self):
        for before, badge_before, badge_after in (
            (1010, "Bronze", "Iron"), (2010, "Silver", "Bronze"),
            (3010, "Gold", "Silver"), (4010, "Challenger", "Gold"),
        ):
            with self.subTest(before=before):
                result = scoring.settle(before, "normal", "completed", ALL_WRONG)
                self.assertEqual(result.badge_before, badge_before)
                self.assertEqual(result.badge_after, badge_after)


class PromotionEdgeTests(unittest.TestCase):
    def test_early_ending_with_no_mistake_changes_nothing(self):
        result = scoring.settle(1000, "promotion", "disconnect", PARTIAL_PLUS_80)
        self.assertEqual((result.points_after, result.adjustment), (1000, 0))

    def test_quit_with_no_mistake_costs_ten(self):
        result = scoring.settle(1000, "promotion", "quit", PARTIAL_PLUS_80)
        self.assertEqual(result.points_after, 990)

    def test_all_correct_but_not_completed_is_not_a_promotion(self):
        result = scoring.settle(1000, "promotion", "season_close", PERFECT)
        self.assertEqual((result.points_after, result.badge_after), (1000, "Iron"))

    def test_timeouts_deduct_like_wrong_answers(self):
        result = scoring.settle(
            2000, "promotion", "completed",
            answers(easy_correct=5, medium_correct=5, hard_correct=4, hard_timeout=1),
        )
        self.assertEqual((result.points_after, result.badge_after), (1995, "Bronze"))

    def test_perfect_promotion_from_every_cap(self):
        for cap, badge in ((1000, "Bronze"), (2000, "Silver"),
                           (3000, "Gold"), (4000, "Challenger")):
            with self.subTest(cap=cap):
                result = scoring.settle(cap, "promotion", "completed", PERFECT)
                self.assertEqual((result.points_after, result.badge_after),
                                 (cap + 1, badge))

    def test_void_outcomes_ignore_promotion_mistakes(self):
        for outcome in ("outage_void", "launch_reset"):
            with self.subTest(outcome=outcome):
                result = scoring.settle(1000, "promotion", outcome, ALL_WRONG)
                self.assertEqual(result.adjustment, 0)


class InvalidInputTests(unittest.TestCase):
    def test_unknown_mode_or_outcome_is_refused(self):
        with self.assertRaises(ValueError):
            scoring.settle(0, "tiebreak", "completed", PERFECT)
        with self.assertRaises(ValueError):
            scoring.settle(0, "normal", "abandoned", PERFECT)


if __name__ == "__main__":
    unittest.main()
