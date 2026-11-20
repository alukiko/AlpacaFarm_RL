"""Merge three completed personal annotation CSVs into the team CSV."""

from __future__ import annotations

import argparse
import csv
import math
import os
import tempfile
from pathlib import Path


FIELDS = ["id", "annotator", "label", "order", "instruction_version", "elapsed_seconds"]
ANNOTATORS = ("A1", "A2", "A3")
INITIALS = {"A1": "AU", "A2": "VO", "A3": "AD"}
LABELS = {"A", "B", "TIE", "SKIP"}
VERSIONS = {"1.0", "1.1"}
ROWS_PER_ANNOTATOR = 28
RESULT_FIELDS = ("label", "elapsed_seconds", "instruction_version")


def read_annotations(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"{path}: expected columns {','.join(FIELDS)}")
        rows = list(reader)
    for number, row in enumerate(rows, start=2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{path}:{number}: malformed CSV row")
    return rows


def valid_elapsed(value: str) -> bool:
    try:
        seconds = float(value)
    except ValueError:
        return False
    return math.isfinite(seconds) and seconds > 0


def validate_team_rows(path: Path, rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    if len(rows) != len(ANNOTATORS) * ROWS_PER_ANNOTATOR:
        raise ValueError(f"{path}: expected 84 assignments, found {len(rows)}")

    assigned = {annotator: [] for annotator in ANNOTATORS}
    seen = set()
    for number, row in enumerate(rows, start=2):
        annotator = row["annotator"]
        key = (annotator, row["id"])
        if annotator not in assigned or not row["id"] or key in seen:
            raise ValueError(f"{path}:{number}: invalid or duplicate assignment {key}")
        if row["order"] not in {"A-first", "B-first"}:
            raise ValueError(f"{path}:{number}: invalid order")
        if row["instruction_version"] not in VERSIONS:
            raise ValueError(f"{path}:{number}: invalid instruction_version")
        if row["label"] or row["elapsed_seconds"]:
            if row["label"] not in LABELS or not valid_elapsed(row["elapsed_seconds"]):
                raise ValueError(f"{path}:{number}: invalid existing label or elapsed_seconds")
        seen.add(key)
        assigned[annotator].append(row)

    for annotator, assignments in assigned.items():
        if len(assignments) != ROWS_PER_ANNOTATOR:
            raise ValueError(f"{path}: {annotator} needs {ROWS_PER_ANNOTATOR} assignments")
    return assigned


def validate_personal_rows(
    path: Path, annotator: str, rows: list[dict[str, str]],
    assignments: list[dict[str, str]],
) -> None:
    if len(rows) != ROWS_PER_ANNOTATOR:
        raise ValueError(f"{path}: expected {ROWS_PER_ANNOTATOR} rows, found {len(rows)}")
    for number, (row, expected) in enumerate(zip(rows, assignments), start=2):
        for field in ("id", "annotator", "order"):
            if row[field] != expected[field]:
                raise ValueError(f"{path}:{number}: {field} differs from team template for {annotator}")
        if row["label"] not in LABELS:
            raise ValueError(f"{path}:{number}: label must be A, B, TIE, or SKIP")
        if not valid_elapsed(row["elapsed_seconds"]):
            raise ValueError(f"{path}:{number}: elapsed_seconds must be finite and positive")
        if row["instruction_version"] not in VERSIONS:
            raise ValueError(f"{path}:{number}: instruction_version must be 1.0 or 1.1")


def save_annotations(path: Path, rows: list[dict[str, str]]) -> None:
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def merge_annotations(team_audit_dir: Path, personal_dir: Path) -> bool:
    team_path = team_audit_dir / "annotations.csv"
    team_rows = read_annotations(team_path)
    merged = [row.copy() for row in team_rows]
    assignments = validate_team_rows(team_path, merged)

    # Сначала проверяем все личные таблицы целиком.
    personal_rows = {}
    for annotator, team_assignments in assignments.items():
        path = personal_dir / f"{INITIALS[annotator]}_annotations.csv"
        rows = read_annotations(path)
        validate_personal_rows(path, annotator, rows, team_assignments)
        personal_rows[annotator] = rows

    # Строки assignments уже ссылаются на копию командного файла.
    for annotator, team_assignments in assignments.items():
        for team_row, personal_row in zip(team_assignments, personal_rows[annotator]):
            saved = (team_row["label"], team_row["elapsed_seconds"])
            incoming = (personal_row["label"], personal_row["elapsed_seconds"])
            if team_row["label"] and saved != incoming:
                raise ValueError(
                    f"{team_path}: existing annotation conflicts with {annotator} / {team_row['id']}"
                )
            for field in RESULT_FIELDS:
                team_row[field] = personal_row[field]

    if merged == team_rows:
        return False
    save_annotations(team_path, merged)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-audit-dir", type=Path, default=Path("audit"))
    parser.add_argument("--personal-dir", type=Path, default=Path("personal_annotations"))
    args = parser.parse_args()
    try:
        changed = merge_annotations(args.team_audit_dir, args.personal_dir)
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))
    print("Merged all 84 annotations." if changed else "All 84 annotations already match.")


if __name__ == "__main__":
    main()
