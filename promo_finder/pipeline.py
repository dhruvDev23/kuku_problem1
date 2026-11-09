"""Reusable end-to-end pipeline used by the CLI and optional UI."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import yaml

from .cost import reset as reset_cost, set_log_file
from .features import compute_features, heuristic_score
from .llm import configure as configure_llm, reset_runtime_state, set_status_callback
from .parse import parse_folder, parse_report
from .rank import rank_candidates
from .report import write_outputs
from .stage1_candidates import run_stage1
from .stage2_select import run_stage2
from .validate import (
    repair_candidate,
    validate_all,
    validate_stage2_combos,
)


def load_config(config_path: str | Path | None = None) -> tuple[dict, Path]:
    path = Path(config_path or Path(__file__).parent.parent / "config.yaml").resolve()
    return yaml.safe_load(path.read_text(encoding="utf-8")), path


def run_pipeline(
    input_folder: str | Path,
    *,
    run_id: str | None = None,
    output_dir: str | Path = "outputs",
    config_path: str | Path | None = None,
    use_context: bool = False,
    offline: bool = False,
    repair_invalid: bool = False,
    log_callback: Callable[[str], None] | None = None,
    provider: str | None = None,
) -> dict:
    """Run every pipeline phase and write a raw output folder."""
    cfg, cfg_path = load_config(config_path)
    if provider:
        cfg["provider"] = provider
    configure_llm(cfg, cfg_path)
    reset_runtime_state()
    reset_cost()

    run_id = run_id or time.strftime("%Y%m%d_%H%M%S")
    output_root = Path(output_dir)
    run_path = output_root / run_id
    run_path.mkdir(parents=True, exist_ok=True)
    set_log_file(run_path / "cost_log.jsonl")
    run_log: list[str] = []

    def log(message: str):
        stamp = time.strftime("%H:%M:%S")
        entry = f"[{stamp}] {message}"
        run_log.append(entry)
        if log_callback:
            log_callback(entry)

    set_status_callback(log)
    log(f"Promo Finder starting — run_id={run_id}")
    log(f"Input folder: {input_folder}")
    log(f"Config: provider={cfg['provider']}")
    if offline:
        log("Offline baseline enabled; no LLM calls will be made.")

    started = time.time()
    episodes = parse_folder(input_folder)
    parser_report = parse_report(episodes)
    log(f"Phase 1: parsed {len(episodes)} episodes, {parser_report['total_events']} events")
    if parser_report["anomalies"]:
        log(f"Parser anomalies: {len(parser_report['anomalies'])}")
    if not episodes:
        raise ValueError(f"No episode-*.txt files found in {input_folder}")

    stage1_started = time.time()
    stage1_results = run_stage1(
        episodes,
        use_context=use_context,
        offline=offline,
        log_callback=log,
    )
    raw_count = sum(len(result.get("candidates", []) or []) for result in stage1_results)
    log(f"Phase 3: Stage 1 returned {raw_count} raw candidates in {time.time() - stage1_started:.1f}s")

    log("Phase 4: Validating candidates, durations & boundaries...")
    promo_cfg = cfg.get("promo", {})
    validated, validation = validate_all(
        stage1_results,
        episodes,
        min_duration=promo_cfg.get("min_duration_s", 20),
        max_duration=promo_cfg.get("max_duration_s", 60),
        tolerance=promo_cfg.get("duration_tolerance_s", 3),
        hook_window=promo_cfg.get("hook_window_s", 3),
        repair_fn=repair_candidate if repair_invalid and not offline else None,
    )
    validation_dict = validation.to_dict()
    log(
        "Phase 4: valid first pass={valid_first_pass}, repaired={repaired}, "
        "dropped={dropped}".format(**validation_dict)
    )

    if not validated:
        raise ValueError("No valid candidates after deterministic validation and repair.")

    if offline:
        stage2_result = {
            "duplicates_removed": [],
            "spoiler_flags": [],
            "cross_episode_combos": [],
        }
    else:
        log("Phase 5: Stage 2 analyzing global deduplication, plot spoilers & cross-episode combos...")
        stage2_result = run_stage2(validated, episodes, stage1_results)
        log("Phase 5 complete: Stage 2 global analysis finished.")

    duplicate_records = stage2_result.get("duplicates_removed", []) or []
    duplicate_ids = {
        str(item.get("candidate_id"))
        for item in duplicate_records
        if isinstance(item, dict) and item.get("candidate_id") is not None
    }
    validated = [
        candidate for candidate in validated
        if candidate["candidate_id"] not in duplicate_ids
    ]

    spoiler_ids = {
        str(item.get("candidate_id"))
        for item in (stage2_result.get("spoiler_flags", []) or [])
        if isinstance(item, dict) and item.get("candidate_id") is not None
    }
    for candidate in validated:
        if candidate["candidate_id"] in spoiler_ids:
            candidate["spoiler_risk"] = "high"
            candidate.setdefault("flags", []).append("spoiler_flagged_stage2")

    combos, combo_drop_reasons = validate_stage2_combos(
        stage2_result,
        episodes,
        min_duration=promo_cfg.get("min_duration_s", 20),
        max_duration=promo_cfg.get("max_duration_s", 60),
        tolerance=promo_cfg.get("duration_tolerance_s", 3),
        hook_window=promo_cfg.get("hook_window_s", 3),
    )
    existing_ids = {candidate["candidate_id"] for candidate in validated}
    combos = [combo for combo in combos if combo["candidate_id"] not in existing_ids]
    validated.extend(combos)
    validation_dict.update({
        "stage2_duplicates_removed": len(duplicate_records),
        "stage2_combos_raw": len(stage2_result.get("cross_episode_combos", []) or []),
        "stage2_combos_valid": len(combos),
        "stage2_combo_drop_reasons": combo_drop_reasons,
    })
    log(
        f"Phase 6: removed {len(duplicate_records)} duplicates, "
        f"accepted {len(combos)} cross-episode combos"
    )

    episode_lookup = {episode.episode: episode for episode in episodes}
    heuristic_scores: dict[str, float] = {}
    for candidate in validated:
        first_segment = candidate.get("segments", [{}])[0]
        episode = episode_lookup.get(first_segment.get("episode"))
        if episode is None:
            continue
        features = compute_features(candidate, episode)
        candidate["heuristics"] = features
        heuristic_scores[candidate["candidate_id"]] = heuristic_score(features)

    log(f"Phase 7: Ranking & scoring {len(validated)} candidates (MMR diversity & comparative rerank)...")
    ranked = rank_candidates(
        validated,
        heuristic_scores,
        config=cfg,
        rerank=not offline,
    )
    log(f"Phase 7 complete: ranked {len(ranked)} candidates")

    log("Phase 8: Generating output reports, JSON, and CSV files...")
    validation_dict["total_after_stage2"] = len(validated)
    write_outputs(
        run_id=run_id,
        candidates=ranked,
        validation_report=validation_dict,
        run_log=run_log,
        output_dir=output_dir,
        parser_report=parser_report,
        stage2_result=stage2_result,
    )
    log(f"Phase 8: outputs written to {run_path}")
    log(f"Pipeline complete! Completed in {time.time() - started:.1f}s")
    (run_path / "run_log.txt").write_text("\n".join(run_log), encoding="utf-8")

    return {
        "run_id": run_id,
        "output_path": str(run_path),
        "episodes": len(episodes),
        "raw_candidates": raw_count,
        "valid_candidates": len(validated),
        "ranked_candidates": len(ranked),
        "validation_report": validation_dict,
        "ranked": ranked,
    }

