"""Evaluate the pre-registered length rule against AlpacaFarm human votes."""

from __future__ import annotations

import math
from collections import Counter
from statistics import median
from typing import Any

from .data import HumanPair


def word_count(text: str) -> int:
    """Count whitespace-delimited words, as specified in the project card."""
    return len(text.split())


def length_choice(output_1: str, output_2: str) -> int:
    first, second = word_count(output_1), word_count(output_2)
    if first == second:
        return 0
    return 1 if first > second else 2


def character_choice(output_1: str, output_2: str) -> int:
    """A nearby alternative: choose by Unicode character count."""
    first, second = len(output_1), len(output_2)
    if first == second:
        return 0
    return 1 if first > second else 2


def wilson_interval(successes: int, total: int) -> list[float] | None:
    """Two-sided 95% Wilson score interval for a Bernoulli proportion."""
    if total == 0:
        return None
    z = 1.959963984540054
    fraction = successes / total
    denominator = 1 + z * z / total
    centre = (fraction + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(
        fraction * (1 - fraction) / total + z * z / (4 * total * total)
    ) / denominator
    lower = 0.0 if successes == 0 else max(0.0, centre - radius)
    upper = 1.0 if successes == total else min(1.0, centre + radius)
    return [lower, upper]


def evaluate_pairs(pairs: list[HumanPair]) -> list[dict[str, Any]]:
    """Return one row per human pair; non-standard vote counts stay visible."""
    results = []
    for pair in pairs:
        first = word_count(pair.output_1)
        second = word_count(pair.output_2)
        choice = length_choice(pair.output_1, pair.output_2)
        char_choice = character_choice(pair.output_1, pair.output_2)
        eligible = pair.n_votes == 4 and pair.majority != 0
        results.append(
            {
                "pair_id": pair.pair_id,
                "votes_1": pair.votes_1,
                "votes_2": pair.votes_2,
                "agreement": pair.agreement,
                "human_majority": pair.majority,
                "words_1": first,
                "words_2": second,
                "absolute_word_gap": abs(first - second),
                "length_choice": choice,
                "length_error": int(choice != pair.majority) if eligible else "",
                "character_choice": char_choice,
                "character_error": int(char_choice != pair.majority) if eligible else "",
                "position_1_error": int(pair.majority != 1) if eligible else "",
                "eligible": eligible,
            }
        )
    return results


def error_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    total = len(rows)
    errors = sum(int(row[field]) for row in rows)
    return {
        "n": total,
        "errors": errors,
        "error_rate": errors / total if total else None,
        "error_wilson_95": wilson_interval(errors, total),
    }


def padding_probe(
    pairs: list[HumanPair], evaluated: list[dict[str, Any]],
    *, sample_size: int = 100, padding_words: int = 64,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Append irrelevant words to the originally losing response.

    Original human labels do not certify preference after the intervention. This
    is an evaluator sensitivity probe, not a measured post-intervention error.
    """
    pair_by_id = {pair.pair_id: pair for pair in pairs}
    correct = [
        row for row in evaluated
        if row["eligible"] and row["length_error"] == 0
    ]
    selected = sorted(correct, key=lambda row: row["pair_id"])[:sample_size]
    filler = "additional context " * (padding_words // 2)
    if padding_words % 2:
        filler += "additional"

    probes = []
    for row in selected:
        pair = pair_by_id[row["pair_id"]]
        losing_choice = 3 - pair.majority
        first, second = pair.output_1, pair.output_2
        if losing_choice == 1:
            first += " " + filler
        else:
            second += " " + filler
        new_choice = length_choice(first, second)
        probes.append(
            {
                "pair_id": pair.pair_id,
                "original_human_majority": pair.majority,
                "original_length_choice": row["length_choice"],
                "original_word_gap": row["absolute_word_gap"],
                "added_words": padding_words,
                "padded_response": losing_choice,
                "new_length_choice": new_choice,
                "flipped_from_original_majority": int(new_choice != pair.majority),
                "minimum_words_to_reverse": row["absolute_word_gap"] + 1,
            }
        )

    flips = sum(row["flipped_from_original_majority"] for row in probes)
    return probes, {
        "sample_selection": "first 100 initially correct standard pairs sorted by SHA-256 pair_id",
        "padding_text": filler.strip(),
        "added_words_per_pair": padding_words,
        "n": len(probes),
        "flips_relative_to_original_labels": flips,
        "flip_rate": flips / len(probes) if probes else None,
        "flip_wilson_95": wilson_interval(flips, len(probes)),
        "median_minimum_words_to_reverse": median(
            row["minimum_words_to_reverse"] for row in probes
        ) if probes else None,
        "interpretation": "Sensitivity only: changed responses have no new human labels.",
    }


def summarize(
    evaluated: list[dict[str, Any]], overlap: dict[str, int],
    padding: dict[str, Any],
) -> dict[str, Any]:
    counts = Counter(row["agreement"] for row in evaluated)
    primary = [row for row in evaluated if row["eligible"]]
    tied = [row for row in primary if row["length_choice"] == 0]
    large_gap = [row for row in primary if row["absolute_word_gap"] > 30]
    small_gap = [row for row in primary if row["absolute_word_gap"] <= 30]
    subgroup = {
        label: error_summary(
            [row for row in primary if row["agreement"] == label], "length_error"
        ) for label in ("4:0", "3:1")
    }

    return {
        "method": "Length of whitespace-delimited response; ties count as errors",
        "human_pairs": len(evaluated),
        "human_agreement_counts": dict(sorted(counts.items())),
        "primary_eligible_pairs": len(primary),
        "excluded_2_to_2_pairs": counts["2:2"],
        "excluded_nonstandard_vote_count_pairs": counts["nonstandard_vote_count"],
        "overlap_audit": overlap,
        "published_judge_usable_for_primary": overlap["reliable_unique_pairs"] >= 200,
        "main_evaluator": error_summary(primary, "length_error"),
        "character_length_comparator": error_summary(primary, "character_error"),
        "constant_position_1_baseline": error_summary(primary, "position_1_error"),
        "random_choice_expected_error_rate": 0.5,
        "length_ties_counted_as_errors": len(tied),
        "human_agreement_subgroups": subgroup,
        "word_gap_at_most_30": error_summary(small_gap, "length_error"),
        "word_gap_over_30": error_summary(large_gap, "length_error"),
        "padding_probe": padding,
        "limitations": [
            "Human majority is a preference proxy, not factual quality or safety.",
            "Padding changes the answer; no new human preferences were collected.",
            "Published GPT-4 annotations cover too few identical human pairs for comparison.",
        ],
    }
