"""Check that local judge comparisons use the same pair and aligned answers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alpacafarm_rl.judge import analyze_local_judge


class LocalJudgeTests(unittest.TestCase):
    def test_same_pair_comparison_and_order_flip(self) -> None:
        human = [
            {
                "pair_id": "a", "eligible": True, "agreement": "4:0",
                "human_majority": 1, "absolute_word_gap": 4,
                "length_error": 0, "character_error": 0, "position_1_error": 0,
            },
            {
                "pair_id": "b", "eligible": True, "agreement": "3:1",
                "human_majority": 2, "absolute_word_gap": 40,
                "length_error": 1, "character_error": 1, "position_1_error": 1,
            },
        ]
        shared = {"model": "test", "model_id": "id", "options": {"num_gpu": 0}}
        base = [
            {**shared, "pair_id": "a", "mode": "base", "choice_aligned": 1,
             "presented_swapped": False},
            {**shared, "pair_id": "b", "mode": "base", "choice_aligned": 1,
             "presented_swapped": True},
        ]
        swap = [
            {**shared, "pair_id": "a", "mode": "swap", "choice_aligned": 2,
             "presented_swapped": True},
        ]
        repeat = [
            {**shared, "pair_id": "a", "mode": "repeat", "choice_aligned": 1,
             "presented_swapped": False},
        ]
        pairs, order_rows, repeat_rows, summary = analyze_local_judge(
            human, base, swap, repeat, sample_size=2, swap_size=1
        )
        self.assertEqual(len(pairs), 2)
        self.assertEqual(summary["judge"]["errors"], 1)
        self.assertEqual(summary["paired_judge_minus_length"]["judge_minus_length_error_rate"], 0)
        self.assertEqual(summary["order_swap"]["changed_choices"], 1)
        self.assertEqual(order_rows[0]["swap_error"], 1)
        self.assertEqual(summary["same_order_repeat"]["changed_choices"], 0)
        self.assertEqual(repeat_rows[0]["repeat_error"], 0)


if __name__ == "__main__":
    unittest.main()
