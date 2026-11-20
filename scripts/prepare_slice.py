"""Build the label-blind 52-pair slice for K06 Practice 3.

The selection matches the project's exact full-text grouping and SHA-256
pair ordering. Human preferences are used only to choose four-vote majority
pairs; neither preferences nor source pair IDs enter the annotation file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SOURCE_SHA256 = "e75b70d6176cf50f8d9898065541445050e164ebce3704e6d7becf99e39ed704"
SELECTION_START = 200
SELECTION_SIZE = 52
CORE_SIZE = 20


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preference_index(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number in (1.0, 2.0) else None


def pair_texts(row: dict[str, Any]) -> tuple[str, str, str] | None:
    values = row.get("instruction"), row.get("output_1"), row.get("output_2")
    if any(not isinstance(value, str) for value in values):
        return None
    instruction, answer_a, answer_b = values
    if answer_a == answer_b:
        return None
    return instruction, answer_a, answer_b


def grouped_majority_pairs(rows: list[dict[str, Any]]) -> tuple[list[tuple[str, tuple[str, str, str]]], int]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        texts = pair_texts(row)
        vote = preference_index(row.get("preference"))
        if texts is None or vote is None:
            continue

        key = texts[0], *sorted((texts[1], texts[2]))
        if key not in groups:
            groups[key] = {"texts": texts, "votes": [0, 0]}
        original = groups[key]["texts"]
        if (texts[1], texts[2]) != (original[1], original[2]):
            vote = 3 - vote
        groups[key]["votes"][vote - 1] += 1

    eligible = []
    for key, group in groups.items():
        first_votes, second_votes = group["votes"]
        if first_votes + second_votes != 4 or first_votes == second_votes:
            continue
        pair_id = hashlib.sha256(
            json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        eligible.append((pair_id, group["texts"]))
    eligible.sort(key=lambda item: item[0])
    return eligible, len(groups)


def build_slice(eligible: list[tuple[str, tuple[str, str, str]]]) -> list[dict[str, str]]:
    selected = eligible[SELECTION_START:SELECTION_START + SELECTION_SIZE]
    if len(selected) != SELECTION_SIZE:
        raise ValueError(f"Need {SELECTION_START + SELECTION_SIZE} eligible pairs; got {len(eligible)}")

    result = []
    for number, (_, texts) in enumerate(selected, start=1):
        instruction, answer_a, answer_b = texts
        result.append({
            "id": f"K06-P3-{number:03d}",
            "group": "core" if number <= CORE_SIZE else "second",
            "instruction": instruction,
            "answer_a": answer_a,
            "answer_b": answer_b,
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Official AlpacaFarm human JSON")
    parser.add_argument("--output", type=Path, default=Path("audit/slice.jsonl"))
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    source_hash = file_sha256(source)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"Unexpected source SHA-256: {source_hash}")
    with source.open(encoding="utf-8") as stream:
        rows = json.load(stream)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Source must be a JSON array of objects")

    eligible, unique_pairs = grouped_majority_pairs(rows)
    selected = build_slice(eligible)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected).encode("utf-8")
    if output.exists() and output.read_bytes() != payload:
        raise ValueError(f"Refusing to overwrite a different slice: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)

    print(f"Source SHA-256: {source_hash}")
    print(f"Human rows: {len(rows)}; unique pairs: {unique_pairs}; eligible majority pairs: {len(eligible)}")
    print(f"Selected positions: {SELECTION_START}:{SELECTION_START + SELECTION_SIZE}")
    print(f"Wrote {CORE_SIZE} core and {SELECTION_SIZE - CORE_SIZE} second pairs to {output}")
    print(f"Slice SHA-256: {hashlib.sha256(payload).hexdigest()}")


if __name__ == "__main__":
    main()
