from promo_finder.parse import Episode, Event
from promo_finder.validate import validate_candidate, validate_stage2_combos


def _episode(number=1):
    events = [
        Event(i, i * 5.0, (i + 1) * 5.0, "dialogue", f"CHARACTER {i}", None, f"line {i}", 1)
        for i in range(6)
    ]
    return Episode(number, f"episode-{number:03d}.txt", "", "", [], events)


def _candidate(start=0, end=4):
    return {
        "candidate_id": "ep01_a",
        "segments": [{"start_event_id": start, "end_event_id": end}],
        "hook_quote": f"line {start}",
        "cliffhanger_quote": f"line {end}",
        "sub_scores": {"hook": 4, "cliffhanger": 4, "standalone": 4, "pace": 3},
    }


def test_validate_snaps_to_source_boundaries():
    value, reason = validate_candidate(_candidate(), _episode())
    assert reason is None
    assert value["duration_s"] == 25.0
    assert value["segments"][0]["start_s"] == 0.0
    assert value["segments"][0]["end_s"] == 25.0


def test_validate_rejects_unknown_ids_and_unverified_quotes():
    invalid = _candidate()
    invalid["segments"] = [{"start_event_id": 90, "end_event_id": 91}]
    assert validate_candidate(invalid, _episode())[1] == "unknown_event_id"

    invalid = _candidate()
    invalid["hook_quote"] = "not in screenplay"
    assert validate_candidate(invalid, _episode())[1] == "hook_quote_unverified"


def test_validate_cross_episode_combo_order():
    episodes = {1: _episode(1), 2: _episode(2)}
    combo = _candidate()
    combo["candidate_id"] = "combo_01"
    combo["segments"] = [
        {"episode": 1, "start_event_id": 0, "end_event_id": 2},
        {"episode": 2, "start_event_id": 3, "end_event_id": 5},
    ]
    combo["hook_quote"] = "line 0"
    combo["cliffhanger_quote"] = "line 5"
    result, reasons = validate_stage2_combos(
        {"cross_episode_combos": [combo]}, list(episodes.values())
    )
    assert len(result) == 1
    assert reasons == {}
