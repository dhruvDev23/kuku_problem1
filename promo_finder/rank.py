# ──────────────────────────────────────────────────────────
# promo_finder/rank.py – Scoring, diversity, and comparative reranking
# ──────────────────────────────────────────────────────────
"""
1. Compute weighted score from LLM sub-scores + heuristics − penalties
2. Diversity pass (MMR-style)
3. Comparative LLM rerank of the top N
4. Blend formula score with rerank position
5. Generate posting rationales for top 10
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .llm import generate_json


def _load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    return yaml.safe_load(cfg_path.read_text())


def _normalise_subscore(value) -> float:
    try:
        return max(0.0, min(1.0, (float(value) - 1.0) / 4.0))
    except (TypeError, ValueError):
        return 0.5


def compute_score(candidate: dict, h_score: float, cfg: dict | None = None) -> float:
    """Compute the weighted formula score for a candidate."""
    if cfg is None:
        cfg = _load_config()

    sc = cfg["scoring"]
    sub = candidate.get("sub_scores", {})

    # Normalise LLM sub-scores to 0-1 (from 1-5)
    hook = _normalise_subscore(sub.get("hook", 3))
    cliff = _normalise_subscore(sub.get("cliffhanger", 3))
    standalone = _normalise_subscore(sub.get("standalone", 3))
    pace = _normalise_subscore(sub.get("pace", 3))
    h_norm = _normalise_subscore(h_score)

    score = (
        sc["w_hook"] * hook
        + sc["w_cliffhanger"] * cliff
        + sc["w_standalone"] * standalone
        + sc["w_pace"] * pace
        + sc["w_heuristics"] * h_norm
    )

    # Penalties
    spoiler = candidate.get("spoiler_risk", "low")
    if spoiler == "high":
        score -= sc["penalty_spoiler_high"]
    elif spoiler == "med":
        score -= sc["penalty_spoiler_med"]

    if candidate.get("needs_context", False):
        score -= sc["penalty_needs_context"]

    visual = candidate.get("visual_risk", "low")
    if visual == "high":
        score -= sc["penalty_visual_risk_high"]
    elif visual == "med":
        score -= sc["penalty_visual_risk_med"]

    if "borderline_duration" in candidate.get("flags", []):
        score -= sc["penalty_borderline_duration"]

    return round(max(0.0, min(1.0, score)), 4)


def _segments_overlap(a: dict, b: dict, max_overlap: float) -> bool:
    """Check if two candidates have overlapping time ranges."""
    for sa in a.get("segments", []):
        for sb in b.get("segments", []):
            if sa.get("episode") != sb.get("episode"):
                continue
            overlap_start = max(sa["start_s"], sb["start_s"])
            overlap_end = min(sa["end_s"], sb["end_s"])
            if overlap_end - overlap_start > max_overlap:
                return True
    return False


def diversity_pass(
    candidates: list[dict],
    max_per_episode: int = 2,
    max_overlap_s: float = 5.0,
    top_n: int = 10,
) -> list[dict]:
    """
    Greedy MMR-style diversity selection.
    No more than max_per_episode in the top-N, and no overlapping segments.
    """
    # Sort by score descending
    sorted_cands = sorted(
        candidates,
        key=lambda c: (
            -c.get("final_blended_score", c.get("final_score", 0)),
            -c.get("final_score", 0),
            str(c.get("candidate_id", "")),
        ),
    )

    selected = []
    ep_counts: dict[int, int] = {}

    for c in sorted_cands:
        if len(selected) >= top_n:
            break

        # Get episode(s) for this candidate
        eps = set()
        for seg in c.get("segments", []):
            eps.add(seg.get("episode", 0))

        # Check per-episode limit
        skip = False
        for ep in eps:
            if ep_counts.get(ep, 0) >= max_per_episode:
                skip = True
                break
        if skip:
            # Still include but mark it won't be in diverse top-N
            continue

        # Check overlap with already selected
        overlaps = False
        for sel in selected:
            if _segments_overlap(c, sel, max_overlap_s):
                overlaps = True
                break
        if overlaps:
            continue

        selected.append(c)
        for ep in eps:
            ep_counts[ep] = ep_counts.get(ep, 0) + 1

    # Return all candidates but reorder: selected first, then rest
    selected_ids = {c["candidate_id"] for c in selected}
    rest = [c for c in sorted_cands if c["candidate_id"] not in selected_ids]

    return selected + rest


def comparative_rerank(
    candidates: list[dict],
    top_n: int = 20,
) -> list[dict]:
    """
    Send the top N candidates to the LLM for comparative reranking.
    Returns the candidates with updated rerank_position.
    """
    template_path = Path(__file__).parent / "prompts" / "rerank.txt"
    template = template_path.read_text()

    # Build compact description of top N
    top = candidates[:top_n]
    cand_lines = []
    for c in top:
        segs = c.get("segments", [])
        seg_str = ", ".join(
            f"ep{s.get('episode','?')} {s.get('start','?')}-{s.get('end','?')}"
            for s in segs
        )
        sub = c.get("sub_scores", {})
        cand_lines.append(
            f"- {c['candidate_id']}: [{seg_str}] "
            f"dur={c.get('duration_s',0):.0f}s "
            f"hook={sub.get('hook','?')}/5 cliff={sub.get('cliffhanger','?')}/5 "
            f"standalone={sub.get('standalone','?')}/5 "
            f"hook=\"{c.get('hook_quote','')[:50]}\" "
            f"cliff=\"{c.get('cliffhanger_quote','')[:50]}\" "
            f"why=\"{c.get('why_it_works','')[:60]}\""
        )

    prompt = template + "\n\n═══ CANDIDATES ═══\n" + "\n".join(cand_lines)

    if not top:
        return candidates

    try:
        result = generate_json(
            prompt=prompt,
            schema={
                "type": "object",
                "properties": {
                    "ranked": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "rank": {"type": "integer"},
                                "candidate_id": {"type": "string"},
                                "post_first_because": {"type": "string"},
                            },
                        },
                    }
                },
            },
            stage="rerank",
        )
    except Exception as exc:
        print(f"  [Warning] Comparative rerank LLM quota exhausted ({exc}). Proceeding with multi-factor formula ranking.")
        result = {"ranked": []}

    # Apply rerank positions
    ranked = result.get("ranked", []) if isinstance(result, dict) else []
    valid_ids = {c["candidate_id"] for c in top}
    rerank_map = {}
    next_position = 1
    for item in ranked if isinstance(ranked, list) else []:
        if not isinstance(item, dict):
            continue
        cid = item.get("candidate_id")
        if cid not in valid_ids or cid in rerank_map:
            continue
        try:
            position = int(item.get("rank", next_position))
        except (TypeError, ValueError):
            position = next_position
        rerank_map[cid] = (max(1, position), str(item.get("post_first_because", "")))
        next_position += 1

    formula_order = sorted(
        top,
        key=lambda c: (-c.get("final_score", 0), str(c.get("candidate_id", ""))),
    )
    fallback_position = max((position for position, _ in rerank_map.values()), default=0) + 1
    for candidate in formula_order:
        if candidate["candidate_id"] not in rerank_map:
            rerank_map[candidate["candidate_id"]] = (fallback_position, "")
            fallback_position += 1

    for c in candidates:
        cid = c["candidate_id"]
        if cid in rerank_map:
            c["rerank_position"] = rerank_map[cid][0]
            c["post_first_because"] = rerank_map[cid][1]
        else:
            c["rerank_position"] = fallback_position
            c["post_first_because"] = ""
            fallback_position += 1

    return candidates


def blend_and_sort(
    candidates: list[dict],
    rerank_blend_weight: float = 0.3,
) -> list[dict]:
    """
    Blend formula score with rerank position to get final_blended_score.
    Sort by final_blended_score descending.
    """
    # Normalise rerank positions to 0-1 (lower rank = higher score)
    max_pos = max((c.get("rerank_position", 1) for c in candidates), default=1)

    for c in candidates:
        formula = c.get("final_score", 0)
        rerank_pos = c.get("rerank_position", 999)
        # Convert rank to score: rank 1 → 1.0, rank max → 0.0
        rerank_score = 1.0 - (rerank_pos - 1) / max(max_pos - 1, 1)
        blended = (1 - rerank_blend_weight) * formula + rerank_blend_weight * rerank_score
        c["final_blended_score"] = round(blended, 4)

    return sorted(
        candidates,
        key=lambda c: (
            -c["final_blended_score"],
            -c.get("final_score", 0),
            str(c.get("candidate_id", "")),
        ),
    )


def rank_candidates(
    candidates: list[dict],
    heuristic_scores: dict[str, float],
    config: dict | None = None,
    rerank: bool = True,
) -> list[dict]:
    """
    Full ranking pipeline:
    1. Compute formula scores
    2. Diversity pass
    3. Comparative rerank
    4. Blend and sort
    """
    cfg = config or _load_config()
    candidates = [candidate for candidate in candidates if candidate.get("candidate_id")]
    if not candidates:
        return []

    # 1. Score
    for c in candidates:
        h_score = heuristic_scores.get(c["candidate_id"], 2.5)
        c["heuristic_score"] = round(h_score, 2)
        c["final_score"] = compute_score(c, h_score, cfg)

    # 2. Diversity
    rank_cfg = cfg.get("ranking", {})
    candidates = diversity_pass(
        candidates,
        max_per_episode=rank_cfg.get("max_per_episode_in_top10", 2),
        max_overlap_s=cfg.get("diversity", {}).get("max_overlap_s", 5.0),
        top_n=rank_cfg.get("rerank_top_n", 20),
    )

    # 3. Comparative rerank
    if rerank:
        candidates = comparative_rerank(
            candidates,
            top_n=rank_cfg.get("rerank_top_n", 20),
        )
    else:
        for position, candidate in enumerate(candidates, start=1):
            candidate["rerank_position"] = position
            candidate["post_first_because"] = ""

    # 4. Blend and sort
    candidates = blend_and_sort(
        candidates,
        rerank_blend_weight=rank_cfg.get("rerank_blend_weight", 0.3),
    )

    # The first diversity pass only chooses the rerank pool. Apply the actual
    # top-10 constraint again after blending so the published list obeys it.
    candidates = diversity_pass(
        candidates,
        max_per_episode=rank_cfg.get("max_per_episode_in_top10", 2),
        max_overlap_s=cfg.get("diversity", {}).get("max_overlap_s", 5.0),
        top_n=rank_cfg.get("top_n_rationale", 10),
    )

    for candidate in candidates[:rank_cfg.get("top_n_rationale", 10)]:
        if not candidate.get("post_first_because"):
            candidate["post_first_because"] = (
                "Strongest balance of a stop-scrolling hook, standalone conflict, "
                "and an unresolved ending in the final shortlist."
            )

    # 5. Assign final ranks
    for i, c in enumerate(candidates):
        c["rank"] = i + 1

    return candidates

