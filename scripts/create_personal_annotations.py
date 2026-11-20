"""Create three blank personal CSVs from the team assignment template."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["id", "annotator", "label", "order", "instruction_version", "elapsed_seconds"]
ANNOTATORS = ("A1", "A2", "A3")
INITIALS = {"A1": "AU", "A2": "VO", "A3": "AD"}


def read_team_assignments(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"Unexpected columns in {path}")
        rows = list(reader)
    if len(rows) != 84 or any(row["label"] or row["elapsed_seconds"] for row in rows):
        raise ValueError("Team template must contain 84 unfilled assignments")
    for annotator in ANNOTATORS:
        assigned = [row for row in rows if row["annotator"] == annotator]
        if len(assigned) != 28 or len({row["id"] for row in assigned}) != 28:
            raise ValueError(f"Expected 28 unique assignments for {annotator}")
    return rows


def create_personal_csv(path: Path, assignments: list[dict[str, str]]) -> None:
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != COLUMNS:
                raise ValueError(f"Unexpected columns in existing {path}")
            rows = list(reader)
        expected = [(row["id"], row["annotator"], row["order"]) for row in assignments]
        actual = [(row["id"], row["annotator"], row["order"]) for row in rows]
        if actual != expected:
            raise ValueError(f"Existing assignments differ; refusing to overwrite {path}")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(assignments)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-audit-dir", type=Path, default=ROOT / "audit")
    parser.add_argument("--personal-dir", type=Path, default=ROOT / "personal_annotations")
    args = parser.parse_args()

    team_audit = args.team_audit_dir.resolve()
    personal_dir = args.personal_dir.resolve()
    personal_dir.mkdir(parents=True, exist_ok=True)
    rows = read_team_assignments(team_audit / "annotations.csv")
    for annotator in ANNOTATORS:
        assigned = [row for row in rows if row["annotator"] == annotator]
        path = personal_dir / f"{INITIALS[annotator]}_annotations.csv"
        create_personal_csv(path, assigned)
        print(f"{annotator}: 28 blank assignments in {path}")


if __name__ == "__main__":
    main()
