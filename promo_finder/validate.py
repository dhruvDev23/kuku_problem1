# promo_finder/validate.py – deterministic candidate validation
"""Resolve, validate, and (optionally) repair LLM-produced promo picks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Callable, Optional

from .parse import Episode, Event, render_compact


@dataclass
class ValidationReport:
    total_raw: int = 0
    valid_first_pass: int = 0
    repaired: int = 0
    dropped: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    repair_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def valid_rate(self) -> float:
        return self.valid_first_pass / max(self.total_raw, 1)

    @property
    def repair_rate(self) -> float:
        return self.repaired / max(self.total_raw, 1)

    @property
    def drop_rate(self) -> float:
        return self.dropped / max(self.total_raw, 1)

    def to_dict(self) -> dict:
        return {
            "total_raw": self.total_raw,
            "valid_first_pass": self.valid_first_pass,
            "repaired": self.repaired,
            "dropped": self.dropped,
            "valid_rate_pct": round(self.valid_rate * 100, 1),
            "repair_rate_pct": round(self.repair_rate * 100, 1),
            "drop_rate_pct": round(self.drop_rate * 100, 1),
            "drop_reasons": dict(sorted(self.drop_reasons.items())),
            "repair_reasons": dict(sorted(self.repair_reasons.items())),
        }


def _normalise_text(value: str) -> str:
    value = str(value or "").strip()
    value = value.replace("“", '"').replace("”", '"').replace("’", "'")
    value = re.sub(r"\s+", " ", value)
    return value.strip('"').strip().casefold()


def _fuzzy_match(needle: str, haystack: str, threshold: float = 0.78) -> bool:
    """Match a quote against an event without accepting unrelated text."""
    target = _normalise_text(needle)
    source = _normalise_text(haystack)
    if not target or not source:
        return False
    if target in source:
        return True
    if len(target.split()) < 3:
        return False

    target_words = target.split()
    source_words = source.split()
    window_size = len(target_words)
    windows = [
        " ".join(source_words[i:i + window_size])
        for i in range(max(1, len(source_words) - window_size + 1))
    ]
    return max(
        (SequenceMatcher(None, target, window).ratio() for window in windows),
        default=0.0,
    ) >= threshold


def _coerce_event_id(value) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group())
    return None


def _coerce_episode(value, default: int) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value))
        return int(match.group()) if match else None


def _episode_map(episodes: Episode | list[Episode] | dict[int, Episode]) -> dict[int, Episode]:
    if isinstance(episodes, Episode):
        return {episodes.episode: episodes}
    if isinstance(episodes, dict):
        return episodes
    return {episode.episode: episode for episode in episodes}


def _find_event(episode: Episode, event_id: int) -> Optional[Event]:
    return next((event for event in episode.events if event.id == event_id), None)


def _event_text_matches(events: list[Event], quote: str) -> bool:
    return bool(quote) and any(_fuzzy_match(quote, event.text) for event in events)


def _last_event(episode: Episode, segment: dict) -> Optional[Event]:
    return _find_event(episode, segment["end_event_id"])


def _has_following_resolution(episode: Episode, event: Event) -> bool:
    """Flag a likely resolved beat without rejecting it on text alone."""
    try:
        index = episode.events.index(event)
    except ValueError:
        return False
    if index >= len(episode.events) - 1:
        return False
    text = event.text.strip()
    unresolved = text.endswith(("?", "—", "...", "…"))
    following = episode.events[index + 1]
    return not unresolved and following.t >= event.t and following.type in {
        "action", "camera", "dialogue"
    }


def _resolve_segments(
    candidate: dict,
    episodes: Episode | list[Episode] | dict[int, Episode],
) -> tuple[Optional[list[dict]], Optional[str], dict[int, list[Event]]]:
    episode_lookup = _episode_map(episodes)
    default_episode = next(iter(episode_lookup), 0)
    raw_segments = candidate.get("segments") or []
    if not isinstance(raw_segments, list):
        return None, "segments_not_a_list", {}

    resolved: list[dict] = []
    selected_events: dict[int, list[Event]] = {}
    for raw_segment in raw_segments:
        if not isinstance(raw_segment, dict):
            return None, "segment_not_an_object", {}
        episode_number = _coerce_episode(raw_segment.get("episode"), default_episode)
        start_id = _coerce_event_id(raw_segment.get("start_event_id"))
        end_id = _coerce_event_id(raw_segment.get("end_event_id"))
        episode = episode_lookup.get(episode_number) if episode_number is not None else None
        if episode is None or start_id is None or end_id is None:
            return None, "unknown_event_id", {}
        if start_id > end_id:
            return None, "segment_reversed", {}

        start_event = _find_event(episode, start_id)
        end_event = _find_event(episode, end_id)
        if start_event is None or end_event is None:
            return None, "unknown_event_id", {}
        if end_event.t_end < start_event.t:
            return None, "segment_negative_duration", {}

        resolved_segment = {
            "episode": episode_number,
            "start_event_id": start_id,
            "end_event_id": end_id,
            "start_s": round(start_event.t, 4),
            "end_s": round(end_event.t_end, 4),
            "start": _display_ts(start_event.t),
            "end": _display_ts(end_event.t_end),
        }
        resolved.append(resolved_segment)
        selected_events.setdefault(episode_number, []).extend(
            event for event in episode.events if start_id <= event.id <= end_id
        )

    return resolved, None, selected_events


def _display_ts(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:05.2f}"


def _check_order(resolved: list[dict]) -> Optional[str]:
    for previous, current in zip(resolved, resolved[1:]):
        if current["episode"] < previous["episode"]:
            return "segments_out_of_episode_order"
        if current["episode"] == previous["episode"]:
            if current["start_s"] < previous["end_s"]:
                return "segments_overlap"
            if current["start_event_id"] <= previous["end_event_id"]:
                return "segments_overlap"
    return None


def validate_candidate(
    candidate: dict,
    episode: Episode | list[Episode] | dict[int, Episode],
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    tolerance: float = 3.0,
    hook_window: float = 3.0,
) -> tuple[Optional[dict], Optional[str]]:
    """Validate one candidate and return a normalised output record."""
    raw_segments = candidate.get("segments") or []
    if not raw_segments:
        return None, "no_segments"
    if len(raw_segments) > 3:
        return None, "too_many_segments"

    resolved, reason, selected_events = _resolve_segments(candidate, episode)
    if reason or resolved is None:
        return None, reason or "segment_resolution_failed"
    reason = _check_order(resolved)
    if reason:
        return None, reason

    total_duration = sum(
        segment["end_s"] - segment["start_s"] for segment in resolved
    )
    if total_duration < min_duration - tolerance:
        return None, "too_short"
    if total_duration > max_duration + tolerance:
        return None, "too_long"

    episode_lookup = _episode_map(episode)
    first = resolved[0]
    first_events = selected_events.get(first["episode"], [])
    hook_events = [
        event for event in first_events
        if event.t < first["start_s"] + hook_window
    ]
    hook_quote = str(candidate.get("hook_quote") or "").strip()
    if not _event_text_matches(hook_events, hook_quote):
        return None, "hook_quote_unverified"

    last = resolved[-1]
    last_events = selected_events.get(last["episode"], [])
    cliff_quote = str(candidate.get("cliffhanger_quote") or "").strip()
    if not _event_text_matches(last_events[-3:], cliff_quote):
        return None, "cliffhanger_quote_unverified"

    flags: list[str] = []
    if total_duration < min_duration or total_duration > max_duration:
        flags.append("borderline_duration")

    last_episode = episode_lookup[last["episode"]]
    last_event = _last_event(last_episode, last)
    if last_event and _has_following_resolution(last_episode, last_event):
        flags.append("possible_resolution_after_clip")

    if any(
        event.t_end_estimated
        for events in selected_events.values()
        for event in events
    ):
        flags.append("estimated_event_end")

    sub_scores = candidate.get("sub_scores") or {}
    candidate_id = str(candidate.get("candidate_id") or "candidate_unknown")
    validated = {
        "candidate_id": candidate_id,
        "promo_id": candidate_id,
        "segments": resolved,
        "duration_s": round(total_duration, 1),
        "hook": candidate.get("hook_description") or candidate.get("hook", ""),
        "hook_quote": hook_quote,
        "cliffhanger": candidate.get("cliffhanger_description") or candidate.get("cliffhanger", ""),
        "cliffhanger_quote": cliff_quote,
        "why_it_works": candidate.get("why_it_works", ""),
        "sub_scores": {
            key: _score_value(sub_scores.get(key, 3))
            for key in ("hook", "cliffhanger", "standalone", "pace")
        },
        "needs_context": bool(candidate.get("needs_context", False)),
        "spoiler_risk": _risk_value(candidate.get("spoiler_risk", "low")),
        "visual_risk": _risk_value(candidate.get("visual_risk", "low")),
        "confidence": _score_value(candidate.get("confidence", 3)),
        "flags": flags,
        "hook_verified": True,
        "cliffhanger_verified": True,
    }
    return validated, None


def _score_value(value) -> int:
    try:
        return max(1, min(5, int(value)))
    except (TypeError, ValueError):
        return 3


def _risk_value(value) -> str:
    value = str(value or "low").lower()
    return value if value in {"low", "med", "high"} else "med"


def repair_candidate(
    candidate: dict,
    episode: Episode | list[Episode] | dict[int, Episode],
    reason: str,
) -> dict:
    """Ask the configured model for a corrected version of one candidate."""
    from .llm import generate_json

    import json as _json

    episode_lookup = _episode_map(episode)
    excerpts = "\n\n".join(
        render_compact(item) for item in episode_lookup.values()
    )
    candidate_json = _json.dumps(candidate, indent=2, default=str)
    prompt = f"""You are repairing one promo candidate against the screenplay below.
The deterministic validator rejected the candidate for: {reason}.
Return the same candidate JSON shape, using ONLY real event IDs and exact quote text.
Keep 1-3 segments, 20-60 seconds total, with the hook in the first 3 seconds and
an unresolved cliffhanger at the end. Do not explain the repair; return JSON only.

CANDIDATE:
{candidate_json}

SCREENPLAY:
{excerpts}
"""
    return generate_json(prompt, {"type": "object"}, stage="repair")


RepairFunction = Callable[[dict, Episode | list[Episode] | dict[int, Episode], str], dict]


def validate_all(
    stage1_results: list[dict],
    episodes: list[Episode],
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    tolerance: float = 3.0,
    hook_window: float = 3.0,
    repair_fn: RepairFunction | None = None,
) -> tuple[list[dict], ValidationReport]:
    """Validate Stage 1 candidates, optionally giving each failure one repair call."""
    report = ValidationReport()
    validated: list[dict] = []
    episode_lookup = {episode.episode: episode for episode in episodes}

    for result in stage1_results:
        result_episode = _coerce_episode(result.get("episode"), 0)
        episode = episode_lookup.get(result_episode or 0)
        for raw_candidate in result.get("candidates", []) or []:
            report.total_raw += 1
            candidate_episode = episode
            if candidate_episode is None:
                segment_episode = (raw_candidate.get("segments") or [{}])[0].get("episode")
                candidate_episode = episode_lookup.get(_coerce_episode(segment_episode, 0) or 0)
            if candidate_episode is None:
                report.dropped += 1
                _count(report.drop_reasons, "unknown_episode")
                continue

            valid, reason = validate_candidate(
                raw_candidate,
                candidate_episode,
                min_duration=min_duration,
                max_duration=max_duration,
                tolerance=tolerance,
                hook_window=hook_window,
            )
            if valid is not None:
                report.valid_first_pass += 1
                validated.append(valid)
                continue

            if repair_fn is not None:
                try:
                    repaired_raw = repair_fn(raw_candidate, candidate_episode, reason or "invalid")
                    repaired, repair_reason = validate_candidate(
                        repaired_raw,
                        candidate_episode,
                        min_duration=min_duration,
                        max_duration=max_duration,
                        tolerance=tolerance,
                        hook_window=hook_window,
                    )
                except Exception as exc:
                    repaired = None
                    repair_reason = f"repair_error:{type(exc).__name__}"
                if repaired is not None:
                    repaired["flags"].append("repaired")
                    report.repaired += 1
                    _count(report.repair_reasons, reason or "invalid")
                    validated.append(repaired)
                    continue
                reason = f"{reason or 'invalid'};repair_failed:{repair_reason or 'invalid'}"

            report.dropped += 1
            _count(report.drop_reasons, reason or "invalid")

    return validated, report


def validate_stage2_combos(
    stage2_result: dict,
    episodes: list[Episode],
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    tolerance: float = 3.0,
    hook_window: float = 3.0,
) -> tuple[list[dict], dict[str, int]]:
    """Validate cross-episode combos returned by Stage 2."""
    episode_lookup = {episode.episode: episode for episode in episodes}
    valid: list[dict] = []
    dropped: dict[str, int] = {}
    for combo in stage2_result.get("cross_episode_combos", []) or []:
        candidate, reason = validate_candidate(
            combo,
            episode_lookup,
            min_duration=min_duration,
            max_duration=max_duration,
            tolerance=tolerance,
            hook_window=hook_window,
        )
        if candidate is None:
            _count(dropped, reason or "invalid")
        else:
            valid.append(candidate)
    return valid, dropped


def _count(mapping: dict[str, int], key: str):
    mapping[key] = mapping.get(key, 0) + 1

