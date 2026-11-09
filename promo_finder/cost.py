# ──────────────────────────────────────────────────────────
# promo_finder/cost.py – Token and cost logging
# ──────────────────────────────────────────────────────────
"""
Logs prompt/completion tokens and estimated cost per LLM call.
Writes a running log to cost_log.jsonl and provides a summary.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

# Approximate pricing per 1M tokens (USD) — free tier = 0
_PRICING = {
    "gemini-3.8-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "qwen/qwen3.8-27b": {"input": 0.0, "output": 0.0},
    "llama-3.3-70b-versatile": {"input": 0.0, "output": 0.0},
    "llama-3.1-8b-instant": {"input": 0.0, "output": 0.0},
    "meta-llama/llama-3.3-70b-instruct:free": {"input": 0.0, "output": 0.0},
    "llama3.2": {"input": 0.0, "output": 0.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.0},
}

_calls: list[dict] = []
_log_file: Path | None = None


def set_log_file(path: str | Path):
    global _log_file
    _log_file = Path(path)
    _log_file.parent.mkdir(parents=True, exist_ok=True)


def reset():
    """Clear accumulated metrics before starting an independent run."""
    global _calls, _log_file
    _calls = []
    _log_file = None


def log_call(
    stage: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
):
    """Record a single LLM call."""
    pricing = _PRICING.get(model, {"input": 0, "output": 0})
    cost = (
        prompt_tokens * pricing["input"] / 1_000_000
        + completion_tokens * pricing["output"] / 1_000_000
    )

    entry = {
        "timestamp": time.time(),
        "stage": stage,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": round(cost, 6),
    }
    _calls.append(entry)

    if _log_file:
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def summary() -> dict:
    """Return a summary of all logged calls."""
    total_prompt = sum(c["prompt_tokens"] for c in _calls)
    total_completion = sum(c["completion_tokens"] for c in _calls)
    total_cost = sum(c["estimated_cost_usd"] for c in _calls)

    by_stage: dict[str, dict] = {}
    for c in _calls:
        s = c["stage"]
        if s not in by_stage:
            by_stage[s] = {"calls": 0, "prompt_tokens": 0,
                           "completion_tokens": 0, "cost_usd": 0.0}
        by_stage[s]["calls"] += 1
        by_stage[s]["prompt_tokens"] += c["prompt_tokens"]
        by_stage[s]["completion_tokens"] += c["completion_tokens"]
        by_stage[s]["cost_usd"] += c["estimated_cost_usd"]

    return {
        "total_calls": len(_calls),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_prompt + total_completion,
        "total_cost_usd": round(total_cost, 4),
        "by_stage": by_stage,
    }

