"""Evaluate promo outputs against a human-authored blind gold set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from promo_finder.parse import parse_ts


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _promos_from_path(path: str | Path) -> list[dict]:
    target = Path(path)
    if target.is_dir():
        target = target / "promos.json"
    value = _load_json(target)
    return value if isinstance(value, list) else value.get("promos", [])


def _segments(promo: dict) -> list[dict]:
    return promo.get("segments", []) or []


def _seconds(segment: dict, key: str) -> float:
    value = segment.get(f"{key}_s")
    if value is not None:
        return float(value)
    value = segment.get(key, 0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return parse_ts(str(value))


def _interval_iou(left: dict, right: dict) -> float:
    if left.get("episode") != right.get("episode"):
        return 0.0
    start = max(_seconds(left, "start"), _seconds(right, "start"))
    end = min(_seconds(left, "end"), _seconds(right, "end"))
    intersection = max(0.0, end - start)
    union = max(
        _seconds(left, "end"), _seconds(right, "end")
    ) - min(
        _seconds(left, "start"), _seconds(right, "start")
    )
    return intersection / union if union else 0.0


def _matches(prediction: dict, gold: dict) -> bool:
    prediction_segments = _segments(prediction)
    gold_segments = _segments(gold)
    for predicted in prediction_segments:
        for expected in gold_segments:
            if _interval_iou(predicted, expected) >= 0.5:
                return True
            if (
                predicted.get("episode") == expected.get("episode")
                and predicted.get("scene") is not None
                and predicted.get("scene") == expected.get("scene")
                and max(
                    _seconds(predicted, "start"),
                    _seconds(expected, "start"),
                )
                < min(
                    _seconds(predicted, "end"),
                    _seconds(expected, "end"),
                )
            ):
                return True
    return False


def _validity(promos: list[dict]) -> dict:
    checks = {
        "duration_20_to_60": 0,
        "ordered_non_overlapping": 0,
        "hook_verified": 0,
        "cliffhanger_verified": 0,
        "max_3_segments": 0,
    }
    for promo in promos:
        segments = _segments(promo)
        duration = sum(
            _seconds(segment, "end") - _seconds(segment, "start")
            for segment in segments
        )
        if 20 <= duration <= 60:
            checks["duration_20_to_60"] += 1
        ordered = len(segments) <= 3
        for previous, current in zip(segments, segments[1:]):
            if current.get("episode", 0) < previous.get("episode", 0):
                ordered = False
            if (
                current.get("episode") == previous.get("episode")
                and _seconds(current, "start") < _seconds(previous, "end")
            ):
                ordered = False
        if ordered:
            checks["ordered_non_overlapping"] += 1
        if promo.get("hook_verified") is True:
            checks["hook_verified"] += 1
        if promo.get("cliffhanger_verified") is True:
            checks["cliffhanger_verified"] += 1
        if len(segments) <= 3:
            checks["max_3_segments"] += 1

    total = len(promos)
    rule_values = list(checks.values())
    return {
        "promos": total,
        "checks": checks,
        "all_rules_rate_pct": round(
            100 * sum(value == total for value in rule_values) / len(rule_values),
            1,
        ) if total else None,
    }


def _gold_metrics(predictions: list[dict], gold: list[dict]) -> dict:
    if not gold:
        return {
            "gold_promos": 0,
            "precision": None,
            "recall": None,
            "note": "Populate gold_blind.json before interpreting precision or recall.",
        }
    prediction_hits = sum(
        any(_matches(prediction, expected) for expected in gold)
        for prediction in predictions
    )
    gold_hits = sum(
        any(_matches(prediction, expected) for prediction in predictions)
        for expected in gold
    )
    return {
        "gold_promos": len(gold),
        "matched_predictions": prediction_hits,
        "matched_gold": gold_hits,
        "precision": round(prediction_hits / len(predictions), 4) if predictions else 0.0,
        "recall": round(gold_hits / len(gold), 4),
    }


def _stability(first: list[dict], second: list[dict] | None) -> dict:
    if second is None:
        return {"top_n": 20, "jaccard": None, "note": "Pass --second-output for a stability run."}
    first_ids = {str(p.get("candidate_id")) for p in first[:20]}
    second_ids = {str(p.get("candidate_id")) for p in second[:20]}
    union = first_ids | second_ids
    return {
        "top_n": 20,
        "first_count": len(first_ids),
        "second_count": len(second_ids),
        "intersection": len(first_ids & second_ids),
        "jaccard": round(len(first_ids & second_ids) / len(union), 4) if union else 1.0,
    }


def evaluate(
    output: str | Path,
    gold_path: str | Path,
    second_output: str | Path | None = None,
) -> dict:
    predictions = _promos_from_path(output)
    gold_value = _load_json(gold_path)
    gold = gold_value.get("promos", []) if isinstance(gold_value, dict) else gold_value
    second = _promos_from_path(second_output) if second_output else None
    return {
        "output": str(output),
        "validity": _validity(predictions),
        "gold": _gold_metrics(predictions, gold),
        "stability": _stability(predictions, second),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="Run directory or promos.json")
    parser.add_argument("--gold", default=str(Path(__file__).with_name("gold_blind.json")))
    parser.add_argument("--second-output", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    result = evaluate(args.output, args.gold, args.second_output)
    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

