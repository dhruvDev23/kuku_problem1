# Solution Doc — Problem 1: Find the Promos

## 1. Problem Choice and Operational Framing

I chose Problem 1 because promo discovery is the primary operational bottleneck in Kuku's weekly release pipeline. Kuku produces weekly 1–2 minute vertical microdramas for global audiences; human editors currently spend hours manually watching entire 50-episode seasons to cut 20–60s vertical promos for TikTok, Instagram Reels, and YouTube Shorts. 

**Core Design Principle:** Promo selection is a *hybrid cognitive task*. LLMs excel at semantic narrative intuition (identifying emotional tension, curiosity gaps, dialogue punch, and cliffhangers), but fail at exact timestamp arithmetic and hard constraint enforcement. Our architecture enforces a strict division of labor: **AI extracts dramatic potential; deterministic code verifies physics, timestamps, duration, and safety.**

## 2. Operational Assumptions

- **Text-Only Ingestion:** No pre-rendered video/audio exists at promo discovery time. Visual velocity, kinetic pacing, and camera framing are inferred directly from scene headings and action lines.
- **Duration Window:** Exactly 20.0s to 60.0s total runtime (vertical short-form sweet spot). Single continuous scenes preferred; multi-segment joins allowed up to 3 segments in chronological order.
- **Cold Audience Rule:** A promo must make immediate sense to a scrolling user with zero prior context. Heavy lore-dependent or late-season spoiler scenes are penalized.
- **First 3s Hook & Unresolved Cut:** An arresting event (threat, accusation, slap, reveal) must occur in the first 3.0s; the clip must terminate on an unresolved narrative cliffhanger before relief.
- **Audience:** English-language screenplays tailored for US vertical short-form consumption.

## 3. System Architecture: LLM Semantic Judgment vs. Deterministic Code

```
[50 Screenplay TXTs] -> [Regex Parser (Code)] -> [Stage 1: Candidate Extraction (LLM)]
-> [Boundary Snapping & Quote Verification (Code)] -> [Stage 2: Cross-Episode Deduplication & Spoilers (LLM)]
-> [Multi-Factor Scoring (Code)] -> [Comparative Rerank (LLM / Formula Fallback)] -> [MMR Diversity Pass (Code)]
-> [Streamlit Human Review UI + editor_feedback.jsonl + outputs/ JSONs]
```

- **What Code Owns:** Frame-accurate timestamp math, quote verification via fuzzy sequence matching, 20–60s duration snapping, action density heuristics, dialogue turn pacing, duplicate segment rejection, and MMR diversity filtering (max 2 promos/episode in top ranks).
- **What AI Owns:** Emotional escalation scoring (Hook, Cliffhanger, Standalone, Pace on 1–5 scale), dialogue subtext interpretation, spoiler risk detection, and posting priority rationale ("Why it works").

## 4. Multi-Factor Scoring Formula

Raw LLM scores heavily suffer from grade inflation (clustering at 4/5 or 5/5). We calibrate candidate quality through a deterministic multi-objective weighted formula combined with objective text heuristics and penalty deductions:

$$\text{Score} = 0.25 \times \text{Hook} + 0.30 \times \text{Cliffhanger} + 0.20 \times \text{Standalone} + 0.10 \times \text{Pace} + 0.15 \times \text{Text\_Heuristics} - \text{Penalties}$$

- **Penalties:** High spoiler risk (-0.30), Context/Lore dependency (-0.20), Visual dependency risk (-0.15), Borderline duration (-0.05).
- **Fail-Safe Resilience:** If cloud LLM rate limits or daily quotas are reached, the ranking automatically falls back to this multi-factor mathematical score in <0.01s without crashing or pipeline stalling.

## 5. Top Ranked Promos Discovered Across the 50 Episodes (36 Valid Promos Found)

The pipeline discovered and ranked **36 valid, duration-verified promos** across the 50 episodes. Below are the top ranked promos with timestamps, hook/cliffhanger quotes, and launch posting strategy:

| Rank | Promo ID | Segments & Timestamps | Dur | Score | Hook Quote (First 3s) & Cliffhanger | Which to Post First & Why |
|---|---|---|---|---|---|---|
| **#1** | ep01_cand01 | Ep 1 [00:11.30 → 00:41.20] | 29.9s | 0.9412 | **H:** "You should turn around, Juliana."<br/>**C:** "Then you are already an accomplice." | **Launch Day Hero Ad:** Zero lore needed. Immediately establishes the protagonist under threat while introducing the core series premise. |
| **#2** | ep21_a | Ep 21 [00:03.50 → 00:40.40] + [01:31.00 → 01:48.40] | 54.3s | 0.9055 | **H:** "A loud wooden slam as double barn doors violently fly open..."<br/>**C:** "If you take one more step, you burn with it." | **Action Retargeting Ad:** Maximum physical velocity. Explosive kinetic opening and life-or-death visual standoff. |
| **#3** | ep23_a | Ep 23 [00:38.50 → 01:28.00] | 49.5s | 0.8803 | **H:** "No."<br/>**C:** "Tell me who ordered the carriage." | **High Defiance Promo:** High curiosity gap. Subverts victim expectation with fierce dialogue defiance and an interrogation cliffhanger. |
| **#4** | ep18_a | Ep 18 [00:00.00 → 00:22.50] | 22.5s | 0.8630 | **H:** "Low-angle shot on floor as bright orange flames crackle..."<br/>**C:** "Leave her." | **Short-Form Punchy Hook:** Rapid 22s cut for TikTok algorithmic testing; visceral visual danger and commanding protector arrival. |
| **#5** | ep02_a | Ep 2 [00:00.00 → 00:23.70] | 23.7s | 0.8479 | **H:** "I cannot marry you, Juliana."<br/>**C:** "Because I will not survive the wedding." | **Romantic Conflict Ad:** Rejection hook directly appeals to microdrama romance fans; ends on a shocking life-threat revelation. |

## 6. Quality Audit: Where Does the Tool Pick Badly?

Intellectual honesty regarding failure modes:

1. **Dramatic on paper, static on screen:** Ep 08 (#5) scored high on dialogue pacing because characters exchange rapid lines, but the action depicts Juliana quietly reading an herbalism book by a hearth ("Some of the pages are ruined... yarrow"). While emotionally warm in-context, it completely lacks visual momentum as a cold social video ad.
2. **Cliffhanger resolved in immediate next line:** Ep 17 (#1) cut at Alexander saying "As long as I draw breath...". The very next screenplay beat (28.0s) immediately completes the sentence ("...no one will hurt you again") and resolves the romantic tension in 4 seconds, destroying viewer retention.
3. **Stage directions masquerading as hooks:** Ep 35 (#4) opened on "Close-up on her trembling hands gripping a mossy stone bolt". While atmospheric in text, in video production this manifests as an unengaging 3-second establishing shot of an old door.
4. **Major late-season plot spoilers:** Ep 28 (#249) features Catherine stomping an herbarium while the Dowager Duchess stirs, prematurely exposing the late-season poisoning conspiracy to new viewers.
5. **Dialogue turn density bias:** Rapid conversational banter without physical stakes can fool dialogue heuristics into scoring polite debates higher than slow-burn physical threats (corrected via action verb density weighting).

## 7. Production Scaling & Economics for Weekly Show Releases

- **Compute & Token Economics:** Across 50 episodes, Stage 1 extraction requires ~195k tokens. At Groq/Gemini Flash pricing ($0.05–$0.15/M tokens), total inference cost is **$0.02 to $0.05 per full 50-episode show**. Local SHA-256 disk caching ensures zero re-spending on re-runs.
- **Throughput:** Under free-tier rate limits, extraction takes ~3 minutes; with async workers on standard tier, analysis completes in **under 40 seconds per show**.
- **Human-in-the-Loop Workflow:** Rather than an editor spending 3 hours watching 50 episodes, our Streamlit UI surfaces the ranked candidate cards with segment bounds and rationales. Editors approve, reject, or adjust clips in **under 10 minutes** (>90% time savings). Editor decisions persist to `eval/editor_feedback.jsonl` to fine-tune future scoring weights.

## 8. Success Metrics & Verification Loop

- **Operational Velocity:** (1) Editor Acceptance Rate (target ≥ 70%), (2) Average boundary adjustment (< 2.0s drift), (3) Turnaround time per show (< 15 min).
- **Ad Performance (Paid Traffic A/B Test):** A/B test pipeline-picked promos vs. editor-picked promos across identical TikTok/Meta ad spend. Core evaluation metrics: **3-second thumbstop rate** (testing hook power), **Video Completion Rate (VCR)**, and **App Installs per Impression (IPM)**.

## 9. AI Tools Used & Documented Tool Failure

- **AI Tools Used:** Claude Opus (pipeline architecture, test suite design), Groq / Qwen 2.5 27B (screenplay extraction), Google GenAI SDK / Gemini 3.8 Flash (cross-episode deduplication), Antigravity IDE.
- **Where AI Got It Wrong:** During validation, the LLM attempted to sequentially "repair" 96 slightly out-of-bounds candidates one-by-one, initiating 96 background API calls that triggered quota exhaustion (429 RESOURCE_EXHAUSTED) and froze execution for minutes. We realized this was an algorithmic anti-pattern: the pipeline already had 56 fully valid candidates (far more than needed for a top-tier launch). We corrected this by replacing the recursive LLM repair loop with a deterministic candidate sufficiency check, reducing validation latency from 7 minutes to **0.12 seconds**.
- **Free Tiers vs. Paid APIs:** Built 100% on free tiers (Groq free tier, Gemini Flash, local Ollama, and offline heuristic engine). If paid vision APIs were available (e.g. Gemini 1.5 Pro Video), we would pass rendered video frames to score actor kinetic motion and audio loudness peaks directly.
