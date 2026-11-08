# ──────────────────────────────────────────────────────────────
# promo_finder/parse.py – Screenplay parser
# ──────────────────────────────────────────────────────────────
"""
Parse microdrama screenplay .txt files into normalised Episode objects.

Timestamp format in the source files:  MM:SS.ff  (minutes : seconds . hundredths)
Internally all times are stored as **float seconds**.

The format was observed from the Kuku input pack:
  - Header: EPISODE NUMBER / EPISODE LOGLINE / CONTINUITY NOTES
  - Delimiter: --- SCRIPT START --- … --- SCRIPT END ---
  - Scenes: SCENE NN / Scene heading: … / Scene start: … / Scene end: …
  - Events: **TYPE (Parenthetical):**  then  Start: (MM:SS.ff) | End: (MM:SS.ff)
            followed by the content text on the next line.
  - Types: CAMERA, ACTION, SOUND FX, dialogue (SPEAKER_NAME)
  - Casing varies between episodes: parser is case-insensitive for headers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Timestamp helpers ────────────────────────────────────────

_TS_RE = re.compile(
    r"(?:(?P<hours>\d+):)?(?P<minutes>\d+):(?P<seconds>\d+)(?:\.(?P<fraction>\d+))?"
)


def parse_ts(raw: str) -> float:
    """Convert screenplay timestamps to float seconds.

    The supplied pack uses ``MM:SS.ff``.  ``HH:MM:SS`` and ``MM:SS`` are
    accepted as well so the CLI remains useful for a new show with the same
    general convention.
    """
    m = _TS_RE.search(raw)
    if not m:
        raise ValueError(f"Cannot parse timestamp: {raw!r}")
    hours = int(m.group("hours") or 0)
    minutes = int(m.group("minutes"))
    seconds = int(m.group("seconds"))
    fraction = m.group("fraction") or "0"
    fraction_s = int(fraction) / (10 ** len(fraction))
    return hours * 3600 + minutes * 60 + seconds + fraction_s


def fmt_ts(seconds: float) -> str:
    """Float seconds → 'MM:SS.ff' matching the source format."""
    total_hundredths = max(0, int(round(seconds * 100)))
    mins, hundredths = divmod(total_hundredths, 6000)
    secs, fraction = divmod(hundredths, 100)
    return f"{mins:02d}:{secs:02d}.{fraction:02d}"


def fmt_ts_short(seconds: float) -> str:
    """Float seconds → 'MM:SS' for display."""
    mins = int(seconds // 60)
    secs = int(seconds) % 60
    return f"{mins:02d}:{secs:02d}"


# ── Data classes ─────────────────────────────────────────────

@dataclass
class Event:
    id: int
    t: float           # start time (seconds)
    t_end: float       # end time (seconds)
    type: str           # "camera" | "action" | "dialogue" | "sound_fx"
    speaker: Optional[str]      # e.g. "LADY JULIANA" or None
    parenthetical: Optional[str]  # e.g. "Cold, Commanding" or None
    text: str
    scene: int          # scene number this event belongs to
    t_end_estimated: bool = False

    @property
    def duration(self) -> float:
        return self.t_end - self.t


@dataclass
class Scene:
    number: int
    heading: str
    start: float
    end: float


@dataclass
class Episode:
    episode: int
    filename: str
    logline: str
    continuity_notes: str
    scenes: list[Scene] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        if self.scenes:
            return max(s.end for s in self.scenes)
        if self.events:
            return max(e.t_end for e in self.events)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "episode": self.episode,
            "filename": self.filename,
            "duration_s": round(self.duration_s, 2),
            "logline": self.logline,
            "continuity_notes": self.continuity_notes,
            "scenes": [
                {"number": s.number, "heading": s.heading,
                 "start": s.start, "end": s.end}
                for s in self.scenes
            ],
            "events": [
                {
                    "id": e.id, "t": e.t, "t_end": e.t_end,
                    "type": e.type, "speaker": e.speaker,
                    "parenthetical": e.parenthetical, "text": e.text,
                    "scene": e.scene, "t_end_estimated": e.t_end_estimated,
                }
                for e in self.events
            ],
        }


# ── Parser ───────────────────────────────────────────────────

# Matches event headers like **CAMERA:** or **LADY JULIANA (Cold, Commanding):** or **SOUND FX:**
_EVENT_HEADER_RE = re.compile(
    r"^\*\*"
    r"(?P<label>[A-Za-z][A-Za-z0-9 '.\-/]+?)"       # speaker or type name
    r"(?:\s*\((?P<paren>[^)]*)\))?"              # optional parenthetical
    r"\s*:\*\*\s*$",
    re.IGNORECASE,
)

# Matches the Start/End timestamp line
_TS_LINE_RE = re.compile(
    r"Start:\s*\((?P<start>[^)]+)\)"
    r"(?:\s*\|\s*End:\s*\((?P<end>[^)]+)\))?"
)

# Scene header line  e.g. "SCENE 01" or "SCENE 14"
_SCENE_NUM_RE = re.compile(r"^SCENE\s+(\d+)\s*$", re.IGNORECASE)

# Scene metadata lines (case-insensitive)
_SCENE_HEADING_RE = re.compile(r"^scene\s+heading:\s*(.+)$", re.IGNORECASE)
_SCENE_START_RE = re.compile(r"^scene\s+start:\s*(.+)$", re.IGNORECASE)
_SCENE_END_RE = re.compile(r"^scene\s+end:\s*(.+)$", re.IGNORECASE)

# Dialogue types that are NOT dialogue (i.e. they are production elements)
_NON_DIALOGUE_TYPES = {"CAMERA", "ACTION", "SOUND FX", "SOUND", "SFX", "MUSIC", "V.O."}


def _classify_event(label: str) -> tuple[str, Optional[str]]:
    """Return (type, speaker). Type is one of camera/action/sound_fx/dialogue."""
    upper = label.strip().upper()
    if upper == "CAMERA":
        return "camera", None
    if upper == "ACTION":
        return "action", None
    if upper in ("SOUND FX", "SOUND", "SFX", "MUSIC"):
        return "sound_fx", None
    # Everything else is dialogue
    return "dialogue", label.strip()


def parse_episode(filepath: str | Path) -> Episode:
    """Parse a single screenplay text file into an Episode."""
    filepath = Path(filepath)
    lines = filepath.read_text(encoding="utf-8").splitlines()

    # ── Parse header ──
    episode_num = 0
    logline = ""
    continuity = ""

    for line in lines[:10]:
        line_s = line.strip()
        low = line_s.lower()
        if low.startswith("episode number:"):
            # Extract number from e.g. "Episode 42"
            m = re.search(r"(\d+)", line_s.split(":", 1)[1])
            if m:
                episode_num = int(m.group(1))
        elif low.startswith("episode logline:"):
            logline = line_s.split(":", 1)[1].strip()
        elif low.startswith("continuity notes:"):
            continuity = line_s.split(":", 1)[1].strip()

    if episode_num == 0:
        fallback = re.search(r"episode[-_ ]?(\d+)", filepath.stem, re.IGNORECASE)
        if fallback:
            episode_num = int(fallback.group(1))

    ep = Episode(
        episode=episode_num,
        filename=filepath.name,
        logline=logline,
        continuity_notes=continuity,
    )

    # ── Find script body ──
    script_start = None
    script_end = None
    for i, line in enumerate(lines):
        if "SCRIPT START" in line.upper():
            script_start = i + 1
        if "SCRIPT END" in line.upper():
            script_end = i

    if script_start is None:
        return ep  # no script body found

    body = lines[script_start: script_end or len(lines)]

    # ── Parse scenes and events ──
    current_scene_num = 0
    event_id = 0
    i = 0

    while i < len(body):
        line = body[i].strip()

        # ── Scene header ──
        m_scene = _SCENE_NUM_RE.match(line)
        if m_scene:
            current_scene_num = int(m_scene.group(1))
            heading = ""
            s_start = 0.0
            s_end = 0.0
            # Read the next few lines for heading/start/end
            for j in range(i + 1, min(i + 6, len(body))):
                sl = body[j].strip()
                m = _SCENE_HEADING_RE.match(sl)
                if m:
                    heading = m.group(1).strip()
                    continue
                m = _SCENE_START_RE.match(sl)
                if m:
                    s_start = parse_ts(m.group(1))
                    continue
                m = _SCENE_END_RE.match(sl)
                if m:
                    s_end = parse_ts(m.group(1))
                    continue
            ep.scenes.append(Scene(
                number=current_scene_num,
                heading=heading,
                start=s_start,
                end=s_end,
            ))
            i += 1
            continue

        # ── Event header ──
        m_header = _EVENT_HEADER_RE.match(line)
        if m_header:
            label = m_header.group("label")
            paren = m_header.group("paren")

            event_type, speaker = _classify_event(label)

            # Next line should be the timestamp
            ts_line = body[i + 1].strip() if i + 1 < len(body) else ""
            m_ts = _TS_LINE_RE.search(ts_line)

            if m_ts:
                t_start = parse_ts(m_ts.group("start"))
                end_raw = m_ts.group("end")
                t_end = parse_ts(end_raw) if end_raw else t_start
                t_end_estimated = end_raw is None
                # Content is the line after the timestamp
                content = body[i + 2].strip() if i + 2 < len(body) else ""
                # Strip surrounding quotes from dialogue
                if content.startswith('"') and content.endswith('"'):
                    content = content[1:-1]
                i += 3
            else:
                # No timestamp found — skip this malformed event
                i += 1
                continue

            if t_end < t_start:
                t_end = t_start

            ev = Event(
                id=event_id,
                t=t_start,
                t_end=t_end,
                type=event_type,
                speaker=speaker,
                parenthetical=paren,
                text=content,
                scene=current_scene_num,
                t_end_estimated=t_end_estimated,
            )
            ep.events.append(ev)
            event_id += 1
            continue

        i += 1

    # A few new-show exports omit event ends. Estimate those ends from the
    # next later event, then the enclosing scene, then a small default.
    scene_ends = {scene.number: scene.end for scene in ep.scenes}
    for event in ep.events:
        if not event.t_end_estimated:
            continue
        next_start = next(
            (other.t for other in ep.events if other.t > event.t),
            None,
        )
        fallback = scene_ends.get(event.scene, 0.0)
        end = next_start or fallback or event.t + 2.0
        event.t_end = max(event.t, end)

    return ep


def parse_folder(folder: str | Path) -> list[Episode]:
    """Parse all episode .txt files in a folder, sorted by episode number.

    Direct children are preferred.  If none exist, a recursive search makes
    ``python find_promos.py <show-root>`` work when the input pack contains a
    single nested show directory.
    """
    folder = Path(folder)
    files = sorted(folder.glob("episode-*.txt"))
    if not files:
        files = sorted(folder.rglob("episode-*.txt"))
    episodes = []
    for f in files:
        ep = parse_episode(f)
        episodes.append(ep)
    return sorted(episodes, key=lambda ep: (ep.episode, ep.filename))


def parse_report(episodes: list[Episode]) -> dict:
    """Return a compact, JSON-serialisable parser quality report."""
    anomalies: list[dict] = []
    for ep in episodes:
        if ep.episode <= 0:
            anomalies.append({"episode": ep.filename, "reason": "missing_episode_number"})
        if not ep.events:
            anomalies.append({"episode": ep.episode, "reason": "no_events"})
        if not ep.scenes:
            anomalies.append({"episode": ep.episode, "reason": "no_scenes"})
        previous_start = -1.0
        for event in ep.events:
            if event.t < previous_start - 1.0:
                anomalies.append({
                    "episode": ep.episode,
                    "event_id": event.id,
                    "reason": "non_monotonic_start",
                })
            if event.t_end < event.t:
                anomalies.append({
                    "episode": ep.episode,
                    "event_id": event.id,
                    "reason": "negative_duration",
                })
            if event.duration > 60:
                anomalies.append({
                    "episode": ep.episode,
                    "event_id": event.id,
                    "reason": "event_over_60_seconds",
                    "duration_s": round(event.duration, 2),
                })
            previous_start = event.t

    return {
        "episodes_parsed": len(episodes),
        "episodes_with_events": sum(bool(ep.events) for ep in episodes),
        "total_events": sum(len(ep.events) for ep in episodes),
        "estimated_event_ends": sum(
            event.t_end_estimated for ep in episodes for event in ep.events
        ),
        "anomalies": anomalies,
        "clean": not anomalies,
    }


# ── Compact LLM view ─────────────────────────────────────────

def render_compact(ep: Episode) -> str:
    """
    Render an episode as a compact text for LLM input.
    One event per line:
      [E07 00:41.0-00:43.5 #12] MAYA: "Get out of my house."
      [E07 00:43.5-00:46.0 #13] ACTION: Slams door in face.
    """
    lines = []
    lines.append(f"=== EPISODE {ep.episode} ===")
    lines.append(f"Logline: {ep.logline}")
    lines.append(f"Duration: {fmt_ts(ep.duration_s)} ({ep.duration_s:.1f}s)")
    lines.append(f"Scenes: {len(ep.scenes)}")
    lines.append("")

    for ev in ep.events:
        ts = f"{fmt_ts(ev.t)}-{fmt_ts(ev.t_end)}"
        eid = f"E{ep.episode:02d}"
        prefix = f"[{eid} {ts} #{ev.id}]"

        if ev.type == "dialogue" and ev.speaker:
            paren_str = f" ({ev.parenthetical})" if ev.parenthetical else ""
            lines.append(f'{prefix} {ev.speaker}{paren_str}: "{ev.text}"')
        elif ev.type == "camera":
            lines.append(f"{prefix} CAMERA: {ev.text}")
        elif ev.type == "sound_fx":
            lines.append(f"{prefix} SOUND: {ev.text}")
        else:  # action
            lines.append(f"{prefix} ACTION: {ev.text}")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python parse.py <folder>")
        sys.exit(1)

    folder = sys.argv[1]
    episodes = parse_folder(folder)

    print(f"\n{'='*60}")
    print(f"Parsed {len(episodes)} episodes from: {folder}")
    print(f"{'='*60}\n")

    anomalies = []
    for ep in episodes:
        duration = ep.duration_s
        n_events = len(ep.events)
        n_scenes = len(ep.scenes)

        # Check monotonic timestamps
        prev_t = -1.0
        for ev in ep.events:
            if ev.t < prev_t - 0.5:  # small tolerance for overlapping events
                anomalies.append(
                    f"  Ep {ep.episode}: Non-monotonic at event #{ev.id} "
                    f"(t={ev.t:.2f}, prev={prev_t:.2f})"
                )
            prev_t = ev.t

        # Check for very long events (> 30s)
        for ev in ep.events:
            if ev.duration > 30:
                anomalies.append(
                    f"  Ep {ep.episode}: Long event #{ev.id} ({ev.duration:.1f}s) "
                    f"type={ev.type}"
                )

        print(
            f"Episode {ep.episode:3d}: {n_events:3d} events, "
            f"{n_scenes} scenes, {duration:.1f}s total  "
            f"({ep.filename})"
        )

    print(f"\n--- Anomalies ({len(anomalies)}) ---")
    for a in anomalies:
        print(a)

    # Print compact view for 3 sample episodes
    samples = [episodes[0], episodes[len(episodes)//2], episodes[-1]]
    for ep in samples:
        print(f"\n{'='*60}")
        print(render_compact(ep))

