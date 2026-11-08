# Microdrama Promo Finder

A text-only prototype for finding 20–60 second microdrama promo candidates from timestamped screenplay files. It selects moments that open with a hook, end before an unresolved answer, and remain understandable to a cold viewer.

The tool does not see video or audio. Stage directions, visual risk, acting, blocking, sound, and likely social performance are inferred from text and should be reviewed by an editor.

## Quick start

~~~bash
cd promo-finder
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="..."
python find_promos.py /path/to/show-folder
~~~

For local tests, install requirements-dev.txt and run `python -m pytest -q`.

The input folder can contain episode-*.txt directly or inside one nested directory. Outputs are written to outputs/<run_id>/:

- promos.json and promos.csv: every validated candidate in deterministic rank order
- ranked_report.md: top 10 with hooks, cliffhangers, scores, flags, and posting rationale
- validation_report.json: raw → first-pass valid → repaired → dropped funnel and reasons
- cost_report.json and cost_log.jsonl: token and estimated cost accounting
- parse_report.json: episode/event count and parser anomalies
- stage2_report.json: duplicate, spoiler, and combo decisions
- run_log.txt: unedited run log

The screenplay pack belongs in data/ or another private location and is ignored by Git. Do not publish raw outputs that contain quoted screenplay lines.

## Local smoke test

Run without credentials to verify parsing, validation, ranking, and report writing:

~~~bash
python find_promos.py /path/to/show-folder --offline
~~~

This deterministic baseline is for pipeline verification only; it is not the editorial model.

## Configuration and model swapping

config.yaml controls provider, model per stage, rate limiting, cache location, promo duration, penalties, and ranking weights. Supported providers:

- gemini: uses the current google-genai SDK and the environment variable named by gemini.api_key_env.
- openai_compatible: sends JSON-mode chat completions to base_url using the configured key environment variable. This also supports a Kuku-provided compatible endpoint.

Example:

~~~bash
python find_promos.py /path/to/show-folder --config config.yaml
~~~

The LLM layer has one public entry point, generate_json(prompt, schema, *, model=None, temperature=...). It uses a SHA-256 disk cache, schema checks, one invalid-response repair retry, exponential backoff for 429/5xx responses, a requests-per-minute limiter, and token/cost logging.

## Pipeline

1. Parse the screenplay into normalized events with float-second timestamps.
2. Ask Stage 1 for per-episode summaries, characters, and 4–6 candidate moments.
3. Resolve event IDs and snap every segment to source event boundaries.
4. Reject or repair candidates with invalid IDs, quotes, order, duration, or segment count.
5. Compute cheap text features such as action verbs, pace, monologue length, named speakers, and unfinished beats.
6. Ask Stage 2 to remove duplicates, flag spoilers, and propose cross-episode combos; validate combos with the same deterministic gate.
7. Blend LLM scores, heuristic signals, risk penalties, comparative reranking, and diversity constraints.
8. Write raw output artifacts without hand-editing them.

The LLM judges hooks, cliffhangers, standalone clarity, summaries, rationale, and comparative ordering. Code owns parsing, timestamp resolution, validation, snapping, deduplication, scoring, diversity, caching, retries, and reporting.

## Evaluation

Create a blind set in eval/gold_blind.json before reviewing model output. Each gold segment should include episode, start_s, and end_s; an optional scene can provide a same-scene match.

~~~bash
python eval/run_eval.py outputs/<run_id> --gold eval/gold_blind.json
python eval/run_eval.py outputs/<run_id> --second-output outputs/<second_run_id>
~~~

The evaluator reports duration/order/quote compliance, gold precision and recall using segment IoU ≥ 0.5, and top-20 Jaccard stability. Populate eval/failures.md with real examples from the raw scripts. No text-only evaluation can show actual social performance; a real rollout should compare editor acceptance, timestamp edits, review time, 3-second view rate, completion, and install conversion for tool-picked versus editor-picked promos.

## Optional review UI

~~~bash
pip install streamlit
streamlit run app.py
~~~

The UI accepts a ZIP or multiple episode text files, runs the same pipeline, shows the top 10, and stores approve/reject/adjust notes in eval/editor_feedback.jsonl. It does not deploy or publish screenplay content.

## Known limits

- No video/audio means visual and kinetic judgments can be wrong.
- Exact quote checks do not prove a line will be audible or compelling.
- Cross-episode combos are only accepted when event IDs and quotes resolve against the original scripts.
- The blind gold file must be authored by a human; an empty gold set is reported as unevaluable, not as a score.
- The tool is a review aid, not a production-ready automatic publishing system.

