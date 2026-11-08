# AI Mistake Log

Concrete mistakes observed during development. Each entry describes the
error, what caught it, and the fix.

---

### 1. JSONDecodeError bypass in retry path

**Where:** LLM layer (`llm.py`), original scaffold
**What happened:** The JSON extraction function raised `ValueError` on
malformed responses, but the retry logic only caught `JSONDecodeError`.
This meant parse failures bypassed the retry-with-error-feedback path.
**Caught by:** Code review during implementation.
**Fix:** Unified the extraction to raise `ValueError`, and the retry loop
catches both `ValueError` and `JSONDecodeError`.

---

### 2. Repair prompt sent Python repr instead of JSON

**Where:** `validate.py`, `repair_candidate()` function
**What happened:** The repair prompt used an f-string `{candidate}` which
produces Python dictionary repr notation (with single quotes, `True`/`False`,
`None`). This is not valid JSON and would confuse the LLM into returning
malformed JSON back.
**Caught by:** Codebase audit.
**Fix:** Changed to `json.dumps(candidate, indent=2, default=str)`.

---

### 3. Offline baseline ranked quiet scenes above confrontations

**Where:** `stage1_candidates.py`, `_offline_candidates()` deterministic baseline
**What happened:** The sliding-window baseline assigned identical sub-scores
(all 3/5) to every candidate, so ranking was driven entirely by heuristic
features (pace, action verbs, etc.). Episode 8 — a tender scene about reading
a herbalism book and arranging dried flowers — ranked #5 overall because it
had slightly higher event density than some genuinely dramatic scenes.
**Caught by:** Manual review of `outputs/baseline_50eps/ranked_report.md`.
**Impact:** Demonstrates why the offline mode is only a pipeline-verification
tool, not a substitute for LLM editorial judgment. The heuristic features
cannot distinguish "quiet tenderness" from "tense confrontation" when both
have similar event density.

---

### 4. test_parse.py silently passed when data was missing

**Where:** `tests/test_parse.py`
**What happened:** Tests that needed the data folder used
`if not os.path.isdir(DATA_DIR): print("SKIP"); return`, which made pytest
report them as PASSING even when the data was absent. CI would show green
even though no real validation ran.
**Caught by:** Codebase audit.
**Fix:** Changed to `@pytest.mark.skipif(...)` decorator so pytest correctly
reports SKIPPED.

---

### 5. google-genai SDK version confusion

**Where:** Initial project setup
**What happened:** The first instinct was to install `google-generativeai`
(the deprecated package). The current official SDK is `google-genai` with a
different import path (`from google import genai` instead of
`import google.generativeai as genai`). The deprecated package uses a
global `genai.configure()` pattern; the new SDK uses an explicit
`genai.Client(api_key=...)` pattern.
**Caught by:** Pre-implementation check of installed packages.
**Fix:** Used `google-genai` throughout with the `Client` API.
