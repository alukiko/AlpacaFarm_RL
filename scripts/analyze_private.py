"""Prepare length baseline and two scorer probes outside the shared branch."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_verdicts(path: Path) -> dict[str, str]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    verdicts = {row["id"]: row["verdict"] for row in rows}
    if len(rows) != len(verdicts) or set(verdicts.values()) - {"A", "B", "TIE"}:
        raise ValueError(f"Invalid verdict file: {path}")
    return verdicts


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    if path.is_relative_to(ROOT):
        raise ValueError(f"Keep generated predictions outside the shared branch: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def longer_answer(pair: dict[str, str]) -> str:
    length_a = len(pair["answer_a"].split())
    length_b = len(pair["answer_b"].split())
    if length_a == length_b:
        return "TIE"
    return "A" if length_a > length_b else "B"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", type=Path, default=ROOT / "audit/slice.jsonl")
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--swap", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    pairs = [json.loads(line) for line in args.slice.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = {pair["id"] for pair in pairs}
    base = read_verdicts(args.base)
    swap = read_verdicts(args.swap)
    if len(pairs) != 52 or len(ids) != 52 or set(base) != ids or set(swap) != ids:
        raise ValueError("Expected 52 matching, unique IDs in slice, base scorer, and swapped scorer")

    length_choices = {pair["id"]: longer_answer(pair) for pair in pairs}
    baseline = [{"id": pair_id, "verdict": verdict} for pair_id, verdict in length_choices.items()]
    unequal = [pair_id for pair_id, choice in length_choices.items() if choice != "TIE"]
    order_changes = sum(base[object_id] != swap[object_id] for object_id in ids)
    longer_choices = sum(base[pair_id] == length_choices[pair_id] for pair_id in unequal)
    probes = [
        {
            "probe": "Перестановка A/B",
            "n": len(pairs),
            "metric": "доля изменившихся решений после обратного порядка",
            "value": round(order_changes / len(pairs), 6),
            "interpretation": f"После выравнивания букв изменилось {order_changes} из {len(pairs)} решений.",
        },
        {
            "probe": "Связь с длиной ответа",
            "n": len(unequal),
            "metric": "доля выбора более длинного ответа",
            "value": round(longer_choices / len(unequal), 6),
            "interpretation": (
                f"Оценщик выбрал более длинный ответ в {longer_choices} из {len(unequal)} пар "
                "с разной длиной; это описательная связь, а не доказательство причины."
            ),
        },
    ]
    output_dir = args.output_dir.expanduser().resolve()
    write_csv(output_dir / "baseline_predictions.csv", ["id", "verdict"], baseline)
    write_csv(output_dir / "probe_results.csv", ["probe", "n", "metric", "value", "interpretation"], probes)
    for row in probes:
        print(f"{row['probe']}: n={row['n']}, value={row['value']}")


if __name__ == "__main__":
    main()
