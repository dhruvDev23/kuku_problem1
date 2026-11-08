# ──────────────────────────────────────────────────────────
# promo_finder/report.py – Output writers
# ──────────────────────────────────────────────────────────
"""
Writes promos.json, promos.csv, ranked_report.md,
validation_report.json, cost_report.json, and run_log.txt
to outputs/<run_id>/.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from .cost import summary as cost_summary


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def write_outputs(
    run_id: str,
    candidates: list[dict],
    validation_report: dict,
    run_log: list[str],
    output_dir: str = "outputs",
    parser_report: dict | None = None,
    stage2_result: dict | None = None,
):
    """Write all output files for a run."""
    out = Path(output_dir) / run_id
    _ensure_dir(out)

    # ── promos.json ──
    (out / "promos.json").write_text(
        json.dumps(candidates, indent=2, default=str), encoding="utf-8"
    )

    # ── promos.csv ──
    fieldnames = [
        "rank", "promo_id", "candidate_id", "duration_s",
        "hook_quote", "cliffhanger_quote", "why_it_works",
        "final_blended_score", "final_score",
        "spoiler_risk", "needs_context", "visual_risk",
        "segments_summary", "flags",
    ]
    with open(out / "promos.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for c in candidates:
            row = dict(c)
            # Flatten segments for CSV
            segs = c.get("segments", [])
            row["segments_summary"] = "; ".join(
                f"ep{s.get('episode','?')} {s.get('start','?')}-{s.get('end','?')}"
                for s in segs
            )
            row["flags"] = ", ".join(c.get("flags", []))
            writer.writerow(row)

    # ── ranked_report.md ──
    md_lines = [
        "# Promo Finder — Ranked Report",
        f"\nRun ID: `{run_id}`",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total candidates ranked: {len(candidates)}\n",
        "---\n",
        "## Top 10 Promos\n",
    ]

    for c in candidates[:10]:
        segs = c.get("segments", [])
        seg_str = " + ".join(
            f"Episode {s.get('episode','?')} [{s.get('start','?')} → {s.get('end','?')}]"
            for s in segs
        )
        sub = c.get("sub_scores", {})
        md_lines.extend([
            f"### #{c.get('rank', '?')}. `{c.get('candidate_id', '?')}`",
            f"**Segments:** {seg_str}",
            f"**Duration:** {c.get('duration_s', 0):.1f}s",
            f"**Score:** {c.get('final_blended_score', 0):.3f} "
            f"(formula: {c.get('final_score', 0):.3f}, rerank: #{c.get('rerank_position', '?')})",
            "",
            f"**🪝 Hook:** {c.get('hook', '')}",
            f"> \"{c.get('hook_quote', '')}\"",
            "",
            f"**🎬 Cliffhanger:** {c.get('cliffhanger', '')}",
            f"> \"{c.get('cliffhanger_quote', '')}\"",
            "",
            f"**Why it works:** {c.get('why_it_works', '')}",
            "",
            f"**Post first because:** {c.get('post_first_because', 'N/A')}",
            "",
            f"Scores — Hook: {sub.get('hook','?')}/5, "
            f"Cliff: {sub.get('cliffhanger','?')}/5, "
            f"Standalone: {sub.get('standalone','?')}/5, "
            f"Pace: {sub.get('pace','?')}/5 | "
            f"Heuristic: {c.get('heuristic_score', '?')}",
            "",
            f"Flags: {', '.join(c.get('flags', [])) or 'none'}",
            f"Spoiler: {c.get('spoiler_risk', '?')} | "
            f"Context needed: {c.get('needs_context', '?')} | "
            f"Visual risk: {c.get('visual_risk', '?')}",
            "",
            "---\n",
        ])

    # Validation summary
    md_lines.extend([
        "\n## Validation Summary\n",
        f"- Total raw candidates: {validation_report.get('total_raw', 0)}",
        f"- Valid on first pass: {validation_report.get('valid_first_pass', 0)} "
        f"({validation_report.get('valid_rate_pct', 0)}%)",
        f"- Repaired: {validation_report.get('repaired', 0)} "
        f"({validation_report.get('repair_rate_pct', 0)}%)",
        f"- Dropped: {validation_report.get('dropped', 0)} "
        f"({validation_report.get('drop_rate_pct', 0)}%)",
        "",
        "**Drop reasons:**",
    ])
    for reason, count in validation_report.get("drop_reasons", {}).items():
        md_lines.append(f"  - {reason}: {count}")

    (out / "ranked_report.md").write_text("\n".join(md_lines), encoding="utf-8")

    # ── validation_report.json ──
    (out / "validation_report.json").write_text(
        json.dumps(validation_report, indent=2), encoding="utf-8"
    )

    # ── cost_report.json ──
    (out / "cost_report.json").write_text(
        json.dumps(cost_summary(), indent=2), encoding="utf-8"
    )

    # ── run_log.txt ──
    (out / "run_log.txt").write_text("\n".join(run_log), encoding="utf-8")

    if parser_report is not None:
        (out / "parse_report.json").write_text(
            json.dumps(parser_report, indent=2), encoding="utf-8"
        )
    if stage2_result is not None:
        (out / "stage2_report.json").write_text(
            json.dumps(stage2_result, indent=2, default=str), encoding="utf-8"
        )

    return str(out)

