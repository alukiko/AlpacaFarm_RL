"""Run the K06 AlpacaFarm audit from a fresh checkout with Python 3.10+."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from alpacafarm_rl.analysis import evaluate_pairs, padding_probe, summarize  # noqa: E402
from alpacafarm_rl.data import (  # noqa: E402
    audit_judge_overlap,
    group_human_annotations,
    load_json_rows,
    sha256_file,
)
from alpacafarm_rl.judge import analyze_local_judge, load_jsonl  # noqa: E402

HUMAN_PATH = ROOT / "data/raw/alpaca_farm_human_crossannotations.json"
JUDGE_PATH = ROOT / "data/raw/alpaca_eval_annotations_alpaca_eval_gpt4.json"
OUTPUT_DIR = ROOT / "results"


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    human_rows = load_json_rows(HUMAN_PATH)
    judge_rows = load_json_rows(JUDGE_PATH)
    pairs, human_counts = group_human_annotations(human_rows)
    overlap_rows, overlap_counts = audit_judge_overlap(pairs, judge_rows)
    evaluated = evaluate_pairs(pairs)
    padding_rows, padding_summary = padding_probe(pairs, evaluated)
    summary = summarize(evaluated, overlap_counts, padding_summary)
    summary["source_data"] = {
        "human": {"path": HUMAN_PATH.relative_to(ROOT).as_posix(), "sha256": sha256_file(HUMAN_PATH)},
        "judge": {"path": JUDGE_PATH.relative_to(ROOT).as_posix(), "sha256": sha256_file(JUDGE_PATH)},
    }
    summary["human_data_quality"] = human_counts

    OUTPUT_DIR.mkdir(exist_ok=True)
    write_csv(OUTPUT_DIR / "pair_metrics.csv", evaluated)
    write_csv(OUTPUT_DIR / "judge_overlap_audit.csv", overlap_rows)
    write_csv(OUTPUT_DIR / "padding_probe.csv", padding_rows)

    local_base = ROOT / "data/generated/local_judge_cpu_base.jsonl"
    local_swap = ROOT / "data/generated/local_judge_cpu_swap.jsonl"
    local_repeat = ROOT / "data/generated/local_judge_cpu_repeat.jsonl"
    if all(path.is_file() for path in (local_base, local_swap, local_repeat)):
        judge_pairs, swap_pairs, repeat_pairs, judge_summary = analyze_local_judge(
            evaluated, load_jsonl(local_base), load_jsonl(local_swap), load_jsonl(local_repeat)
        )
        write_csv(OUTPUT_DIR / "local_judge_pair_metrics.csv", judge_pairs)
        write_csv(OUTPUT_DIR / "order_swap_probe.csv", swap_pairs)
        write_csv(OUTPUT_DIR / "same_order_repeat_probe.csv", repeat_pairs)
        summary["method"] = (
            "Local CPU-only Qwen3 judge on 200 human-majority pairs; "
            "word length, character length, and first position as matched baselines"
        )
        summary["study_primary_evaluator"] = "local_judge.judge"
        summary["local_judge"] = judge_summary
        summary["source_data"]["local_judge_base"] = {
            "path": local_base.relative_to(ROOT).as_posix(), "sha256": sha256_file(local_base)
        }
        summary["source_data"]["local_judge_swap"] = {
            "path": local_swap.relative_to(ROOT).as_posix(), "sha256": sha256_file(local_swap)
        }
        summary["source_data"]["local_judge_repeat"] = {
            "path": local_repeat.relative_to(ROOT).as_posix(), "sha256": sha256_file(local_repeat)
        }
    with (OUTPUT_DIR / "summary.json").open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, indent=2, ensure_ascii=False)
        stream.write("\n")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
