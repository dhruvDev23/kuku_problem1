# Microdrama Promo Finder 🎬

An AI tool that reads microdrama screenplays and automatically extracts, scores, and ranks the best 20–60 second promo clips for TikTok, Instagram Reels, and YouTube Shorts.

Built for the **Kuku AI Generalist Assignment (Problem 1)**.

---

## 🚀 Quick Start (Under 2 Minutes)

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/dhruvDev23/kuku_problem1.git
cd kuku_problem1

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt -r requirements-ui.txt
```

### 2. Launch the Web App

```bash
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`.

---

## 🖥️ How to Use the App

Follow these simple steps in the interactive Streamlit web interface:

### Step 1: Choose or Upload Screenplays
- **Default Show:** The app comes pre-loaded with all 50 episodes of the test show (*I Married a Broken Soldier. He was a Duke*) located in `data/show`.
- **Upload Custom Files:** You can also drag and drop new `episode-*.txt` screenplay files or a `.zip` archive using the file uploader.

### Step 2: Select Mode & Provider
- **Offline Mode (Fastest & Free):**
  - Check the box **"Offline baseline (no API calls)"**.
  - Runs in **~0.5 seconds** using local deterministic heuristics (action verb density, dialogue pace, ending punctuation) and cross-model evaluations. No API key needed!
- **AI Mode (Gemini / OpenAI):**
  - Choose **`gemini`** (default model: `gemini-3.8-flash`) or **`openai_compatible`**.
  - Enter your API key in the password box (or set `export GEMINI_API_KEY="..."` in your terminal).

### Step 3: Click "Find promos"
- Click the red **Find promos** button.
- A live progress bar will show the stages:
  1. Parsing screenplays & normalizing timestamps
  2. Extracting candidate scenes (Stage 1)
  3. Enforcing 20–60s duration & quote validation
  4. Deduplication & spoiler filtering (Stage 2)
  5. Multi-signal ranking (Hook + Cliffhanger + Standalone clarity)

### Step 4: View & Export Results
- **Ranked Promos Table:** View all 36 ranked promo clips across all 50 episodes. For each clip, you see:
  - Exact episode and start/end timestamps (e.g. `00:11.30 → 00:41.20`)
  - Clip duration (20s to 60s)
  - Overall quality score
  - Hook quote (first 3 seconds)
  - Unresolved cliffhanger quote
  - Why it works
  - Posting order strategy ("Which to post first and why")
- **Export Data:** Click **📥 Download Promos CSV** or **📥 Download Promos JSON** to save the outputs.

### Step 5: Human Editorial Review
- Scroll down to the **Human Editorial Review** section.
- Expand any promo card to inspect timestamps, quotes, and rationale.
- Select **Approve**, **Reject**, or **Adjust**, add editorial notes, and click **Save review** to log human feedback directly to `eval/editor_feedback.jsonl`.

---

## 💻 Alternative: Run from the Command Line (CLI)

If you prefer using the terminal instead of the web UI:

```bash
# 1. Run offline (instant, no API key required)
python find_promos.py data/show --offline

# 2. Run with Gemini AI
export GEMINI_API_KEY="your-api-key"
python find_promos.py data/show
```

Outputs will be saved directly into the `outputs/` directory.

---

## 📁 Key Assignment Deliverables

- 📄 **Solution Document (2-Page PDF):** [`SOLUTION_DOC.pdf`](SOLUTION_DOC.pdf) (also in [`docs/SOLUTION_DOC.pdf`](docs/SOLUTION_DOC.pdf))
  - Covers problem scoping, assumptions, system architecture, top-ranked promos, failure analysis, and scaling economics.
- 📦 **Raw Outputs (Full 50 Episodes):** [`raw_outputs/`](raw_outputs/)
  - `promos.json` & `promos.csv`: All 36 ranked promos with exact timestamps and quotes.
  - `ranked_report.md`: Human-readable report of top picks and posting strategy.
  - `validation_report.json` & `cost_report.json`: Quality verification and token spend audit.
- 🧪 **Automated Tests:**
  ```bash
  python -m pytest tests/ -q
  ```
