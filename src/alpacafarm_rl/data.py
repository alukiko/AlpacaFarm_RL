"""Load human annotations and audit overlap with published judge annotations."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HumanPair:
    pair_id: str
    instruction: str
    output_1: str
    output_2: str
    votes_1: int
    votes_2: int

    @property
    def n_votes(self) -> int:
        return self.votes_1 + self.votes_2

    @property
    def majority(self) -> int:
        if self.votes_1 > self.votes_2:
            return 1
        if self.votes_2 > self.votes_1:
            return 2
        return 0

    @property
    def agreement(self) -> str:
        if self.n_votes != 4:
            return "nonstandard_vote_count"
        return f"{max(self.votes_1, self.votes_2)}:{min(self.votes_1, self.votes_2)}"


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        rows = json.load(stream)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"Expected a JSON array of objects: {path}")
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_preference(value: Any) -> int | None:
    """Return the selected response index; zero and missing values are not votes."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number in (1.0, 2.0) else None


def _texts(row: dict[str, Any]) -> tuple[str, str, str] | None:
    values = (row.get("instruction"), row.get("output_1"), row.get("output_2"))
    if any(not isinstance(value, str) for value in values):
        return None
    instruction, output_1, output_2 = values
    if output_1 == output_2:
        return None
    return instruction, output_1, output_2


def _key(texts: tuple[str, str, str]) -> tuple[str, str, str]:
    instruction, output_1, output_2 = texts
    first, second = sorted((output_1, output_2))
    return instruction, first, second


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalized_key(texts: tuple[str, str, str]) -> tuple[str, str, str]:
    return _key(tuple(_normalized(text) for text in texts))


def group_human_annotations(
    rows: list[dict[str, Any]],
) -> tuple[list[HumanPair], dict[str, int]]:
    """Group votes by full instruction and unordered response texts."""
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    invalid_rows = 0
    for row in rows:
        texts = _texts(row)
        preference = parse_preference(row.get("preference"))
        if texts is None or preference is None:
            invalid_rows += 1
            continue

        key = _key(texts)
        if key not in groups:
            groups[key] = {"texts": texts, "votes": [0, 0]}
        original = groups[key]["texts"]
        reversed_order = (texts[1], texts[2]) != (original[1], original[2])
        vote = 3 - preference if reversed_order else preference
        groups[key]["votes"][vote - 1] += 1

    pairs = []
    for key, group in groups.items():
        pair_id = hashlib.sha256(
            json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        instruction, output_1, output_2 = group["texts"]
        votes_1, votes_2 = group["votes"]
        pairs.append(HumanPair(pair_id, instruction, output_1, output_2, votes_1, votes_2))
    pairs.sort(key=lambda pair: pair.pair_id)
    return pairs, {"input_rows": len(rows), "invalid_rows": invalid_rows, "unique_pairs": len(pairs)}


def _judge_index(
    rows: list[dict[str, Any]], normalize: bool
) -> tuple[dict[tuple[str, str, str], list[dict[str, Any]]], int]:
    index: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    invalid_rows = 0
    for row in rows:
        texts = _texts(row)
        preference = parse_preference(row.get("preference"))
        if texts is None or preference is None:
            invalid_rows += 1
            continue
        key = _normalized_key(texts) if normalize else _key(texts)
        index.setdefault(key, []).append(row)
    return index, invalid_rows


def audit_judge_overlap(
    pairs: list[HumanPair], judge_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Find full-text matches in either response order; reject ambiguous matches."""
    exact_index, invalid_rows = _judge_index(judge_rows, normalize=False)
    normalized_index, _ = _judge_index(judge_rows, normalize=True)
    audited = []
    counts = {
        "judge_rows": len(judge_rows),
        "invalid_judge_rows": invalid_rows,
        "exact_match_pairs": 0,
        "whitespace_only_match_pairs": 0,
        "direct_unique_pairs": 0,
        "swapped_unique_pairs": 0,
        "ambiguous_pairs": 0,
        "reliable_unique_pairs": 0,
    }

    for pair in pairs:
        texts = (pair.instruction, pair.output_1, pair.output_2)
        candidates = exact_index.get(_key(texts), [])
        match_kind = "exact"
        if candidates:
            counts["exact_match_pairs"] += 1
        else:
            candidates = normalized_index.get(_normalized_key(texts), [])
            match_kind = "whitespace_only"
            if candidates:
                counts["whitespace_only_match_pairs"] += 1

        result: dict[str, Any] = {
            "pair_id": pair.pair_id,
            "human_votes": pair.n_votes,
            "human_majority": pair.majority,
            "judge_rows_matched": len(candidates),
            "match_kind": match_kind if candidates else "unmatched",
            "orientation": "",
            "judge_preference_aligned": "",
        }
        if len(candidates) > 1:
            counts["ambiguous_pairs"] += 1
            result["match_kind"] = f"{match_kind}_ambiguous"
        elif len(candidates) == 1:
            judge = candidates[0]
            direct = (
                _normalized(judge["output_1"]) == _normalized(pair.output_1)
                and _normalized(judge["output_2"]) == _normalized(pair.output_2)
            )
            result["orientation"] = "direct" if direct else "swapped"
            preference = parse_preference(judge["preference"])
            result["judge_preference_aligned"] = preference if direct else 3 - preference
            counts[f"{result['orientation']}_unique_pairs"] += 1
            counts["reliable_unique_pairs"] += 1
        audited.append(result)

    counts["unmatched_pairs"] = sum(row["match_kind"] == "unmatched" for row in audited)
    return audited, counts
