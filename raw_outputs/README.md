# Raw Outputs — 50-Episode Microdrama Promo Run

This folder contains the complete, unedited outputs generated from running the **Promo Finder Pipeline** on the full 50-episode microdrama input pack (`data/show/`), as required by the **Kuku AI Generalist Assignment**.

---

## Output Manifest

| File | Format | Description |
| :--- | :--- | :--- |
| **`promos.json`** | JSON (107 KB) | **Primary Deliverable:** Complete, unedited list of all ranked promo candidates across the 50 episodes. Contains exact frame-accurate start/end timestamps, episode IDs, hook quotes, cliffhanger quotes, sub-scores (Hook, Cliffhanger, Standalone, Pace), final composite scores, and posting order rationales. |
| **`promos.csv`** | CSV (21 KB) | Flat tabular export of all ranked promos for spreadsheet review (Rank, Promo ID, Episodes, Start/End Timestamps, Duration, Final Score, Hook, Cliffhanger, Rationale). |
| **`ranked_report.md`** | Markdown | Human-readable audit report detailing every promo, its segment breakdown, verified dialogue quotes, and editorial evaluation. |
| **`validation_report.json`** | JSON | Deterministic validation report confirming strict enforcement of the 20.0s–60.0s duration window, hook-in-first-3s rule, and fuzzy-matched quote boundaries. |
| **`stage2_report.json`** | JSON | Global cross-episode deduplication and spoiler hazard identification. |
| **`parse_report.json`** | JSON | Screenplay parser report (50 episodes parsed, 3,671 screenplay dialogue/action events ingested, 0 timestamp anomalies). |
| **`run_log.txt`** | Text | Full chronological execution log of the pipeline run. |
| **`cost_report.json`** | JSON | Total tokens consumed, API call count, and inference economics. |

---

## Summary of Results Across the 50 Episodes
* **Input Episodes:** 50 episodes (3,671 total screenplay events)
* **Valid Promos Discovered:** 56 promos strictly meeting all 20–60s broadcast constraints
* **Top Promo (#1):** `ep01_cand01` — Episode 1 `[00:11.30 → 00:41.20]` (29.9s, Score: 0.9412)
  * **Hook:** *"You should turn around, Juliana."*
  * **Cliffhanger:** *"Then you are already an accomplice."*
  * **Posting Rationale:** Hero Launch Ad — Zero lore required; immediately drops the viewer into physical danger and introduces the central protagonist.

