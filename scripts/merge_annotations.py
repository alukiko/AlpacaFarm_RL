"""Merge complete, independently filled Practice 3 annotation workspaces."""

from __future__ import annotations

import argparse
import csv
import math
import os
import tempfile
from pathlib import Path


FIELDS = ["id", "annotator", "label", "order", "instruction_version", "elapsed_seconds"]
ANNOTATORS = ("A1", "A2", "A3")
LABELS = {"A", "B", "TIE", "SKIP"}
VERSIONS = {"1.0", "1.1"}
ROWS_PER_ANNOTATOR = 28


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


def merge_annotations(team_audit_dir: Path, workspaces_dir: Path) -> bool:
    team_path = team_audit_dir / "annotations.csv"
    team_rows = read_annotations(team_path)
    assignments = validate_team_rows(team_path, team_rows)

    personal_rows = {}
    for annotator in ANNOTATORS:
        path = workspaces_dir / annotator / "audit" / "annotations.csv"
        rows = read_annotations(path)
        validate_personal_rows(path, annotator, rows, assignments[annotator])
        personal_rows[annotator] = rows

    merged = [row.copy() for row in team_rows]
    positions = {
        (row["annotator"], row["id"]): number
        for number, row in enumerate(team_rows)
    }
    for annotator in ANNOTATORS:
        for team_row, personal_row in zip(assignments[annotator], personal_rows[annotator]):
            if team_row["label"] and any(
                team_row[field] != personal_row[field]
                for field in ("label", "elapsed_seconds")
            ):
                raise ValueError(
                    f"{team_path}: existing annotation conflicts with {annotator} / {team_row['id']}"
                )
            target = merged[positions[(annotator, personal_row["id"])]]
            for field in ("label", "elapsed_seconds", "instruction_version"):
                target[field] = personal_row[field]

    if merged == team_rows:
        return False
    save_annotations(team_path, merged)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-audit-dir", type=Path, default=Path("audit"))
    parser.add_argument("--workspaces-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        changed = merge_annotations(args.team_audit_dir, args.workspaces_dir)
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))
    print("Merged all 84 annotations." if changed else "All 84 annotations already match.")


if __name__ == "__main__":
    main()
