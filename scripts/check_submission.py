"""Verify the reproducible code, data, results, and two PDF deliverables."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
EXPECTED_ROWS = {
    "pair_metrics.csv": 648,
    "judge_overlap_audit.csv": 648,
    "padding_probe.csv": 100,
    "local_judge_pair_metrics.csv": 200,
    "order_swap_probe.csv": 50,
    "same_order_repeat_probe.csv": 50,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def pdf_pages(path: Path) -> int:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf to check report and slide page counts") from exc
    return len(PdfReader(str(path)).pages)


def main() -> None:
    required = [
        ROOT / "README.md",
        ROOT / "data/README.md",
        ROOT / "data/raw/alpaca_farm_human_crossannotations.json",
        ROOT / "data/raw/alpaca_eval_annotations_alpaca_eval_gpt4.json",
        ROOT / "data/generated/README.md",
        ROOT / "data/generated/local_judge_cpu_base.jsonl",
        ROOT / "data/generated/local_judge_cpu_swap.jsonl",
        ROOT / "data/generated/local_judge_cpu_repeat.jsonl",
        ROOT / "docs/results_overview.md",
        RESULTS / "summary.json",
        *(RESULTS / name for name in EXPECTED_ROWS),
        ROOT / "docs/report.pdf",
        ROOT / "docs/defense.pdf",
    ]
    for path in required:
        assert path.is_file() and path.stat().st_size > 0, f"Missing or empty: {path}"

    before = {name: sha256(RESULTS / name) for name in (*EXPECTED_ROWS, "summary.json")}
    started = time.perf_counter()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_analysis.py")],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    duration = time.perf_counter() - started
    after = {name: sha256(RESULTS / name) for name in before}
    assert before == after, "Generated result files changed on a repeat run"
    assert duration < 600, "Control run exceeded ten minutes"

    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    for item in summary["source_data"].values():
        assert sha256(ROOT / item["path"]) == item["sha256"], "Raw data checksum mismatch"
    for name, expected in EXPECTED_ROWS.items():
        assert len(csv_rows(RESULTS / name)) == expected, f"Unexpected row count: {name}"

    pairs = csv_rows(RESULTS / "pair_metrics.csv")
    primary = [row for row in pairs if row["eligible"] == "True"]
    assert len(primary) == summary["primary_eligible_pairs"] == 498
    assert sum(int(row["length_error"]) for row in primary) == summary["main_evaluator"]["errors"]
    assert len({row["pair_id"] for row in pairs}) == len(pairs)
    assert summary["overlap_audit"]["reliable_unique_pairs"] < 200
    assert summary["local_judge"]["valid_decisions"] >= 200
    assert summary["local_judge"]["options"]["num_gpu"] == 0
    assert summary["local_judge"]["order_swap"]["n"] == 50
    assert summary["local_judge"]["same_order_repeat"]["n"] == 50

    report_pages = pdf_pages(ROOT / "docs/report.pdf")
    defense_pages = pdf_pages(ROOT / "docs/defense.pdf")
    assert 1 <= report_pages <= 5, f"Report has {report_pages} pages (limit 5)"
    assert 1 <= defense_pages <= 8, f"Slides have {defense_pages} pages (limit 8)"

    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    lines = [
        "K06 submission check: PASS",
        f"Repeat analysis: {duration:.2f} s (<600 s)",
        "Result files: byte-identical on repeat run",
        "Raw data: SHA-256 verified",
        "CSV schema/counts: verified",
        "Unit tests: passed",
        f"Report: {report_pages} pages (limit 5)",
        f"Defense slides: {defense_pages} pages (limit 8)",
    ]
    with (RESULTS / "checks.txt").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
