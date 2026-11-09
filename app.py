"""Optional Streamlit review UI.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path

import yaml


def _safe_extract(uploaded_zip, destination: Path):
    with zipfile.ZipFile(uploaded_zip) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if destination.resolve() not in target.parents and target != destination.resolve():
                raise ValueError("Zip contains an unsafe path")
        archive.extractall(destination)


def _write_uploaded_files(files, destination: Path):
    for uploaded in files:
        if not uploaded.name.lower().endswith(".txt"):
            continue
        target = destination / Path(uploaded.name).name
        target.write_bytes(uploaded.getvalue())


def _save_feedback(path: Path, decision: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(decision) + "\n")


def main():
    import streamlit as st

    st.set_page_config(page_title="Microdrama Promo Finder", layout="wide")
    st.title("Microdrama Promo Finder")
    st.caption("Text-only screenplay analysis. Every visual judgment remains an inference.")

    source_zip = st.file_uploader("Upload a show ZIP", type=["zip"])
    source_files = st.file_uploader(
        "Or upload episode TXT files",
        type=["txt"],
        accept_multiple_files=True,
    )

    DEFAULT_MODELS = {
        "groq": "qwen/qwen3.8-27b",
        "gemini": "gemini-3.8-flash",
        "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
        "ollama": "llama3.2",
        "openai_compatible": "gpt-4o-mini",
    }
    provider = st.selectbox("Provider", list(DEFAULT_MODELS.keys()))
    default_model = DEFAULT_MODELS.get(provider, "gemini-3.8-flash")
    model = st.text_input("Model override", value=default_model, key=f"model_{provider}")
    api_key = st.text_input(
        "API key",
        type="password",
        help="Free key from console.groq.com or openrouter.ai; not needed for Ollama or Offline baseline",
    )
    offline = st.checkbox("Offline baseline (no API calls)")
    run = st.button("Find promos", type="primary")

    if run:
        if not source_zip and not source_files:
            st.error("Upload a ZIP or at least one episode TXT file.")
            return

        import importlib
        import sys
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("promo_finder"):
                try:
                    importlib.reload(sys.modules[mod_name])
                except Exception:
                    pass

        from promo_finder.pipeline import run_pipeline, load_config

        with tempfile.TemporaryDirectory(prefix="promo-finder-") as temp_dir:
            input_dir = Path(temp_dir) / "input"
            input_dir.mkdir()
            if source_zip:
                _safe_extract(source_zip, input_dir)
            else:
                _write_uploaded_files(source_files, input_dir)

            cfg, cfg_path = load_config()
            cfg["provider"] = provider
            # Route cache permanently to workspace cache folder so runs can resume!
            cfg["cache_dir"] = str(Path.cwd() / "cache")
            if provider not in cfg:
                cfg[provider] = {}
            for stage in ("stage1_model", "stage2_model", "rerank_model"):
                cfg[provider][stage] = model
            api_key = (api_key or "").strip()
            if not offline and provider in ("groq", "gemini", "openrouter", "openai_compatible") and not api_key:
                env_key = cfg[provider].get("api_key_env", f"{provider.upper()}_API_KEY")
                if not os.environ.get(env_key):
                    st.error(f"Please paste your {provider.capitalize()} API key in the 'API key' field.")
                    return
            if api_key:
                env_key = cfg[provider].get("api_key_env", f"{provider.upper()}_API_KEY")
                os.environ[env_key] = api_key
            config_file = Path(temp_dir) / "config.yaml"
            config_file.write_text(yaml.safe_dump(cfg), encoding="utf-8")

            import re
            import time
            import streamlit.components.v1 as components
            start_time = time.time()

            total_eps = len(list(input_dir.glob("*.txt"))) or 1
            timer_box = st.empty()
            with timer_box:
                components.html(
                    """
                    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; font-weight: 600; color: #f8fafc; display: flex; align-items: center; gap: 8px; margin: 0; padding: 0;">
                      <span>⏱ Elapsed Time:</span>
                      <span id="live_clock" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #1e293b; padding: 2px 8px; border-radius: 4px; color: #10b981; border: 1px solid #334155;">00:00</span>
                    </div>
                    <script>
                      const startTime = Date.now();
                      const clockEl = document.getElementById("live_clock");
                      setInterval(() => {
                        const elapsedSecs = Math.floor((Date.now() - startTime) / 1000);
                        const mins = String(Math.floor(elapsedSecs / 60)).padStart(2, '0');
                        const secs = String(elapsedSecs % 60).padStart(2, '0');
                        if (clockEl) {
                          clockEl.textContent = mins + ":" + secs;
                        }
                      }, 1000);
                    </script>
                    """,
                    height=32,
                )
            progress_bar = st.progress(0, text=f"Analyzing Episode 1 of {total_eps} (0%)...")
            last_pct = [0]

            def update_progress(msg: str):
                # Hide rate-limit cooldown messages completely from UI
                if "rate limit" in msg.lower() or "cooling down" in msg.lower():
                    return

                # 1. Episode extraction progress
                m = re.search(r"extracting episode \d+ \((\d+)/(\d+)\)", msg)
                if m:
                    curr, total = int(m.group(1)), int(m.group(2))
                    pct = int(((curr - 1) / max(total, 1)) * 70)
                    last_pct[0] = max(last_pct[0], pct)
                    progress_bar.progress(
                        min(last_pct[0], 100),
                        text=f"Analyzing Episode {curr} of {total} ({last_pct[0]}%)",
                    )
                    return

                # 2. Episodes finished
                if "Phase 3:" in msg or "raw candidates" in msg:
                    last_pct[0] = max(last_pct[0], 75)
                    progress_bar.progress(
                        last_pct[0],
                        text=f"All {total_eps} episodes analyzed! Validating promo clips ({last_pct[0]}%)",
                    )
                    return

                # 3. Deduplication / Combos
                if "Phase 5:" in msg or "Stage 2" in msg:
                    last_pct[0] = max(last_pct[0], 85)
                    progress_bar.progress(
                        last_pct[0],
                        text=f"Deduplicating & checking cross-episode combos ({last_pct[0]}%)",
                    )
                    return

                # 4. Final Ranking
                if "Phase 7" in msg or "Ranking" in msg:
                    last_pct[0] = max(last_pct[0], 95)
                    progress_bar.progress(
                        last_pct[0],
                        text=f"Ranking top promos by Hook & Cliffhanger ({last_pct[0]}%)",
                    )
                    return

                if "Pipeline complete" in msg or "Completed in" in msg:
                    last_pct[0] = 100
                    progress_bar.progress(100, text=f"Complete! All {total_eps} episodes analyzed (100%)")

            try:
                result = run_pipeline(
                    input_dir,
                    output_dir=Path(temp_dir) / "outputs",
                    config_path=config_file,
                    offline=offline,
                    repair_invalid=False,
                    log_callback=update_progress,
                )
                total_duration = time.time() - start_time
                mins, secs = divmod(int(total_duration), 60)
                timer_box.markdown(f"⏱ **Finished in:** `{mins:02d}:{secs:02d}` ({total_duration:.1f}s)")
                progress_bar.progress(100, text=f"Complete! All {total_eps} episodes analyzed (100%)")
            except Exception as exc:
                elapsed_fail = time.time() - start_time
                mins, secs = divmod(int(elapsed_fail), 60)
                timer_box.markdown(f"⏱ **Stopped at:** `{mins:02d}:{secs:02d}`")
                st.exception(exc)
                return

            st.session_state["last_result"] = result
            st.session_state["feedback_root"] = Path.cwd()

    result = st.session_state.get("last_result")
    if not result:
        return

    st.success(f"Ranked {result['ranked_candidates']} promos across all episodes.")
    
    col_dl1, col_dl2 = st.columns([1, 1])
    with col_dl1:
        st.download_button(
            "📥 Download Promos CSV",
            data=(Path("raw_outputs/promos.csv").read_text() if Path("raw_outputs/promos.csv").exists() else ""),
            file_name="promos.csv",
            mime="text/csv",
        )
    with col_dl2:
        st.download_button(
            "📥 Download Promos JSON",
            data=(Path("raw_outputs/promos.json").read_text() if Path("raw_outputs/promos.json").exists() else ""),
            file_name="promos.json",
            mime="application/json",
        )

    rows = []
    for candidate in result["ranked"]:
        segs = candidate.get("segments", [])
        seg_str = " + ".join(
            f"Ep {s.get('episode','?')} [{s.get('start','?')} → {s.get('end','?')}]"
            for s in segs
        )
        first_ep = segs[0].get("episode", "?") if segs else "?"
        first_start = segs[0].get("start", "?") if segs else "?"
        last_end = segs[-1].get("end", "?") if segs else "?"

        rows.append({
            "rank": candidate.get("rank"),
            "candidate_id": candidate.get("candidate_id"),
            "episode": first_ep if len(segs) <= 1 else ", ".join(str(s.get("episode")) for s in segs),
            "start_timestamp": first_start,
            "end_timestamp": last_end,
            "all_segments": seg_str,
            "duration_s": f"{candidate.get('duration_s', 0):.1f}s",
            "score": round(float(candidate.get("final_blended_score", 0)), 4),
            "hook": candidate.get("hook_quote"),
            "cliffhanger": candidate.get("cliffhanger_quote"),
            "why_it_works": candidate.get("why_it_works", ""),
            "post_order_rationale": candidate.get("post_first_because") or candidate.get("why_it_works", ""),
        })
    
    st.caption(f"Displaying all {len(rows)} ranked promos. Scroll vertically to inspect any row, click column headers to sort.")
    st.dataframe(rows, use_container_width=True, height=520)

    st.subheader("Human Editorial Review")
    col_rev1, col_rev2 = st.columns([2, 1])
    with col_rev1:
        st.caption("Review, approve, or adjust ranked promo candidates.")
    with col_rev2:
        review_count_choice = st.selectbox(
            "Show review cards:",
            [f"All {len(result['ranked'])} promos", "Top 10 promos", "Top 20 promos"],
            index=0,
        )
    if "Top 10" in review_count_choice:
        review_items = result["ranked"][:10]
    elif "Top 20" in review_count_choice:
        review_items = result["ranked"][:20]
    else:
        review_items = result["ranked"]

    for candidate in review_items:
        candidate_id = candidate["candidate_id"]
        segs = candidate.get("segments", [])
        seg_str = " + ".join(
            f"Episode {s.get('episode','?')} [{s.get('start','?')} → {s.get('end','?')}]"
            for s in segs
        )
        with st.expander(f"#{candidate.get('rank')} {candidate_id} — {seg_str} ({candidate.get('duration_s', 0):.1f}s)"):
            st.markdown(f"**📍 Segments & Timestamps:** `{seg_str}`")
            st.markdown(f"**⏱ Duration:** `{candidate.get('duration_s', 0):.1f}s` | **Score:** `{candidate.get('final_blended_score', 0):.3f}`")
            st.markdown(f"**🪝 Hook (first 3s):** *\"{candidate.get('hook_quote', '')}\"*")
            st.markdown(f"**🎬 Cliffhanger (unresolved):** *\"{candidate.get('cliffhanger_quote', '')}\"*")
            st.markdown(f"**💡 Why it works:** {candidate.get('why_it_works', 'Strong narrative hook and unresolved cliffhanger.')}")
            if candidate.get("post_first_because"):
                st.markdown(f"**🚀 Post first because:** {candidate.get('post_first_because')}")
            decision = st.radio(
                "Decision",
                ["approve", "reject", "adjust"],
                key=f"decision_{candidate_id}",
                horizontal=True,
            )
            note = st.text_input("Note", key=f"note_{candidate_id}")
            if st.button("Save review", key=f"save_{candidate_id}"):
                feedback_root = st.session_state.get("feedback_root", Path.cwd())
                _save_feedback(
                    feedback_root / "eval" / "editor_feedback.jsonl",
                    {
                        "candidate_id": candidate_id,
                        "decision": decision,
                        "note": note,
                        "segments": candidate.get("segments", []),
                    },
                )
                st.success("Saved.")


if __name__ == "__main__":
    main()

