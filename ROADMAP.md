# Build Spec: Microdrama Promo Finder (Kuku Assignment, Problem 1)

> Paste this whole file into the Antigravity agent as the project brief.
> Agent: follow the phases in order. After each phase, STOP, show me the output and wait for my "go". Do not invent facts about the input files. Inspect them first.

---

## 0. Goal and ground rules

Build a tool that reads microdrama screenplays (50 episodes, English, US audience) and finds the best **promos**: 20-60 second clips (one continuous stretch, or up to 3 joined segments, from one episode or across several) that:

1. **Hook**: something in the first 3 seconds makes a scroller stop (slap, reveal, shocking line).
2. **Cliffhanger**: the clip cuts at an unresolved moment.
3. **Standalone**: makes sense to someone who has never seen the show.

For every promo, output: episode(s), start and end timestamp of every segment in order, the hook, the cliffhanger, one line on why it works. Then **rank** the promos and explain which to post first and why. Then **measure quality honestly**, including where the tool fails.

**Hard constraints**
- Runs again on a NEW show folder during the interview: `python find_promos.py <folder>`. No notebook-only logic.
- The LLM is **swappable** through config (Kuku may plug in a stronger model via their API).
- Works on free-tier APIs. Paid models are described in the doc, not required.
- The screenplays are Kuku's confidential content. **Never commit them.** `data/` goes in `.gitignore`. Raw outputs may contain short quoted lines, so keep the repo private or unlisted.
- Honest > impressive. No "production-ready" claims. State limits.
- Only screenplay text is available (no video, no audio). Every visual or kinetic judgment is an inference from text. Say so in the doc.

**What goes to code vs the LLM**
| Code (deterministic) | LLM (judgment) |
|---|---|
| parsing, timestamps, durations | spotting hooks and cliffhangers |
| validation, snapping, dedup | standalone-clarity judgment |
| scoring formula, diversity, final sort | episode summaries, cross-episode combos |
| caching, retries, cost logging | rationale text, comparative rerank |

---

## 1. Repo layout

```
promo-finder/
  README.md                 # run steps, config, limits
  ROADMAP.md                # this file
  config.yaml               # provider, models, weights, thresholds
  find_promos.py            # CLI entrypoint
  app.py                    # (P1) Streamlit UI for upload/run/review
  promo_finder/
    parse.py                # screenplay -> normalized Episode objects
    llm.py                  # ONE swappable interface: generate_json()
    stage1_candidates.py    # per-episode candidate extraction + summary
    stage2_select.py        # global selection, cross-episode combos
    validate.py             # snap, duration, ordering, quote checks
    features.py             # cheap heuristic signals
    rank.py                 # weighted score, diversity, comparative rerank
    report.py               # json/csv/markdown writers
    cost.py                 # token + cost logging
    prompts/
      stage1.txt
      stage2.txt
      rerank.txt
  eval/
    gold_blind.json         # MY hand-picked promos (made BEFORE seeing model output)
    run_eval.py             # precision/recall vs gold, stability, validity rate
    failures.md             # failure taxonomy with real examples
  data/                     # gitignored: input pack goes here
  cache/                    # gitignored: per-episode LLM results
  outputs/                  # raw unedited outputs of runs (submitted as the "raw outputs" folder)
  notebook.ipynb            # thin wrapper that calls the same package
  .gitignore                # data/, cache/, .env, *.zip
```

Secrets via `.env` (`GEMINI_API_KEY` etc.). Never hardcode.

---

## 2. Phases

### Phase 1: Inspect the data and write the parser (P0)

1. Unzip the input pack into `data/`. **Print the first ~60 lines of 3 different episodes** and the file listing. Report:
   - filename pattern and episode numbering
   - exact timestamp format (HH:MM:SS? MM:SS? ranges? brackets?)
   - how scenes, dialogue lines, key actions and speakers are marked
   - anything odd (missing timestamps, titles, headers)
2. Write `parse.py` **against the actual format found**, not an assumed regex. Output a normalized structure:

```json
{
  "episode": 7,
  "duration_s": 118,
  "events": [
    {"id": 0, "t": 0.0, "t_end": 2.0, "type": "scene|dialogue|action", "speaker": "MAYA|null", "text": "..."}
  ]
}
```

   - Store all times internally as **float seconds**; keep a formatter back to the source format.
   - `t_end` of an event = start of the next event (last event: episode end if known, else + a stated default). Flag estimated ends.
3. Write `tests/test_parse.py`: event count > 0 for every file, timestamps monotonic, no event longer than a sane cap. Print a parse report (episodes parsed, anomalies).
4. Add a rendered compact view for LLM input, one event per line, e.g. `[E07 00:41.0-00:43.5 #12] MAYA: "Get out of my house."`, so the model can cite event ids and times copied from the text, never computed.

**Done when:** all 50 files parse, the report is clean, I have eyeballed 3 episodes' parsed output.

### Phase 2: Swappable LLM layer (P0)

`llm.py` exposes exactly one function:

```python
generate_json(prompt: str, schema: dict, *, model: str = None, temperature: float = 0.2) -> dict
```

- Provider and model names come from `config.yaml` (`stage1_model`, `stage2_model`, `rerank_model`). Providers: `gemini` (use the current official Google SDK. Check current docs, because the older `google-generativeai` package is deprecated), plus an `openai_compatible` adapter (base_url + key) so any Kuku-provided API works. Adding a provider should be about 20 lines.
- Structured JSON output with schema where supported; otherwise parse and validate with `pydantic`/`jsonschema`.
- **Exponential backoff with jitter** on 429/5xx, max retries from config. Respect a configurable requests-per-minute limit.
- **Disk cache** keyed by hash(prompt + model + schema) in `cache/`. Re-runs and resumes cost nothing.
- Log prompt/completion tokens and estimated cost per call into `cost.py`.
- On invalid JSON: retry once with the validation error appended.

**Done when:** one test call works on the free tier, a cache hit is demonstrated, and switching the model name in config changes the model used.

### Phase 3: Stage 1, per-episode candidates (P0)

For each episode, one call returns:
- `episode_summary` (max 60 words, spoiler-aware: what is set up, what is unresolved)
- `characters` (name + one-line role as visible in this episode)
- `candidates`: 4-6 moments

Prompt rules (put in `prompts/stage1.txt`):
- Role: editor cutting vertical-drama ads (ReelShort/DramaBox style) for cold viewers.
- **Cite only event ids and timestamps that appear in the input. Never calculate times.**
- Each candidate = 1-3 segments, each `{start_event_id, end_event_id}`. Total 20-60 s. Ordered.
- `hook_quote`: the exact line or action text from the first 3 seconds of the clip (copied verbatim).
- `cliffhanger_quote`: the exact last line or action (copied verbatim) and one sentence on what is left unresolved.
- Prefer: a confrontation, a reveal, betrayal, a threat, a slap or physical action in the first seconds, rapid back-and-forth, a cut BEFORE the answer or reaction.
- Reject: long monologues, exposition, scenes that need earlier lore, endings that resolve the tension, quiet scenes that only read as dramatic on paper.
- Sub-scores 1-5 each: `hook`, `cliffhanger`, `standalone`, `pace`, plus `needs_context` (bool) and `spoiler_risk` (low|med|high).
- Also return `confidence` and `visual_risk` (low|med|high: does it depend on visuals the text cannot show?).

Context option (P1): pass the previous 1-2 episode summaries so the model can judge what a cold viewer would not know.

### Phase 4: Validation in code (P0, most important)

`validate.py` runs on every candidate. **Drop or repair, never trust.**

1. Resolve event ids to real timestamps. **Snap** starts and ends to event boundaries. Reject unknown ids.
2. Segments ordered, non-overlapping, within the episode.
3. Total duration within the configured window (default 20-60 s, with a small tolerance flagged as `borderline`).
4. `hook_quote` must be found (fuzzy match, threshold in config) inside the clip's first ~3 s of events. Otherwise either shift the start to a better event or drop it.
5. `cliffhanger_quote` must match the last event(s) of the clip.
6. Heuristic cliffhanger check: flag clips whose last event is a resolved statement (e.g. an answer to the previous question) when the next event in the script is a reaction or resolution. Prefer ending one event before the resolution.
7. Max 3 segments. Cross-episode combos must be in the order the viewer would meet them.
8. On failure: one **repair call** that sends the failure reason and the same episode excerpt. If still invalid, drop and log with reason.

Log a validation report: `% raw LLM picks valid on first pass`, `% repaired`, `% dropped`, with reason counts. **This is a headline quality metric for the doc.**

### Phase 5: Heuristic features (P1)

`features.py`, cheap and explainable signals computed from the clip text:
- ALL-CAPS stage directions and action verbs (slap, grab, run, crash, scream, ...) in the first 3 s
- events per 10 s (pace); longest single-speaker run (monologue penalty)
- ends on a question mark, an interruption (em dash, "—"), or an unfinished beat
- number of named characters appearing in the clip without introduction inside the clip (standalone proxy)
- first-3-seconds density

These blend with the LLM sub-scores. They also serve as a sanity check on LLM disagreements.

### Phase 6: Stage 2, global selection and cross-episode combos (P0)

One call (or a few chunked calls if the context is too large) receives all validated candidates plus all episode summaries. It:
- removes near-duplicates (same scene or overlapping time ranges)
- proposes up to ~5 **cross-episode combos** (e.g. hook from ep 3 + escalation from ep 4), each with ≤3 segments, referencing existing event ids; these go through Phase 4 again
- flags candidates that spoil late reveals or rely on lore

Output goes back through `validate.py`. A segment the model invents is dropped.

### Phase 7: Ranking (P0)

`rank.py`:
1. `score = w1*hook + w2*cliffhanger + w3*standalone + w4*pace + w5*heuristics − penalties` (weights in `config.yaml`; penalties for `spoiler_risk`, `needs_context`, `visual_risk`, borderline duration).
2. **Diversity pass**: no more than N promos per episode in the top 10, and no two top-10 promos overlapping in time (greedy MMR-style selection).
3. **Comparative rerank** of the top ~15-20 in a single LLM call (pairwise or listwise, `prompts/rerank.txt`) because absolute LLM scores cluster near the top. Final score = blend of formula and rerank position (blend weight in config).
4. For the top 10, generate a short written rationale: *why post this first* (hook strength, standalone clarity, cliffhanger, platform fit), with the trade-off versus the next one.
5. Final list is sorted deterministically (fixed tie-breaks) so re-runs are comparable.

### Phase 8: Outputs (P0)

`report.py` writes to `outputs/<run_id>/`:
- `promos.json` (schema below), `promos.csv`, `ranked_report.md` (top-10 with rationales), `validation_report.json`, `cost_report.json`, `run_log.txt`
- **Never hand-edit these files.** They are the "unedited raw outputs" submission folder.

```json
{
  "rank": 1,
  "promo_id": "ep07_a",
  "segments": [{"episode": 7, "start": "00:41", "end": "01:08", "start_s": 41.0, "end_s": 68.0}],
  "duration_s": 27.0,
  "hook": "…",
  "hook_quote": "…",
  "cliffhanger": "…",
  "cliffhanger_quote": "…",
  "why_it_works": "one line",
  "sub_scores": {"hook": 5, "cliffhanger": 4, "standalone": 4, "pace": 5},
  "heuristics": {"...": 0},
  "flags": ["borderline_duration"],
  "final_score": 0.0,
  "post_first_because": "top-10 only"
}
```

### Phase 9: Quality evaluation (P0)

Do this honestly, it is a large part of the grade.
1. **Blind gold set**: BEFORE looking at model output, I (the human) read 5-6 varied episodes and hand-pick the promos I would post, with timestamps, in `eval/gold_blind.json`.
2. `run_eval.py` reports:
   - **Validity rate** (from Phase 4)
   - **Recall and precision against gold**, with a match defined as time-range IoU ≥ 0.5 or overlap on the same scene
   - **Stability**: run twice, report Jaccard overlap of the top 20
   - **Rule compliance** of final output (duration, ordering, hook-in-3s): should be 100% by construction. Report it anyway
3. **Failure audit** in `eval/failures.md`: review the top 10 and bottom 10 against the raw script. Tag each failure with a type, with a quoted example:
   - dramatic on paper, static on screen (quiet, tense dialogue)
   - cliffhanger actually resolves one line later
   - needs lore a cold viewer lacks
   - hook inferred from a stage direction that is actually boring
   - spoils a major twist
   - duration borderline or time snapped awkwardly
4. State what the evaluation cannot show: no video, so no ground truth of what really performs on social platforms. Propose how Kuku would measure real success (see doc outline).

### Phase 10: Prototype polish (P1, only after the P0 items work)

- `app.py` (Streamlit): upload a zip or folder, paste an API key, pick a model, run, and view the ranked table with a **human review panel** (approve / reject / adjust timestamps / note). Saved decisions go to `eval/editor_feedback.jsonl` and can later become few-shot examples and regression tests.
- Deploy to Streamlit Community Cloud or HF Spaces only if it works **without** shipping the screenplays. Otherwise, repo + README run steps is fine.
- `README.md`: install, config, one-command run, expected runtime, how to swap model, known limits.

### Phase 11: Submission pack

1. **2-page PDF** (outline below)
2. **Prototype link**: private or unlisted repo with README (data excluded)
3. **Raw outputs folder**: `outputs/<run_id>/` from the full 50-episode run, untouched
4. **Walkthrough video** (≤3 min, my own voice): run `find_promos.py` on the data, show the top 3 promos next to the raw script lines, show the validation report, then one failure case and explain it
5. Interview prep: I must be able to run `python find_promos.py <new_folder>` live and explain every design decision

---

## 3. Solution doc outline (2 pages, I write it, the agent drafts only data and tables)

1. **Problem and approach (3-4 lines)**: why this problem, what I scoped in and out.
2. **Assumptions** (list): timestamp semantics, event end = next start, text-only inference, 20-60 s window, up to 3 segments, English only, US audience, etc.
3. **Pipeline diagram + what is LLM vs code** (reasoning for each split).
4. **Ranking logic** and why raw LLM scores are not trusted (clustering, calibration), plus the top-3 posting rationale.
5. **Results**: validity funnel (raw → valid → final), gold-set recall/precision, stability, cost and runtime for 50 episodes.
6. **Where it fails**: 3-4 real examples from `failures.md`, honest.
7. **Scaling to every show** (Kuku releases new shows weekly): per-show cost = tokens × price (use measured token counts), caching, batch APIs, cheap model for Stage 1 and strong model for Stage 2/rerank, parallel episodes within rate limits, and a human editor approving the top-N (target: review minutes per show instead of watching every episode). Mention latency and storage.
8. **How we'd know it worked with a real team**: editor acceptance rate of top-10 picks, edits per accepted promo (timestamp shifts), time saved per show vs manual, and later correlation with actual platform metrics (3-sec view rate, completion, install conversion) from posted promos, with an A/B of tool-picked vs editor-picked.
9. **AI tools used and one place they got it wrong**: this must be a REAL mistake I actually hit (e.g. hallucinated timestamps, deprecated SDK, JSON schema violation). I record it as it happens in `eval/ai_mistakes.md`.
10. **Next steps**: use of audio/video signals, a learned ranker from editor feedback, multilingual support.

---

## 4. Priorities if time runs short (the brief says ~2-3 hours)

- **P0 (must)**: Phases 1, 2, 3, 4, 6, 7, 8, 9 (small gold set of 3-5 episodes is OK)
- **P1 (should)**: Phase 5, Phase 10 Streamlit app
- **P2 (stretch)**: previous-episode context, few-shot examples from editor feedback, multi-provider comparison table (same input, two models)

A smaller version that is validated and honestly evaluated beats a bigger one that is not.

## 5. Agent working rules

- Show the parsed-format report before writing any prompts.
- Do not invent timestamps, events or quotes anywhere. All times come from parsed data.
- Keep functions small and typed; add a test for parse and validate.
- After each phase: print what ran, what failed, what is next. Wait for my approval.
- If anything in this spec conflicts with the real data, tell me and propose a fix instead of guessing.
