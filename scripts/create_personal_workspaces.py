"""Create separate blank audit folders for the three future human annotators."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["id", "annotator", "label", "order", "instruction_version", "elapsed_seconds"]
ANNOTATORS = ("A1", "A2", "A3")


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


def copy_immutable(source: Path, target: Path) -> None:
    if target.exists():
        if target.read_bytes() != source.read_bytes():
            raise ValueError(f"Existing file differs; refusing to overwrite {target}")
        return
    shutil.copyfile(source, target)


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
    parser.add_argument("--workspaces-dir", type=Path, default=ROOT.parent / "k06_p3_workspaces")
    args = parser.parse_args()

    team_audit = args.team_audit_dir.resolve()
    workspaces = args.workspaces_dir.resolve()
    rows = read_team_assignments(team_audit / "annotations.csv")
    for annotator in ANNOTATORS:
        personal_audit = workspaces / annotator / "audit"
        personal_audit.mkdir(parents=True, exist_ok=True)
        for name in ("slice.jsonl", "instruction.md"):
            copy_immutable(team_audit / name, personal_audit / name)
        assigned = [row for row in rows if row["annotator"] == annotator]
        create_personal_csv(personal_audit / "annotations.csv", assigned)
        print(f"{annotator}: 28 blank assignments in {personal_audit}")


if __name__ == "__main__":
    main()
