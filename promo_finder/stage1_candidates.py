# ──────────────────────────────────────────────────────────
# promo_finder/stage1_candidates.py – Per-episode candidate extraction
# ──────────────────────────────────────────────────────────
"""
For each episode, send the compact screenplay to the LLM and extract
4-6 promo candidates with hooks, cliffhangers, and sub-scores.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .parse import Episode, render_compact
from .llm import generate_json


STAGE1_SCHEMA = {
    "type": "object",
    "required": ["episode", "episode_summary", "candidates"],
    "properties": {
        "episode": {"type": "integer"},
        "episode_summary": {"type": "string"},
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                },
            },
        },
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string"},
                    "segments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start_event_id": {"type": "integer"},
                                "end_event_id": {"type": "integer"},
                            },
                        },
                    },
                    "hook_quote": {"type": "string"},
                    "hook_description": {"type": "string"},
                    "cliffhanger_quote": {"type": "string"},
                    "cliffhanger_description": {"type": "string"},
                    "why_it_works": {"type": "string"},
                    "sub_scores": {
                        "type": "object",
                        "properties": {
                            "hook": {"type": "integer"},
                            "cliffhanger": {"type": "integer"},
                            "standalone": {"type": "integer"},
                            "pace": {"type": "integer"},
                        },
                    },
                    "needs_context": {"type": "boolean"},
                    "spoiler_risk": {"type": "string"},
                    "visual_risk": {"type": "string"},
                    "confidence": {"type": "integer"},
                },
            },
        },
    },
}


def _load_prompt_template() -> str:
    p = Path(__file__).parent / "prompts" / "stage1.txt"
    return p.read_text()


def extract_candidates(
    episode: Episode,
    prev_summaries: Optional[list[str]] = None,
) -> dict:
    """
    Extract promo candidates from a single episode.

    Args:
        episode: Parsed Episode object.
        prev_summaries: Optional list of previous episode summaries for context.

    Returns:
        Raw JSON dict from the LLM with candidates.
    """
    template = _load_prompt_template()
    compact = render_compact(episode)

    prompt_parts = [template, "\n═══ EPISODE SCREENPLAY ═══\n", compact]

    if prev_summaries:
        ctx = "\n".join(
            f"  Episode {i+1}: {s}" for i, s in enumerate(prev_summaries)
        )
        prompt_parts.insert(
            1,
            f"\n═══ PREVIOUS EPISODE CONTEXT ═══\n{ctx}\n"
        )

    prompt = "\n".join(prompt_parts)

    result = generate_json(
        prompt=prompt,
        schema=STAGE1_SCHEMA,
        stage="stage1",
    )

    if not isinstance(result, dict):
        raise ValueError(f"Stage 1 returned {type(result).__name__}, expected object")
    result.setdefault("episode", episode.episode)
    result.setdefault("candidates", [])

    return result


def _offline_candidates(episode: Episode) -> dict:
    """Create transparent, deterministic candidates for local smoke tests.

    This is intentionally not a substitute for the LLM editor. It selects
    screenplay windows only, keeps exact event IDs and quotes, and is useful
    when reviewing the pipeline without an API key.
    """
    candidates = []
    minimum = 20.0
    maximum = 60.0
    for start_index, start_event in enumerate(episode.events):
        if len(candidates) >= 5:
            break
        end_event = None
        for event in episode.events[start_index:]:
            duration = event.t_end - start_event.t
            if duration >= minimum:
                end_event = event
                if duration <= maximum:
                    break
        if end_event is None:
            continue
        duration = end_event.t_end - start_event.t
        if duration > maximum + 3:
            continue
        candidate_id = f"ep{episode.episode:02d}_offline_{len(candidates) + 1:02d}"
        candidates.append({
            "candidate_id": candidate_id,
            "segments": [{
                "start_event_id": start_event.id,
                "end_event_id": end_event.id,
            }],
            "hook_quote": start_event.text,
            "hook_description": "The opening screenplay beat creates immediate context.",
            "cliffhanger_quote": end_event.text,
            "cliffhanger_description": "The window ends at the selected final screenplay beat.",
            "why_it_works": "Deterministic baseline window for pipeline verification.",
            "sub_scores": {"hook": 3, "cliffhanger": 3, "standalone": 3, "pace": 3},
            "needs_context": False,
            "spoiler_risk": "med",
            "visual_risk": "high",
            "confidence": 2,
        })
    return {
        "episode": episode.episode,
        "episode_summary": episode.logline[:400],
        "characters": [],
        "candidates": candidates,
    }


def is_episode_cached(episode: Episode, prev_summaries: Optional[list[str]] = None) -> bool:
    try:
        from promo_finder.llm import is_cached, get_model_name
        template = _load_prompt_template()
        compact = render_compact(episode)
        prompt_parts = [template, "\n═══ EPISODE SCREENPLAY ═══\n", compact]
        if prev_summaries:
            ctx = "\n".join(
                f"  Episode {i+1}: {s}" for i, s in enumerate(prev_summaries)
            )
            prompt_parts.insert(1, f"\n═══ PREVIOUS EPISODE CONTEXT ═══\n{ctx}\n")
        prompt = "\n".join(prompt_parts)
        model = get_model_name("stage1")
        return is_cached(prompt, model, STAGE1_SCHEMA, stage="stage1")
    except Exception:
        return False


def run_stage1(
    episodes: list[Episode],
    use_context: bool = False,
    offline: bool = False,
    log_callback: Optional[Callable[[str], None]] = None,
) -> list[dict]:
    """Run Stage 1, or a deterministic local baseline when offline is true."""
    if offline:
        return [_offline_candidates(episode) for episode in episodes]

    results = []
    summaries: list[str] = []
    for i, ep in enumerate(episodes):
        prev = summaries[-2:] if use_context and summaries else None
        cached_flag = is_episode_cached(ep, prev_summaries=prev)
        status_suffix = " [Loaded from disk cache]" if cached_flag else ""
        msg = f"Phase 2: Stage 1 extracting episode {ep.episode} ({i+1}/{len(episodes)})...{status_suffix}"
        if log_callback:
            log_callback(msg)
        print(f"  Stage 1: Episode {ep.episode} ({i+1}/{len(episodes)})...{status_suffix}", flush=True)
        result = extract_candidates(ep, prev_summaries=prev)
        results.append(result)
        summaries.append(str(result.get("episode_summary", "")))
    return results

