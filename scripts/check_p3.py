"""Check the K06 Practice 3 audit files without filling in human judgments.

The prepared phase checks the label-blind packet that can be shared with
annotators. The final phase checks the completed packet after independent
human annotation and scorer disclosure.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SLICE_FIELDS = {"id", "group", "instruction", "answer_a", "answer_b"}
ANNOTATION_FIELDS = ["id", "annotator", "label", "order", "instruction_version", "elapsed_seconds"]
BASELINE_FIELDS = ["id", "verdict"]
PROBE_FIELDS = ["probe", "n", "metric", "value", "interpretation"]
VERDICTS = {"A", "B", "TIE"}
HUMAN_LABELS = VERDICTS | {"SKIP"}
ANNOTATORS = ("A1", "A2", "A3")
NOTEBOOK_INITIALS = {"A1": "AU", "A2": "VO", "A3": "AD"}
EXPECTED_IDS = [f"K06-P3-{number:03d}" for number in range(1, 53)]
PREPARED_FILES = {
    "slice.jsonl", "instruction.md", "annotations.csv",
    "baseline_predictions.csv", "probe_results.csv",
}
PRIVATE_FILES = {"scorer.jsonl", "assistant_annotations.csv", "scorer_swap.jsonl"}


def issue(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def read_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.is_file():
        errors.append(f"Missing {path}")
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            errors.append(f"{path.name}:{line_number}: empty line")
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path.name}:{line_number}: expected a JSON object")
            continue
        records.append(record)
    return records


def read_csv(path: Path, fields: list[str], errors: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        errors.append(f"Missing {path}")
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != fields:
            errors.append(f"{path.name}: expected columns {','.join(fields)}")
            return []
        rows = list(reader)
    for number, row in enumerate(rows, start=2):
        if None in row or any(value is None for value in row.values()):
            errors.append(f"{path.name}:{number}: malformed CSV row")
    return rows


def check_slice(audit: Path, errors: list[str]) -> tuple[set[str], set[str]]:
    rows = read_jsonl(audit / "slice.jsonl", errors)
    issue(errors, len(rows) == 52, f"slice.jsonl: expected 52 objects, found {len(rows)}")
    seen_pairs = set()
    for number, row in enumerate(rows, start=1):
        prefix = f"slice.jsonl:{number}"
        issue(errors, set(row) == SLICE_FIELDS, f"{prefix}: unexpected or missing fields")
        expected_id = EXPECTED_IDS[number - 1] if number <= 52 else None
        issue(errors, row.get("id") == expected_id, f"{prefix}: expected id {expected_id}")
        expected_group = "core" if number <= 20 else "second"
        issue(errors, row.get("group") == expected_group, f"{prefix}: expected group {expected_group}")
        for field in ("instruction", "answer_a", "answer_b"):
            issue(errors, isinstance(row.get(field), str) and bool(row[field].strip()),
                  f"{prefix}: {field} must be nonempty text")
        if all(isinstance(row.get(field), str) for field in ("instruction", "answer_a", "answer_b")):
            issue(errors, row["answer_a"] != row["answer_b"], f"{prefix}: identical answers")
            pair = row["instruction"], *sorted((row["answer_a"], row["answer_b"]))
            issue(errors, pair not in seen_pairs, f"{prefix}: duplicate text pair")
            seen_pairs.add(pair)
    core = {row["id"] for row in rows
            if row.get("group") == "core" and isinstance(row.get("id"), str)}
    second = {row["id"] for row in rows
              if row.get("group") == "second" and isinstance(row.get("id"), str)}
    return core, second


def check_instruction(audit: Path, errors: list[str]) -> None:
    path = audit / "instruction.md"
    if not path.is_file():
        errors.append(f"Missing {path}")
        return
    text = path.read_text(encoding="utf-8-sig")
    issue(errors, "К06" in text or "K06" in text, "instruction.md: identify team K06")
    issue(errors, "1.0" in text, "instruction.md: specify version 1.0")
    for token in ("A", "B", "TIE"):
        issue(errors, token in text, f"instruction.md: define {token}")
    for placeholder in ("Команда: Кxx", "Опишите, что именно", "Перечислите все допустимые"):
        issue(errors, placeholder not in text, f"instruction.md: template placeholder remains: {placeholder}")


def check_annotations(audit: Path, core: set[str], second: set[str], phase: str,
                      errors: list[str]) -> None:
    rows = read_csv(audit / "annotations.csv", ANNOTATION_FIELDS, errors)
    issue(errors, len(rows) == 84, f"annotations.csv: expected 84 rows, found {len(rows)}")
    by_annotator: dict[str, list[dict[str, str]]] = defaultdict(list)
    pairs = []
    for number, row in enumerate(rows, start=2):
        prefix = f"annotations.csv:{number}"
        annotator = row["annotator"]
        object_id = row["id"]
        issue(errors, annotator in ANNOTATORS, f"{prefix}: unknown annotator {annotator}")
        issue(errors, object_id in core | second, f"{prefix}: unknown id {object_id}")
        issue(errors, row["order"] in {"A-first", "B-first"}, f"{prefix}: invalid order")
        issue(errors, row["instruction_version"] in {"1.0", "1.1"},
              f"{prefix}: invalid instruction_version")
        if phase == "prepared":
            issue(errors, row["label"] == "", f"{prefix}: human label must be blank before annotation")
            issue(errors, row["elapsed_seconds"] == "", f"{prefix}: elapsed time must be blank")
        else:
            issue(errors, row["label"] in HUMAN_LABELS,
                  f"{prefix}: label must be A, B, TIE, or SKIP")
            seconds = finite_number(row["elapsed_seconds"])
            issue(errors, seconds is not None and seconds > 0,
                  f"{prefix}: elapsed_seconds must be positive")
        by_annotator[annotator].append(row)
        pairs.append((annotator, object_id))
    issue(errors, len(pairs) == len(set(pairs)), "annotations.csv: duplicate annotator/id pair")
    for annotator in ANNOTATORS:
        ids = [row["id"] for row in by_annotator[annotator]]
        issue(errors, len(ids) == 28, f"annotations.csv: {annotator} needs 28 rows")
        issue(errors, {object_id for object_id in ids if object_id in core} == core,
              f"annotations.csv: {annotator} needs every core id")
        issue(errors, len([object_id for object_id in ids if object_id in second]) == 8,
              f"annotations.csv: {annotator} needs eight second ids")
    second_counts = Counter(object_id for _, object_id in pairs if object_id in second)
    issue(errors, len(second_counts) == 24 and all(count == 1 for count in second_counts.values()),
          "annotations.csv: use 24 distinct second ids once each")


def check_personal_templates(personal_dir: Path, audit: Path, errors: list[str]) -> None:
    team_rows = read_csv(audit / "annotations.csv", ANNOTATION_FIELDS, errors)
    for annotator in ANNOTATORS:
        initials = NOTEBOOK_INITIALS[annotator]
        path = personal_dir / f"{initials}_annotations.csv"
        rows = read_csv(path, ANNOTATION_FIELDS, errors)
        expected = [row for row in team_rows if row.get("annotator") == annotator]
        issue(errors, len(rows) == 28, f"{path.name}: expected 28 assigned rows")
        issue(errors, len(expected) == 28, f"annotations.csv: expected 28 rows for {annotator}")
        for number, (row, assignment) in enumerate(zip(rows, expected), start=2):
            prefix = f"{path.name}:{number}"
            for field in ("id", "annotator", "order", "instruction_version"):
                issue(errors, row.get(field) == assignment.get(field),
                      f"{prefix}: {field} differs from team template")
            issue(errors, row.get("label") == "", f"{prefix}: label must be blank")
            issue(errors, row.get("elapsed_seconds") == "",
                  f"{prefix}: elapsed_seconds must be blank")


def check_baseline(audit: Path, expected_ids: set[str], phase: str,
                   errors: list[str]) -> None:
    rows = read_csv(audit / "baseline_predictions.csv", BASELINE_FIELDS, errors)
    ids = [row["id"] for row in rows]
    issue(errors, len(rows) == 52 and set(ids) == expected_ids and len(set(ids)) == 52,
          "baseline_predictions.csv: expected exactly one row for each slice id")
    for number, row in enumerate(rows, start=2):
        allowed = VERDICTS | ({""} if phase == "prepared" else set())
        issue(errors, row["verdict"] in allowed,
              f"baseline_predictions.csv:{number}: verdict must be A, B, or TIE"
              + (", or blank in prepared phase" if phase == "prepared" else ""))


def finite_number(value: str | None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def check_probes(audit: Path, phase: str, errors: list[str]) -> None:
    rows = read_csv(audit / "probe_results.csv", PROBE_FIELDS, errors)
    if phase == "prepared":
        issue(errors, not rows, "probe_results.csv: keep results empty before the audit")
        return
    issue(errors, len(rows) >= 2, "probe_results.csv: track A requires at least two probes")
    for number, row in enumerate(rows, start=2):
        prefix = f"probe_results.csv:{number}"
        for field in ("probe", "metric", "interpretation"):
            issue(errors, bool((row[field] or "").strip()),
                  f"{prefix}: {field} is blank")
        cases = row["n"] or ""
        issue(errors, cases.isdecimal() and int(cases) > 0,
              f"{prefix}: n must be a positive integer")
        issue(errors, finite_number(row["value"]) is not None,
              f"{prefix}: value must be a finite number without percent sign")


def check_scorer(audit: Path, expected_ids: set[str], phase: str,
                 errors: list[str]) -> None:
    path = audit / "scorer.jsonl"
    if phase == "prepared":
        for name in sorted(PRIVATE_FILES):
            issue(errors, not (audit / name).exists(),
                  f"{name}: keep judgments outside shared audit until annotation ends")
        if audit.is_dir():
            for item in audit.iterdir():
                if item.name not in PREPARED_FILES | PRIVATE_FILES:
                    errors.append(f"{item.name}: unexpected file in prepared shared audit")
        return
    rows = read_jsonl(path, errors)
    ids = [row.get("id") for row in rows]
    valid_ids = {item for item in ids if isinstance(item, str)}
    issue(errors, len(rows) == 52 and valid_ids == expected_ids and len(valid_ids) == 52,
          "scorer.jsonl: expected exactly one verdict for each slice id")
    for number, row in enumerate(rows, start=1):
        issue(errors, set(row) == {"id", "verdict"},
              f"scorer.jsonl:{number}: unexpected or missing fields")
        issue(errors, isinstance(row.get("verdict"), str) and row["verdict"] in VERDICTS,
              f"scorer.jsonl:{number}: verdict must be A, B, or TIE")


def check_notebooks(directory: Path, errors: list[str]) -> None:
    for annotator in ANNOTATORS:
        path = directory / f"K06_{NOTEBOOK_INITIALS[annotator]}_lab3_student.ipynb"
        if not path.is_file():
            errors.append(f"Missing {path}")
            continue
        try:
            notebook = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            errors.append(f"{path.name}: invalid notebook JSON")
            continue
        issue(errors, isinstance(notebook, dict) and bool(notebook.get("cells")),
              f"{path.name}: notebook has no cells")
        if isinstance(notebook, dict):
            code_cells = [cell for cell in notebook.get("cells", [])
                          if isinstance(cell, dict) and cell.get("cell_type") == "code"]
            source = "\n".join("".join(cell.get("source", [])) for cell in code_cells)
            issue(errors, "raise NotImplementedError" not in source,
                  f"{path.name}: unfinished notebook function")
            issue(errors, bool(re.search(r"TEAM_ID\s*=\s*['\"]K06['\"]", source)),
                  f"{path.name}: TEAM CONFIG must use K06")
            issue(errors, bool(re.search(r"PAIRWISE_TASK\s*=\s*True", source)),
                  f"{path.name}: TEAM CONFIG must enable pairwise comparison")
            issue(errors, any(cell.get("outputs") for cell in code_cells),
                  f"{path.name}: save notebook with executed cell outputs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepared", "final"), default="prepared")
    parser.add_argument("--audit-dir", type=Path, default=Path("audit"))
    parser.add_argument("--notebooks-dir", type=Path, default=Path("notebooks"))
    parser.add_argument("--personal-dir", type=Path, default=Path("personal_annotations"))
    args = parser.parse_args()
    audit = args.audit_dir if args.audit_dir.is_absolute() else ROOT / args.audit_dir
    notebooks = args.notebooks_dir if args.notebooks_dir.is_absolute() else ROOT / args.notebooks_dir
    personal = args.personal_dir if args.personal_dir.is_absolute() else ROOT / args.personal_dir

    errors: list[str] = []
    core, second = check_slice(audit, errors)
    check_instruction(audit, errors)
    check_annotations(audit, core, second, args.phase, errors)
    if args.phase == "prepared":
        check_personal_templates(personal, audit, errors)
    check_baseline(audit, core | second, args.phase, errors)
    check_probes(audit, args.phase, errors)
    check_scorer(audit, core | second, args.phase, errors)
    if args.phase == "final":
        check_notebooks(notebooks, errors)
    if errors:
        for error in errors[:20]:
            print(f"FAIL: {error}")
        if len(errors) > 20:
            print(f"... and {len(errors) - 20} further issue(s)")
        raise SystemExit(f"{args.phase} phase: {len(errors)} issue(s)")
    print(f"PASS: {args.phase} phase; 52 slice objects, 84 annotation assignments")


if __name__ == "__main__":
    main()
