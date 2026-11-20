"""Behavioral checks for pair alignment and the evaluator's edge cases."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alpacafarm_rl.analysis import length_choice, wilson_interval
from alpacafarm_rl.data import audit_judge_overlap, group_human_annotations


class AnalysisTests(unittest.TestCase):
    def test_reversed_human_votes_and_judge_alignment(self) -> None:
        human = [
            {"instruction": "task", "output_1": "A", "output_2": "B", "preference": 1},
            {"instruction": "task", "output_1": "B", "output_2": "A", "preference": 2},
        ]
        pairs, counts = group_human_annotations(human)
        self.assertEqual(counts["unique_pairs"], 1)
        self.assertEqual((pairs[0].votes_1, pairs[0].votes_2), (2, 0))
        judge = [{"instruction": "task", "output_1": "B", "output_2": "A", "preference": 2}]
        audited, overlap = audit_judge_overlap(pairs, judge)
        self.assertEqual(overlap["swapped_unique_pairs"], 1)
        self.assertEqual(audited[0]["judge_preference_aligned"], 1)

    def test_length_rule_ties_and_order_swap(self) -> None:
        self.assertEqual(length_choice("a b", "c d"), 0)
        self.assertEqual(length_choice("a b c", "d e"), 1)
        self.assertEqual(length_choice("d e", "a b c"), 2)

    def test_wilson_boundary(self) -> None:
        self.assertIsNone(wilson_interval(0, 0))
        low, high = wilson_interval(0, 100)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.0)
        self.assertLess(high, 0.05)


if __name__ == "__main__":
    unittest.main()
