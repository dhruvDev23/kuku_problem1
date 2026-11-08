# ──────────────────────────────────────────────────────────
# promo_finder/features.py – Heuristic feature signals
# ──────────────────────────────────────────────────────────
"""
Cheap, deterministic signals computed from the clip text.
These blend with LLM sub-scores and serve as sanity checks.
"""

from __future__ import annotations

import re
from .parse import Episode, Event

# Action verbs that suggest visual drama
_ACTION_VERBS = {
    "slap", "slaps", "slapped", "grab", "grabs", "grabbed",
    "punch", "punches", "punched", "kick", "kicks", "kicked",
    "push", "pushes", "pushed", "shove", "shoves", "shoved",
    "run", "runs", "crash", "crashes", "scream", "screams",
    "throw", "throws", "threw", "hit", "hits", "strike", "strikes",
    "stab", "stabs", "shoot", "shoots", "fire", "fires",
    "collapse", "collapses", "fall", "falls", "slam", "slams",
    "gasp", "gasps", "cry", "cries", "sob", "sobs",
    "storm", "storms", "burst", "bursts", "rip", "rips",
    "drag", "drags", "yank", "yanks", "clutch", "clutches",
    "strangle", "strangles", "choke", "chokes", "wrestle", "wrestles",
}

# Cliffhanger indicators
_CLIFFHANGER_PATTERNS = [
    re.compile(r"\?$"),          # ends with question mark
    re.compile(r"—$"),           # em dash (interruption)
    re.compile(r"\.\.\.$"),      # ellipsis
    re.compile(r"\.\.\.\"?$"),   # ellipsis possibly in quotes
]


def compute_features(
    candidate: dict,
    episode: Episode,
) -> dict:
    """
    Compute heuristic features for a validated candidate.

    Returns a dict of feature values.
    """
    events = episode.events

    # Gather all events within the candidate segments
    clip_events: list[Event] = []
    first_3s_events: list[Event] = []

    for seg in candidate["segments"]:
        start_id = seg["start_event_id"]
        end_id = seg["end_event_id"]
        seg_start = seg["start_s"]

        for e in events:
            if start_id <= e.id <= end_id:
                clip_events.append(e)
                if e.t < seg_start + 3.0:
                    first_3s_events.append(e)

    if not clip_events:
        return _empty_features()

    duration = candidate.get("duration_s", 1.0)

    # ── Feature 1: Action verbs in first 3 seconds ──
    first_3s_text = " ".join(e.text.lower() for e in first_3s_events)
    first_3s_words = set(re.findall(r"\w+", first_3s_text))
    action_verb_count = len(first_3s_words & _ACTION_VERBS)

    # ── Feature 2: ALL-CAPS stage directions in first 3s ──
    caps_actions = sum(
        1 for e in first_3s_events
        if e.type in ("action", "camera") and any(
            w.isupper() and len(w) > 2
            for w in e.text.split()
        )
    )

    # ── Feature 3: Pace (events per 10 seconds) ──
    events_per_10s = len(clip_events) / max(duration, 1.0) * 10.0

    # ── Feature 4: Longest single-speaker run (monologue penalty) ──
    max_speaker_run = 0
    current_run = 0
    current_speaker = None
    for e in clip_events:
        if e.type == "dialogue":
            if e.speaker == current_speaker:
                current_run += 1
            else:
                current_speaker = e.speaker
                current_run = 1
            max_speaker_run = max(max_speaker_run, current_run)

    # ── Feature 5: Cliffhanger text patterns ──
    last_event = clip_events[-1] if clip_events else None
    cliffhanger_pattern_match = False
    if last_event:
        for pat in _CLIFFHANGER_PATTERNS:
            if pat.search(last_event.text):
                cliffhanger_pattern_match = True
                break

    # ── Feature 6: Named characters without introduction ──
    # Speakers are a conservative proxy because screenplay text has no
    # reliable way to identify whether a character was visually introduced.
    speakers_in_clip = set(
        e.speaker for e in clip_events
        if e.type == "dialogue" and e.speaker
    )
    first_speaker_index: dict[str, int] = {}
    for index, event in enumerate(clip_events):
        if event.type == "dialogue" and event.speaker:
            first_speaker_index.setdefault(event.speaker, index)
    unintroduced_speakers = sum(
        1 for index in first_speaker_index.values() if index > 0
    )

    # ── Feature 7: First 3-second density ──
    first_3s_density = len(first_3s_events) / max(min(3.0, duration), 0.1)

    # ── Feature 8: Dialogue vs non-dialogue ratio ──
    n_dialogue = sum(1 for e in clip_events if e.type == "dialogue")
    dialogue_ratio = n_dialogue / max(len(clip_events), 1)
    last_text = last_event.text.strip() if last_event else ""
    unfinished_beat = bool(last_text.endswith(("?", "—", "...", "…")))

    return {
        "action_verbs_first_3s": action_verb_count,
        "caps_actions_first_3s": caps_actions,
        "events_per_10s": round(events_per_10s, 2),
        "max_speaker_run": max_speaker_run,
        "monologue_penalty": max(0, max_speaker_run - 3),  # penalty if > 3 consecutive
        "cliffhanger_pattern_match": cliffhanger_pattern_match,
        "n_speakers": len(speakers_in_clip),
        "unintroduced_speakers": unintroduced_speakers,
        "first_3s_density": round(first_3s_density, 2),
        "first_3s_event_count": len(first_3s_events),
        "unfinished_beat": unfinished_beat,
        "dialogue_ratio": round(dialogue_ratio, 2),
    }


def _empty_features() -> dict:
    return {
        "action_verbs_first_3s": 0,
        "caps_actions_first_3s": 0,
        "events_per_10s": 0,
        "max_speaker_run": 0,
        "monologue_penalty": 0,
        "cliffhanger_pattern_match": False,
        "n_speakers": 0,
        "unintroduced_speakers": 0,
        "first_3s_density": 0,
        "first_3s_event_count": 0,
        "unfinished_beat": False,
        "dialogue_ratio": 0,
    }


def heuristic_score(features: dict) -> float:
    """
    Compute a single heuristic score 0-5 from the features.
    Used to blend with LLM sub-scores.
    """
    score = 2.5  # baseline

    # Action verbs in first 3s boost
    score += min(features.get("action_verbs_first_3s", 0), 3) * 0.3

    # Pace boost (more events = faster pace = better for short-form)
    pace = features.get("events_per_10s", 0)
    if pace > 5:
        score += 0.5
    elif pace > 3:
        score += 0.2

    # Monologue penalty
    score -= features.get("monologue_penalty", 0) * 0.3

    # Cliffhanger pattern match boost
    if features.get("cliffhanger_pattern_match", False):
        score += 0.4

    if features.get("unfinished_beat", False):
        score += 0.25

    score -= min(features.get("unintroduced_speakers", 0), 3) * 0.12

    # First 3s density boost
    density = features.get("first_3s_density", 0)
    if density > 2:
        score += 0.3

    return max(0.0, min(5.0, score))

