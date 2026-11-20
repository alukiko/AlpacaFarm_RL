"""Analyze frozen CPU-only local judge decisions on the same human pairs."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .analysis import error_summary, wilson_interval


def paired_error_difference(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Judge minus length-rule error, with a pair bootstrap 95% interval."""
    differences = [int(row["judge_error"]) - int(row["length_error"]) for row in rows]
    randomizer = random.Random(20261120)
    estimates = sorted(
        sum(randomizer.choices(differences, k=len(differences))) / len(differences)
        for _ in range(5000)
    )
    return {
        "judge_minus_length_error_rate": sum(differences) / len(differences),
        "bootstrap_95": [estimates[124], estimates[4874]],
        "resamples": 5000,
        "seed": 20261120,
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, start=1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{number}") from exc
    return rows


def analyze_local_judge(
    evaluated: list[dict[str, Any]],
    base_records: list[dict[str, Any]],
    swap_records: list[dict[str, Any]],
    repeat_records: list[dict[str, Any]],
    *, sample_size: int = 200, swap_size: int = 50,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    primary = sorted(
        (row for row in evaluated if row["eligible"]),
        key=lambda row: row["pair_id"],
    )[:sample_size]
    if len(primary) != sample_size:
        raise ValueError(f"Only {len(primary)} primary human pairs")
    by_id = {row["pair_id"]: row for row in primary}
    base_by_id = {row["pair_id"]: row for row in base_records}
    if len(base_by_id) != len(base_records) or set(base_by_id) != set(by_id):
        raise ValueError("Base judge JSONL must contain exactly the selected 200 pair IDs")
    swap_by_id = {row["pair_id"]: row for row in swap_records}
    expected_swap_ids = {row["pair_id"] for row in primary[:swap_size]}
    if len(swap_by_id) != len(swap_records) or set(swap_by_id) != expected_swap_ids:
        raise ValueError("Swap JSONL must contain the first 50 selected pair IDs")
    repeat_by_id = {row["pair_id"]: row for row in repeat_records}
    if len(repeat_by_id) != len(repeat_records) or set(repeat_by_id) != expected_swap_ids:
        raise ValueError("Repeat JSONL must contain the first 50 selected pair IDs")

    all_records = base_records + swap_records + repeat_records
    model_ids = {row.get("model_id") for row in all_records}
    if len(model_ids) != 1 or any(row.get("model") != base_records[0].get("model") for row in all_records):
        raise ValueError("Model identity is inconsistent")
    if {row.get("mode") for row in base_records} != {"base"}:
        raise ValueError("Unexpected mode in base JSONL")
    if any(row.get("options") != base_records[0].get("options") for row in all_records):
        raise ValueError("Inference settings are inconsistent")
    if any(row.get("options", {}).get("num_gpu") != 0 for row in all_records):
        raise ValueError("The local judge was not configured for CPU-only inference")

    pair_rows = []
    for human in primary:
        record = base_by_id[human["pair_id"]]
        choice = record.get("choice_aligned")
        pair_rows.append({
            "pair_id": human["pair_id"],
            "agreement": human["agreement"],
            "human_majority": human["human_majority"],
            "word_gap": human["absolute_word_gap"],
            "judge_choice": choice if choice in (1, 2) else "",
            "judge_error": int(choice != human["human_majority"]) if choice in (1, 2) else "",
            "length_error": human["length_error"],
            "character_error": human["character_error"],
            "position_1_error": human["position_1_error"],
            "judge_presented_swapped": record["presented_swapped"],
            "prompt_eval_count": record.get("prompt_eval_count"),
            "eval_count": record.get("eval_count"),
        })

    valid = [row for row in pair_rows if row["judge_choice"] != ""]
    if not valid:
        raise ValueError("No parseable local judge decisions")
    swapped_rows = []
    for human in primary[:swap_size]:
        base = base_by_id[human["pair_id"]]
        swapped = swap_by_id[human["pair_id"]]
        if swapped.get("mode") != "swap":
            raise ValueError("Unexpected mode in swap JSONL")
        if swapped.get("presented_swapped") == base.get("presented_swapped"):
            raise ValueError("Answer order did not reverse")
        first, second = base.get("choice_aligned"), swapped.get("choice_aligned")
        swapped_rows.append({
            "pair_id": human["pair_id"],
            "human_majority": human["human_majority"],
            "base_choice": first if first in (1, 2) else "",
            "swap_choice": second if second in (1, 2) else "",
            "choice_changed_after_order_swap": int(first != second) if first in (1, 2) and second in (1, 2) else "",
            "base_error": int(first != human["human_majority"]) if first in (1, 2) else "",
            "swap_error": int(second != human["human_majority"]) if second in (1, 2) else "",
        })
    valid_swap = [row for row in swapped_rows if row["choice_changed_after_order_swap"] != ""]
    changed = sum(row["choice_changed_after_order_swap"] for row in valid_swap)
    repeat_rows = []
    for human in primary[:swap_size]:
        base = base_by_id[human["pair_id"]]
        repeated = repeat_by_id[human["pair_id"]]
        if repeated.get("mode") != "repeat":
            raise ValueError("Unexpected mode in repeat JSONL")
        if repeated.get("presented_swapped") != base.get("presented_swapped"):
            raise ValueError("Answer order changed in same-order repeat")
        first, second = base.get("choice_aligned"), repeated.get("choice_aligned")
        repeat_rows.append({
            "pair_id": human["pair_id"],
            "human_majority": human["human_majority"],
            "base_choice": first if first in (1, 2) else "",
            "repeat_choice": second if second in (1, 2) else "",
            "choice_changed_on_repeat": int(first != second) if first in (1, 2) and second in (1, 2) else "",
            "base_error": int(first != human["human_majority"]) if first in (1, 2) else "",
            "repeat_error": int(second != human["human_majority"]) if second in (1, 2) else "",
        })
    valid_repeat = [row for row in repeat_rows if row["choice_changed_on_repeat"] != ""]
    repeat_changed = sum(row["choice_changed_on_repeat"] for row in valid_repeat)
    summary = {
        "model": base_records[0]["model"],
        "model_id": next(iter(model_ids)),
        "options": base_records[0]["options"],
        "sample_selection": "first 200 standard majority pairs sorted by SHA-256 pair_id",
        "sample_size": sample_size,
        "valid_decisions": len(valid),
        "coverage": len(valid) / sample_size,
        "judge": error_summary(valid, "judge_error"),
        "word_length_on_same_pairs": error_summary(valid, "length_error"),
        "character_length_on_same_pairs": error_summary(valid, "character_error"),
        "position_1_on_same_pairs": error_summary(valid, "position_1_error"),
        "paired_judge_minus_length": paired_error_difference(valid),
        "human_agreement_subgroups": {
            label: error_summary(
                [row for row in valid if row["agreement"] == label], "judge_error"
            ) for label in ("4:0", "3:1")
        },
        "word_gap_at_most_30": error_summary(
            [row for row in valid if row["word_gap"] <= 30], "judge_error"
        ),
        "word_gap_over_30": error_summary(
            [row for row in valid if row["word_gap"] > 30], "judge_error"
        ),
        "order_swap": {
            "n": len(valid_swap),
            "changed_choices": changed,
            "change_rate": changed / len(valid_swap) if valid_swap else None,
            "change_wilson_95": wilson_interval(changed, len(valid_swap)),
            "original_order_error": error_summary(
                valid_swap, "base_error"
            ) if valid_swap else None,
            "reversed_order_error": error_summary(
                valid_swap, "swap_error"
            ) if valid_swap else None,
        },
        "same_order_repeat": {
            "n": len(valid_repeat),
            "changed_choices": repeat_changed,
            "change_rate": repeat_changed / len(valid_repeat) if valid_repeat else None,
            "change_wilson_95": wilson_interval(repeat_changed, len(valid_repeat)),
            "repeated_order_error": error_summary(valid_repeat, "repeat_error") if valid_repeat else None,
        },
    }
    return pair_rows, swapped_rows, repeat_rows, summary
