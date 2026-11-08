# ──────────────────────────────────────────────────────────
# promo_finder/stage2_select.py – Global selection & cross-episode combos
# ──────────────────────────────────────────────────────────
"""
Takes all validated per-episode candidates + episode summaries,
and calls the LLM to:
  - Remove near-duplicates
  - Propose cross-episode combo promos
  - Flag spoilers
"""

from __future__ import annotations

from pathlib import Path

from .parse import Episode
from .llm import generate_json


STAGE2_SCHEMA = {
    "type": "object",
    "required": ["duplicates_removed", "spoiler_flags", "cross_episode_combos"],
    "properties": {
        "duplicates_removed": {"type": "array"},
        "spoiler_flags": {"type": "array"},
        "cross_episode_combos": {"type": "array"},
    },
}


def _load_prompt_template() -> str:
    p = Path(__file__).parent / "prompts" / "stage2.txt"
    return p.read_text()


def run_stage2(
    candidates: list[dict],
    episodes: list[Episode],
    stage1_results: list[dict],
) -> dict:
    """
    Run Stage 2: global selection across all episodes.

    Args:
        candidates: All validated candidates from Stage 1.
        episodes: All parsed episodes.
        stage1_results: Raw Stage 1 results (for episode summaries).

    Returns:
        Stage 2 result dict with duplicates_removed, spoiler_flags,
        and cross_episode_combos.
    """
    template = _load_prompt_template()

    # Build episode summaries section
    summaries = []
    for index, r in enumerate(stage1_results, start=1):
        ep_num = r.get("episode", index)
        summary = r.get("episode_summary", "No summary")
        summaries.append(f"  Episode {ep_num}: {summary}")

    summaries_text = "\n".join(summaries)

    # Build candidates section (compact)
    cand_lines = []
    for c in candidates:
        segs = c.get("segments", [])
        seg_str = ", ".join(
            f"ep{s.get('episode','?')} #{s.get('start_event_id','?')}-#{s.get('end_event_id','?')} "
            f"({s.get('start','?')}-{s.get('end','?')})"
            for s in segs
        )
        scores = c.get("sub_scores", {})
        cand_lines.append(
            f"  {c.get('candidate_id','?')}: [{seg_str}] "
            f"dur={c.get('duration_s',0):.0f}s "
            f"hook={scores.get('hook','?')}/5 cliff={scores.get('cliffhanger','?')}/5 "
            f"standalone={scores.get('standalone','?')}/5 "
            f"spoiler={c.get('spoiler_risk','?')} "
            f"hook_quote=\"{c.get('hook_quote','')[:60]}\" "
            f"cliff_quote=\"{c.get('cliffhanger_quote','')[:60]}\""
        )

    cand_text = "\n".join(cand_lines)

    prompt = (
        template
        + "\n\n═══ EPISODE SUMMARIES ═══\n"
        + summaries_text
        + "\n\n═══ VALIDATED CANDIDATES ═══\n"
        + cand_text
    )

    result = generate_json(prompt=prompt, schema=STAGE2_SCHEMA, stage="stage2")

    if not isinstance(result, dict):
        raise ValueError(f"Stage 2 returned {type(result).__name__}, expected object")
    result.setdefault("duplicates_removed", [])
    result.setdefault("spoiler_flags", [])
    result.setdefault("cross_episode_combos", [])

    return result

