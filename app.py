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
    api_key = st.text_input("API key", type="password")
    provider = st.selectbox("Provider", ["gemini", "openai_compatible"])
    model = st.text_input("Model override", value="gemini-2.5-flash")
    offline = st.checkbox("Offline baseline (no API calls)")
    run = st.button("Find promos", type="primary")

    if run:
        if not source_zip and not source_files:
            st.error("Upload a ZIP or at least one episode TXT file.")
            return

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
            for stage in ("stage1_model", "stage2_model", "rerank_model"):
                cfg[provider][stage] = model
            if api_key:
                os.environ[cfg[provider]["api_key_env"]] = api_key
            config_file = Path(temp_dir) / "config.yaml"
            config_file.write_text(yaml.safe_dump(cfg), encoding="utf-8")

            progress = st.empty()
            try:
                result = run_pipeline(
                    input_dir,
                    output_dir=Path(temp_dir) / "outputs",
                    config_path=config_file,
                    offline=offline,
                    log_callback=progress.write,
                )
            except Exception as exc:
                st.exception(exc)
                return

            st.session_state["last_result"] = result
            st.session_state["feedback_root"] = Path.cwd()

    result = st.session_state.get("last_result")
    if not result:
        return

    st.success(f"Ranked {result['ranked_candidates']} promos.")
    rows = []
    for candidate in result["ranked"][:10]:
        rows.append({
            "rank": candidate.get("rank"),
            "candidate_id": candidate.get("candidate_id"),
            "duration_s": candidate.get("duration_s"),
            "score": candidate.get("final_blended_score"),
            "hook": candidate.get("hook_quote"),
            "cliffhanger": candidate.get("cliffhanger_quote"),
        })
    st.dataframe(rows, use_container_width=True)

    st.subheader("Human review")
    for candidate in result["ranked"][:10]:
        candidate_id = candidate["candidate_id"]
        with st.expander(f"#{candidate.get('rank')} {candidate_id}"):
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

