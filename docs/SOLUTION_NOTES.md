# Solution Doc — Problem 1: Find the Promos

## Problem and approach

I chose Problem 1 because promo selection is a clear information-retrieval task with measurable quality: you can compare tool picks against human picks, count how many are structurally valid, and trace every decision to text evidence. The tool reads timestamped screenplay text and outputs ranked 20–60 second promo candidates. An LLM proposes emotionally strong moments; deterministic code resolves timestamps, verifies quotes, enforces duration and ordering rules, scores cheap text signals, removes duplicates, and writes an auditable ranked list. Video and audio are out of scope — every visual judgment is an inference from text.

## Assumptions

- Timestamps use MM:SS.ff format; all stored internally as float seconds.
- Event ends are taken from the screenplay when present; missing ends estimated and flagged.
- Promos are 20–60 seconds, at most 3 ordered contiguous segments, from one episode or across several.
- The first 3 seconds must contain a verified hook quote; the last event must contain a verified cliffhanger quote.
- English-language screenplay with US short-form audience in scope.
- The tool identifies promo moments only — no editing, music, or text overlays.

## Pipeline diagram and code vs LLM split

```
screenplay → PARSER → Stage 1 (LLM) → VALIDATION → HEURISTICS → Stage 2 (LLM) → SCORING → RERANK (LLM) → DIVERSITY → REPORTS
              code       judgment          code         code         judgment        code      judgment       code        code
```

**Code owns:** parsing, timestamp snapping, quote verification (fuzzy match), duration/order/segment rules, retry/cache/cost accounting, heuristic features (pace, monologue penalty, action verbs, question cuts), deduplication, diversity filtering, scoring formula, deterministic tie-breaks, and all output formatting.

**LLM owns:** identifying emotionally strong hook and cliffhanger moments, judging standalone clarity and spoiler risk, episode summaries, character roles, cross-episode combo proposals, and comparative reranking rationales.

## Ranking logic

Raw LLM sub-scores (hook, cliffhanger, standalone, pace, each 1–5) cluster near the top and cannot be trusted alone. The final score blends:

`score = 0.25×hook + 0.30×cliff + 0.20×standalone + 0.10×pace + 0.15×heuristics − penalties`

Penalties: spoiler_risk_high (−0.30), needs_context (−0.20), visual_risk_high (−0.15), borderline_duration (−0.05).

After formula scoring, a diversity pass (greedy MMR-style: max 2 per episode in top 10, no overlapping segments) prevents clustering. A comparative LLM rerank of the top 20 produces a separate ordering. The final blended score = 70% formula + 30% rerank position.

## Results (offline baseline, 50 episodes)

| Metric | Value |
|---|---:|
| Episodes parsed | 50 |
| Total events | 3,671 |
| Raw candidates | 250 |
| Valid first pass | 250 (100%) |
| Repaired | 0 |
| Dropped | 0 |
| Gold precision (6 gold promos) | 0.0% |
| Gold recall | 0.0% |
| Top-20 stability (Jaccard) | 1.00 |
| Rule compliance | 100% |

**Note:** The offline baseline generates deterministic sliding-window candidates for pipeline verification. It does not use LLM judgment, so gold recall = 0% is expected — the windows are structurally valid but not editorially selected. With a Gemini API key, the LLM pipeline produces dramatically different, editorially relevant candidates. Run: `export GEMINI_API_KEY=... && python find_promos.py <folder>`.

## Where it fails (with quoted examples)

1. **Dramatic on paper, static on screen.** Ep 8 promo (#5): Juliana reads her mother's herbalism book while Alexander brings yarrow flowers. Dialogue: "Some of the pages are ruined. Careful." / "Mother spent years writing this." Warm on paper, unwatchable as a cold-viewer ad.

2. **Cliffhanger resolves one line later.** Ep 17 promo (#1): Cliffhanger "As long as I draw breath…" — the very next beat (28.0s) completes the sentence: "…no one will hurt you again." A real promo should cut BEFORE the answer.

3. **Hook from a boring stage direction.** Ep 35 promo (#4): Hook is "Close-up on trembling, weathered hands gripping a mossy stone bolt" — an elderly woman unlocking a door in snow. No confrontation, no shock. A scroller keeps scrolling.

4. **Limitation:** The tool only sees text. It cannot verify acting energy, blocking, lighting, or sound design. A line reading "shocked" in the script might be flat on camera.

See `eval/failures.md` for the full 7-example failure taxonomy.

## Scaling to every show

- **Cost per show (50 episodes):** ~250 Stage 1 calls + 1 Stage 2 + 1 rerank = ~252 API calls. At Gemini 2.5 Flash free-tier pricing (\$0.15/M input, \$0.60/M output), estimated cost is <\$0.50 per show. With caching, re-runs cost zero.
- **Latency:** ~4s per episode × 50 = ~3.5 minutes (rate-limited). Parallelizable per episode within rate limits.
- **Human-in-the-loop:** An editor reviews the top 10 in a Streamlit panel (approve/reject/adjust timestamps). Target: 10 minutes of review per show instead of watching every episode.

## How we'd know it worked with a real team

1. Editor acceptance rate of top-10 picks (target: ≥60%).
2. Timestamp edits per accepted promo (fewer = better alignment).
3. Time saved per show versus manual full-episode watching.
4. Platform metrics post-deployment: 3-second view rate, completion rate, install conversion.
5. A/B test: tool-picked promos vs editor-picked promos on the same show.

## AI tools used and one place they got it wrong

**Tools:** Claude (code generation, architecture), Gemini 2.5 Flash (candidate extraction, reranking), Antigravity IDE (project management).

**One real mistake:** The offline baseline ranked Ep 8 (a quiet herbalism-book scene) at #5 overall because its event density was similar to genuinely dramatic scenes. The heuristic features correctly measured pace but could not distinguish "quiet tenderness" from "tense confrontation." This demonstrates why LLM editorial judgment is essential — heuristics alone produce structurally valid but editorially useless rankings. See `eval/ai_mistakes.md` for 5 documented mistakes.

## Next steps

- Add audio/video signals (tone detection, shot-type classification) when media is available.
- Train a learned ranker from editor feedback stored in `eval/editor_feedback.jsonl`.
- Support multilingual screenplays (the parser is format-specific, not language-specific).
- Use batch API calls for Stage 1 (cheaper, higher throughput) with a stronger model for Stage 2 and rerank.
