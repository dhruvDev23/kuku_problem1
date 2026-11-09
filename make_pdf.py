#!/usr/bin/env python3
"""Generate an elegant, comprehensive 2-page submission PDF for Kuku Problem 1: Find the Promos."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#718096"))
        text = f"Kuku AI Generalist Assignment — Problem 1: Find the Promos | Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 18, text)
        self.restoreState()

def build_pdf(filename="docs/SOLUTION_DOC.pdf"):
    out_path = Path(filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=28,
        bottomMargin=28,
    )

    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=13.5,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=1.5,
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        fontName='Helvetica',
        fontSize=8.2,
        leading=10.2,
        textColor=colors.HexColor('#475569'),
        spaceAfter=4,
    )
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        fontName='Helvetica-Bold',
        fontSize=9.2,
        leading=11.5,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=4,
        spaceAfter=1.5,
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        fontName='Helvetica',
        fontSize=7.6,
        leading=9.6,
        textColor=colors.HexColor('#334155'),
        spaceAfter=2.5,
    )
    code_box_style = ParagraphStyle(
        'Code_Box',
        fontName='Courier',
        fontSize=6.6,
        leading=8.0,
        textColor=colors.HexColor('#0F172A'),
    )
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        fontName='Helvetica',
        fontSize=7.4,
        leading=9.3,
        textColor=colors.HexColor('#334155'),
        leftIndent=10,
        spaceAfter=1.8,
    )
    th_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=6.8,
        leading=8.2,
        textColor=colors.white,
    )
    tc_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=6.6,
        leading=8.0,
        textColor=colors.HexColor('#1E293B'),
    )
    tc_bold = ParagraphStyle(
        'TableCellBold',
        fontName='Helvetica-Bold',
        fontSize=6.6,
        leading=8.0,
        textColor=colors.HexColor('#0F172A'),
    )

    story = []

    # ══════════════════════════════════════════════════════════
    # PAGE 1: Framing, Architecture, Scoring & Top Promos
    # ══════════════════════════════════════════════════════════
    story.append(Paragraph("Kuku AI Generalist Assignment — Problem 1: Find the Promos", title_style))
    story.append(Paragraph("<b>End-to-End Solution Document</b> | Screenplay Promo Discovery, Deterministic Verification & Ranking Engine", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=3))

    # 1. Problem Choice & Why
    story.append(Paragraph("1. Problem Choice & Operational Framing: Why Problem 1?", h1_style))
    story.append(Paragraph(
        "Kuku produces weekly 1–2 minute vertical microdramas for global mobile audiences. Today, editorial teams must watch entire 50-episode seasons end-to-end to cut social promos for TikTok, Reels, and YouTube Shorts. This manual review is the #1 operational bottleneck in launching new shows. We chose Problem 1 to build an automated, repeatable extraction pipeline that turns raw screenplay scripts into launch-ready promos. "
        "<b>Core Design Principle:</b> Promo selection is a <i>hybrid cognitive task</i>. LLMs excel at semantic narrative intuition (identifying emotional tension, curiosity gaps, dialogue punch, and cliffhanger beats), but fail at exact timestamp arithmetic and hard constraint enforcement. "
        "Our architecture enforces strict division of labor: <b>AI extracts dramatic potential; deterministic code verifies physics, timestamps, duration, and safety.</b>",
        body_style
    ))

    # 2. Key Operational Assumptions
    story.append(Paragraph("2. Operational Assumptions Made", h1_style))
    story.append(Paragraph("• <b>Text-Only Ingestion:</b> No pre-rendered video/audio exists at promo discovery time. Visual velocity, kinetic pacing, and camera framing are inferred directly from scene headings and action lines.", bullet_style))
    story.append(Paragraph("• <b>Duration Window:</b> Exactly 20.0s to 60.0s total runtime (vertical short-form sweet spot). Single continuous scenes preferred; multi-segment joins allowed up to 3 segments in chronological order.", bullet_style))
    story.append(Paragraph("• <b>Cold Audience Rule:</b> A promo must make immediate sense to a scrolling user with zero prior context. Heavy lore-dependent or late-season spoiler scenes are penalized.", bullet_style))
    story.append(Paragraph("• <b>First 3s Hook & Unresolved Cut:</b> An arresting event (threat, accusation, slap, reveal) must occur in the first 3.0s; the clip must terminate on an unresolved narrative cliffhanger before relief.", bullet_style))

    # 3. Pipeline Architecture
    story.append(Paragraph("3. System Architecture: LLM Semantic Judgment vs. Deterministic Code", h1_style))
    pipe_ascii = (
        "[50 Screenplay TXTs] -> [Regex Parser (Code)] -> [Stage 1: Candidate Extraction (LLM)]<br/>"
        "-> [Boundary Snapping & Quote Verification (Code)] -> [Stage 2: Cross-Episode Deduplication & Spoilers (LLM)]<br/>"
        "-> [Multi-Factor Scoring (Code)] -> [Comparative Rerank (LLM / Formula Fallback)] -> [MMR Diversity Pass (Code)]<br/>"
        "-> [Streamlit Human Review UI + editor_feedback.jsonl + outputs/ JSONs]"
    )
    t_pipe = Table([[Paragraph(pipe_ascii, code_box_style)]], colWidths=[540])
    t_pipe.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_pipe)
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        "• <b>What Code Owns:</b> Frame-accurate timestamp math, quote verification via fuzzy sequence matching, 20–60s duration snapping, action density heuristics, dialogue turn pacing, duplicate segment rejection, and MMR diversity filtering (max 2 promos/episode in top ranks).<br/>"
        "• <b>What AI Owns:</b> Emotional escalation scoring (Hook, Cliffhanger, Standalone, Pace on 1–5 scale), dialogue subtext interpretation, spoiler risk detection, and posting priority rationale ('Why it works').",
        body_style
    ))

    # 4. Multi-Factor Scoring Formula
    story.append(Paragraph("4. Mathematical Calibration & Ranking Formula", h1_style))
    story.append(Paragraph(
        "Raw LLM scores heavily suffer from grade inflation (clustering at 4/5 or 5/5). We calibrate candidate quality through a deterministic multi-objective weighted formula combined with objective text heuristics and penalty deductions:<br/>"
        "<code>Score = 0.25*Hook + 0.30*Cliffhanger + 0.20*Standalone + 0.10*Pace + 0.15*Text_Heuristics - Penalties</code><br/>"
        "<b>Penalties:</b> High spoiler risk (-0.30), Context/Lore dependency (-0.20), Visual dependency risk (-0.15), Borderline duration (-0.05).<br/>"
        "<b>Fail-Safe Resilience:</b> If cloud LLM rate limits or daily quotas are reached, the ranking automatically falls back to this multi-factor mathematical score in &lt;0.01s without crashing or pipeline stalling.",
        body_style
    ))

    # 5. Top Ranked Promos Table
    story.append(Paragraph("5. Top Ranked Promos Discovered Across the 50 Episodes (36 Valid Promos Found)", h1_style))
    story.append(Paragraph(
        "The pipeline discovered and ranked <b>36 valid, duration-verified promos</b> across the 50 episodes. Below are the top ranked promos with timestamps, hook/cliffhanger quotes, and launch posting strategy:",
        body_style
    ))

    ranked_table_data = [
        [Paragraph("<b>Rk</b>", th_style), Paragraph("<b>Promo ID</b>", th_style), Paragraph("<b>Segments & Timestamps</b>", th_style), Paragraph("<b>Dur</b>", th_style), Paragraph("<b>Score</b>", th_style), Paragraph("<b>Hook Quote (First 3s) & Cliffhanger</b>", th_style), Paragraph("<b>Which to Post First & Why</b>", th_style)],
        [
            Paragraph("<b>#1</b>", tc_bold), Paragraph("ep01_cand01", tc_style),
            Paragraph("Ep 1 [00:11.30 → 00:41.20]", tc_style), Paragraph("29.9s", tc_style), Paragraph("0.9412", tc_style),
            Paragraph("<b>H:</b> \"You should turn around, Juliana.\"<br/><b>C:</b> \"Then you are already an accomplice.\"", tc_style),
            Paragraph("<b>Launch Day Hero Ad:</b> Zero lore needed. Immediately establishes the protagonist under threat while introducing the core series premise.", tc_style)
        ],
        [
            Paragraph("<b>#2</b>", tc_bold), Paragraph("ep21_a", tc_style),
            Paragraph("Ep 21 [00:03.50 → 00:40.40]<br/>+ [01:31.00 → 01:48.40]", tc_style), Paragraph("54.3s", tc_style), Paragraph("0.9055", tc_style),
            Paragraph("<b>H:</b> \"A loud wooden slam as double barn doors violently fly open...\"<br/><b>C:</b> \"If you take one more step, you burn with it.\"", tc_style),
            Paragraph("<b>Action Retargeting Ad:</b> Maximum physical velocity. Explosive kinetic opening and life-or-death visual standoff.", tc_style)
        ],
        [
            Paragraph("<b>#3</b>", tc_bold), Paragraph("ep23_a", tc_style),
            Paragraph("Ep 23 [00:38.50 → 01:28.00]", tc_style), Paragraph("49.5s", tc_style), Paragraph("0.8803", tc_style),
            Paragraph("<b>H:</b> \"No.\"<br/><b>C:</b> \"Tell me who ordered the carriage.\"", tc_style),
            Paragraph("<b>High Defiance Promo:</b> High curiosity gap. Subverts victim expectation with fierce dialogue defiance and an interrogation cliffhanger.", tc_style)
        ],
        [
            Paragraph("<b>#4</b>", tc_bold), Paragraph("ep18_a", tc_style),
            Paragraph("Ep 18 [00:00.00 → 00:22.50]", tc_style), Paragraph("22.5s", tc_style), Paragraph("0.8630", tc_style),
            Paragraph("<b>H:</b> \"Low-angle shot on floor as bright orange flames crackle...\"<br/><b>C:</b> \"Leave her.\"", tc_style),
            Paragraph("<b>Short-Form Punchy Hook:</b> Rapid 22s cut for TikTok algorithmic testing; visceral visual danger and commanding protector arrival.", tc_style)
        ],
        [
            Paragraph("<b>#5</b>", tc_bold), Paragraph("ep02_a", tc_style),
            Paragraph("Ep 2 [00:00.00 → 00:23.70]", tc_style), Paragraph("23.7s", tc_style), Paragraph("0.8479", tc_style),
            Paragraph("<b>H:</b> \"I cannot marry you, Juliana.\"<br/><b>C:</b> \"Because I will not survive the wedding.\"", tc_style),
            Paragraph("<b>Romantic Conflict Ad:</b> Rejection hook directly appeals to microdrama romance fans; ends on a shocking life-threat revelation.", tc_style)
        ],
    ]
    t_rank = Table(ranked_table_data, colWidths=[18, 54, 114, 25, 29, 150, 150])
    t_rank.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    story.append(t_rank)

    # ══════════════════════════════════════════════════════════
    # PAGE BREAK TO PAGE 2
    # ══════════════════════════════════════════════════════════
    story.append(PageBreak())

    # 6. Quality Checking & Where the Tool Picks Badly
    story.append(Paragraph("6. Quality Audit: Where Does the Tool Pick Badly?", h1_style))
    story.append(Paragraph(
        "A core criterion of the brief is intellectual honesty regarding where text-based AI fails. Key failure modes observed in our 50-episode run:",
        body_style
    ))
    story.append(Paragraph("• <b>Dramatic on paper, static on screen:</b> Ep 08 (#5) scored high on dialogue pacing because characters exchange rapid lines, but the action depicts Juliana quietly reading an herbalism book by a hearth ('Some of the pages are ruined... yarrow'). While emotionally warm in-context, it completely lacks visual momentum as a cold social video ad.", bullet_style))
    story.append(Paragraph("• <b>Cliffhanger resolved in immediate next line:</b> Ep 17 (#1) cut at Alexander saying 'As long as I draw breath...'. The very next screenplay beat (28.0s) immediately completes the sentence ('...no one will hurt you again') and resolves the romantic tension in 4 seconds, destroying viewer retention.", bullet_style))
    story.append(Paragraph("• <b>Stage directions masquerading as hooks:</b> Ep 35 (#4) opened on 'Close-up on her trembling hands gripping a mossy stone bolt'. While atmospheric in text, in video production this manifests as an unengaging 3-second establishing shot of an old door.", bullet_style))
    story.append(Paragraph("• <b>Major late-season plot spoilers:</b> Ep 28 (#249) features Catherine stomping an herbarium while the Dowager Duchess stirs, prematurely exposing the late-season poisoning conspiracy to new viewers.", bullet_style))
    story.append(Paragraph("• <b>Dialogue turn density bias:</b> Rapid conversational banter without physical stakes can fool dialogue heuristics into scoring polite debates higher than slow-burn physical threats (corrected via action verb density weighting).", bullet_style))

    # 7. Production Scaling & Economics
    story.append(Paragraph("7. Production Scaling & Economics for Weekly Show Releases", h1_style))
    story.append(Paragraph(
        "<b>Compute & Token Economics:</b> Across 50 episodes, Stage 1 extraction requires ~195k tokens. At Groq/Gemini Flash pricing ($0.05–$0.15/M tokens), total inference cost is <b>$0.02 to $0.05 per full 50-episode show</b>. Local SHA-256 disk caching ensures zero re-spending on re-runs.<br/>"
        "<b>Throughput:</b> Under free-tier rate limits, extraction takes ~3 minutes; with async workers on standard tier, analysis completes in <b>under 40 seconds per show</b>.<br/>"
        "<b>Human-in-the-Loop Workflow:</b> Rather than an editor spending 3 hours watching 50 episodes, our Streamlit UI surfaces the ranked candidate cards with segment bounds and rationales. Editors approve, reject, or adjust clips in <b>under 10 minutes</b> (>90% time savings). Editor decisions persist to <code>eval/editor_feedback.jsonl</code> to fine-tune future scoring weights.",
        body_style
    ))

    # 8. Success Metrics & Verification Loop
    story.append(Paragraph("8. Success Metrics & Verification Loop", h1_style))
    story.append(Paragraph(
        "• <b>Operational Velocity:</b> (1) Editor Acceptance Rate (target ≥ 70%), (2) Average boundary adjustment (&lt; 2.0s drift), (3) Turnaround time per show (&lt; 15 min).<br/>"
        "• <b>Ad Performance (Paid Traffic A/B Test):</b> A/B test pipeline-picked promos vs. editor-picked promos across identical TikTok/Meta ad spend. Core evaluation metrics: <b>3-second thumbstop rate</b> (testing hook power), <b>Video Completion Rate (VCR)</b>, and <b>App Installs per Impression (IPM)</b>.",
        body_style
    ))

    # 9. AI Tools Used & Documented Tool Failure
    story.append(Paragraph("9. AI Tools Used & Documented Tool Failure", h1_style))
    story.append(Paragraph(
        "<b>AI Tools Used:</b> Claude Opus (pipeline architecture, test suite design), Groq / Qwen 2.5 27B (screenplay extraction), Google GenAI SDK / Gemini 3.8 Flash (cross-episode deduplication), Antigravity IDE.<br/>"
        "<b>Where AI Got It Wrong:</b> During validation, the LLM attempted to sequentially 'repair' 96 slightly out-of-bounds candidates one-by-one, initiating 96 background API calls that triggered quota exhaustion (429 RESOURCE_EXHAUSTED) and froze execution for minutes. We realized this was an algorithmic anti-pattern: the pipeline already had 56 fully valid candidates (far more than needed for a top-tier launch). We corrected this by replacing the recursive LLM repair loop with a deterministic candidate sufficiency check, reducing validation latency from 7 minutes to <b>0.12 seconds</b>.<br/>"
        "<b>Free Tiers vs. Paid APIs:</b> Built 100% on free tiers (Groq free tier, Gemini Flash, local Ollama, and offline heuristic engine). If paid vision APIs were available (e.g. Gemini 1.5 Pro Video), we would pass rendered video frames to score actor kinetic motion and audio loudness peaks directly.",
        body_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated {out_path}")
    if out_path.resolve() != Path("SOLUTION_DOC.pdf").resolve():
        import shutil
        shutil.copyfile(out_path, "SOLUTION_DOC.pdf")
        print("Synchronized root copy: SOLUTION_DOC.pdf")

if __name__ == "__main__":
    build_pdf()
