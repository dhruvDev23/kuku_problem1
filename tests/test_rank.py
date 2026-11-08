from promo_finder.rank import rank_candidates


def _candidate(candidate_id, episode, start):
    return {
        "candidate_id": candidate_id,
        "segments": [{"episode": episode, "start_s": start, "end_s": start + 25}],
        "duration_s": 25,
        "sub_scores": {"hook": 5, "cliffhanger": 5, "standalone": 4, "pace": 4},
        "spoiler_risk": "low",
        "visual_risk": "low",
        "needs_context": False,
        "flags": [],
    }


def test_rank_is_deterministic_without_rerank():
    config = {
        "scoring": {
            "w_hook": .25, "w_cliffhanger": .30, "w_standalone": .20,
            "w_pace": .10, "w_heuristics": .15,
            "penalty_spoiler_high": .3, "penalty_spoiler_med": .15,
            "penalty_needs_context": .2, "penalty_visual_risk_high": .15,
            "penalty_visual_risk_med": .05, "penalty_borderline_duration": .05,
        },
        "ranking": {"max_per_episode_in_top10": 2, "rerank_top_n": 20, "rerank_blend_weight": .3, "top_n_rationale": 10},
        "diversity": {"max_overlap_s": 5},
    }
    candidates = [_candidate("b", 2, 0), _candidate("a", 1, 0)]
    ranked = rank_candidates(candidates, {"a": 4, "b": 4}, config=config, rerank=False)
    assert [candidate["rank"] for candidate in ranked] == [1, 2]
    assert ranked[0]["candidate_id"] == "a"
