# tests/test_parse.py
"""Unit tests for the screenplay parser."""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from promo_finder.parse import parse_folder, parse_ts, fmt_ts

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "show")

_need_data = pytest.mark.skipif(
    not os.path.isdir(DATA_DIR), reason=f"data dir not found at {DATA_DIR}"
)


def test_parse_ts():
    assert parse_ts("00:00.00") == 0.0
    assert parse_ts("01:30.50") == 90.5
    assert parse_ts("02:18.00") == 138.0


def test_fmt_ts_roundtrip():
    for val in [0.0, 41.5, 90.0, 138.0]:
        assert abs(parse_ts(fmt_ts(val)) - val) < 0.01


@_need_data
def test_all_episodes_parse():
    episodes = parse_folder(DATA_DIR)
    assert len(episodes) == 50, f"Expected 50 episodes, got {len(episodes)}"

    for ep in episodes:
        # Every episode has at least some events
        assert len(ep.events) > 0, f"Ep {ep.episode}: no events"
        # Episode number > 0
        assert ep.episode > 0, f"Ep number is {ep.episode}"
        # At least one scene
        assert len(ep.scenes) > 0, f"Ep {ep.episode}: no scenes"
        # Duration > 0
        assert ep.duration_s > 0, f"Ep {ep.episode}: zero duration"

        # Timestamps are roughly monotonic (allow small overlaps for
        # concurrent camera + dialogue events)
        prev_t = -1.0
        for ev in ep.events:
            assert ev.t >= prev_t - 1.0, (
                f"Ep {ep.episode} event #{ev.id}: t={ev.t:.2f} < prev={prev_t:.2f}"
            )
            prev_t = ev.t

        # No event longer than 60s (sanity)
        for ev in ep.events:
            dur = ev.t_end - ev.t
            assert dur <= 60, (
                f"Ep {ep.episode} event #{ev.id}: {dur:.1f}s too long"
            )
            assert dur >= 0, (
                f"Ep {ep.episode} event #{ev.id}: negative duration {dur:.1f}s"
            )


@_need_data
def test_compact_view():
    from promo_finder.parse import render_compact
    episodes = parse_folder(DATA_DIR)
    for ep in episodes[:3]:
        view = render_compact(ep)
        assert f"EPISODE {ep.episode}" in view
        assert "#0]" in view  # first event id


if __name__ == "__main__":
    test_parse_ts()
    print("✓ test_parse_ts")
    test_fmt_ts_roundtrip()
    print("✓ test_fmt_ts_roundtrip")
    test_all_episodes_parse()
    print("✓ test_all_episodes_parse")
    test_compact_view()
    print("✓ test_compact_view")
    print("\nAll tests passed!")

