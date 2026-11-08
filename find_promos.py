#!/usr/bin/env python3
"""Command-line entry point for the Microdrama Promo Finder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from promo_finder.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find validated 20–60 second promos in screenplay episodes."
    )
    parser.add_argument("folder", help="Folder containing episode-*.txt files")
    parser.add_argument("--run-id", default=None, help="Output run identifier")
    parser.add_argument(
        "--context",
        action="store_true",
        help="Pass the previous two episode summaries to Stage 1",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory for outputs/<run_id> (default: outputs)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="YAML config path (default: this project's config.yaml)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the deterministic local baseline; no API key or LLM calls",
    )
    parser.add_argument(
        "--no-repair",
        action="store_true",
        help="Drop invalid candidates instead of making repair calls",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def print_log(message: str):
        print(message, flush=True)

    try:
        result = run_pipeline(
            args.folder,
            run_id=args.run_id,
            output_dir=args.output_dir,
            config_path=args.config,
            use_context=args.context,
            offline=args.offline,
            repair_invalid=not args.no_repair,
            log_callback=print_log,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("\nRUN COMPLETE")
    print(f"Episodes: {result['episodes']}")
    print(f"Raw candidates: {result['raw_candidates']}")
    print(f"Valid candidates: {result['valid_candidates']}")
    print(f"Ranked candidates: {result['ranked_candidates']}")
    print(f"Output: {Path(result['output_path']).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

