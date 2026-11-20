"""Collect one participant's independent pairwise labels for Practice 3.

The participant sees only the objects assigned to their pseudonym. Predictions
from the scorer and labels from other participants are never displayed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
import time
from pathlib import Path


REQUIRED_COLUMNS = {
    "id", "annotator", "label", "order", "instruction_version", "elapsed_seconds"
}
LABELS = {"A", "B", "TIE", "SKIP"}


def load_objects(path: Path) -> dict[str, dict]:
    objects = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not all(key in item for key in ("id", "instruction", "answer_a", "answer_b")):
            raise ValueError(f"{path}:{line_number}: недостаёт полей пары")
        object_id = item["id"]
        if object_id in objects:
            raise ValueError(f"{path}:{line_number}: повтор ID {object_id}")
        objects[object_id] = item
    return objects


def load_annotations(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        if not REQUIRED_COLUMNS.issubset(columns):
            raise ValueError(f"{path}: недостаёт столбцов {sorted(REQUIRED_COLUMNS - set(columns))}")
        rows = list(reader)
    seen = set()
    for row in rows:
        key = (row["id"], row["annotator"])
        if key in seen:
            raise ValueError(f"{path}: повтор назначения {key}")
        seen.add(key)
    return columns, rows


def show_pair(item: dict, order: str, position: int, total: int) -> None:
    if order not in {"A-first", "B-first"}:
        raise ValueError(f"Неизвестный порядок показа: {order}")
    first, second = ("A", "B") if order == "A-first" else ("B", "A")
    print(f"\n{'=' * 72}\n{position}/{total}  ID: {item['id']}\n{'=' * 72}")
    print(f"Задание:\n{item['instruction']}\n")
    print(f"Ответ {first}:\n{item[f'answer_{first.lower()}']}\n")
    print(f"Ответ {second}:\n{item[f'answer_{second.lower()}']}\n")
    print("Введите A или B по имени ответа, TIE при равенстве, SKIP если оценить нельзя.")


def save_label(
    path: Path,
    assignment: dict[str, str],
    label: str,
    elapsed: float,
    instruction_version: str | None = None,
) -> None:
    # Re-read the current file so another participant's earlier saves are kept.
    columns, rows = load_annotations(path)
    matches = [row for row in rows if row["id"] == assignment["id"]
               and row["annotator"] == assignment["annotator"]]
    if len(matches) != 1 or matches[0]["order"] != assignment["order"]:
        raise ValueError("Назначение изменилось во время разметки; запись не сохранена")
    row = matches[0]
    if row["label"].strip():
        raise ValueError("Эта пара уже размечена; запись не перезаписана")
    row["label"] = label
    row["elapsed_seconds"] = f"{max(elapsed, 0.001):.3f}"
    if instruction_version is not None:
        row["instruction_version"] = instruction_version

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def annotate(
    audit_dir: Path,
    annotator: str,
    pilot_only: bool = False,
    instruction_version: str | None = None,
    annotations_file: Path | None = None,
) -> None:
    objects = load_objects(audit_dir / "slice.jsonl")
    annotations_path = annotations_file if annotations_file is not None else audit_dir / "annotations.csv"
    _, rows = load_annotations(annotations_path)
    assigned = [row for row in rows if row["annotator"] == annotator]
    if not assigned:
        raise ValueError(f"Для {annotator} нет назначенных пар")
    if any(row["id"] not in objects for row in assigned):
        raise ValueError("В annotations.csv есть ID, отсутствующие в slice.jsonl")
    if pilot_only:
        pilot_ids = [item["id"] for item in objects.values() if item.get("group") == "core"][:10]
        if len(pilot_ids) != 10:
            raise ValueError("Для пилота нужны первые 10 объектов core в slice.jsonl")
        assigned = [row for row in assigned if row["id"] in pilot_ids]
    remaining = [row for row in assigned if not row["label"].strip()]
    print(f"{annotator}: назначено {len(assigned)}, осталось {len(remaining)}.")
    print("Суждения остальных участников и предсказания модели здесь не показываются.")

    for position, row in enumerate(remaining, 1):
        start = time.monotonic()
        show_pair(objects[row["id"]], row["order"], position, len(remaining))
        while True:
            try:
                answer = input("Метка [A/B/TIE/SKIP; Q — выйти]: ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                answer = "Q"
                print()
            if answer == "Q":
                print("Разметка прервана. Уже сохранённые метки останутся в CSV.")
                return
            if answer in LABELS:
                break
            print("Введите A, B, TIE, SKIP или Q.")
        save_label(
            annotations_path, row, answer, time.monotonic() - start,
            instruction_version=instruction_version,
        )
        print("Сохранено.")
    print("Все назначенные пары размечены.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotator", required=True, choices=("A1", "A2", "A3"))
    parser.add_argument("--audit-dir", type=Path, default=Path("audit"))
    parser.add_argument("--annotations-file", type=Path, help="личная таблица; по умолчанию audit/annotations.csv")
    parser.add_argument("--pilot-only", action="store_true", help="только первые 10 объектов core")
    parser.add_argument(
        "--instruction-version", choices=("1.1",),
        help="записать новую версию инструкции для следующих суждений",
    )
    args = parser.parse_args()
    annotate(
        args.audit_dir, args.annotator, args.pilot_only, args.instruction_version,
        annotations_file=args.annotations_file,
    )


if __name__ == "__main__":
    main()
