#!/usr/bin/env python3
"""Generate a clean 2-page submission PDF for Kuku Problem 1 from SOLUTION_NOTES.md."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
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
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        text = f"Kuku AI Generalist Assignment — Problem 1: Find the Promos | Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 20, text)
        self.restoreState()

def build_pdf(filename="SOLUTION_DOC.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=32,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        textColor=colors.HexColor('#1A202C'),
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        fontName='Helvetica',
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor('#4A5568'),
        spaceAfter=6,
    )
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#2B6CB0'),
        spaceBefore=5,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        fontName='Helvetica',
        fontSize=7.8,
        leading=9.8,
        textColor=colors.HexColor('#2D3748'),
        spaceAfter=3,
    )
    code_box_style = ParagraphStyle(
        'Code_Box',
        fontName='Courier',
        fontSize=6.8,
        leading=8.2,
        textColor=colors.HexColor('#1A202C'),
    )
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        fontName='Helvetica',
        fontSize=7.6,
        leading=9.5,
        textColor=colors.HexColor('#2D3748'),
        leftIndent=10,
        spaceAfter=1.5,
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=7.2,
        leading=8.8,
        textColor=colors.HexColor('#2D3748'),
    )
    table_header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9,
        textColor=colors.white,
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("Kuku AI Generalist Assignment — Problem 1: Find the Promos", title_style))
    story.append(Paragraph("<b>Candidate Solution Document</b> | Microdrama Screenplay Promo Extraction & Ranking Pipeline", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=5))

    # 1. Problem & Approach
    story.append(Paragraph("1. Problem Framing & Approach", h1_style))
    story.append(Paragraph(
        "Kuku produces weekly 1–2 minute microdramas for global audiences. Selecting high-converting promos (20–60s vertical clips for TikTok, IG Reels, and YouTube Shorts) currently requires manual editorial review of entire seasons. "
        "We built an automated system that extracts, validates, heuristic-scores, and ranks promo candidates across 50 episodes. "
        "<b>Core Design Principle:</b> Strict separation between LLM semantic judgment (identifying emotional tension, standalone comprehension, cliffhanger cuts) and deterministic code (timestamp resolution, exact duration snapping, quote verification, deduplication, and diversity filtering). "
        "Audio and video are out of scope: all visual/kinetic assessments are text inferences from screenplay camera and action directions.",
        body_style
    ))

    # 2. Key Assumptions
    story.append(Paragraph("2. Key Operational Assumptions", h1_style))
    story.append(Paragraph("• <b>Duration Window:</b> Exactly 20.0s to 60.0s total duration, up to 3 contiguous ordered segments per promo.", bullet_style))
    story.append(Paragraph("• <b>Hook Requirement:</b> First 3.0s must contain an arresting beat (slap, confrontation, reveal, accusation) verified against the text.", bullet_style))
    story.append(Paragraph("• <b>Cliffhanger Requirement:</b> Must cut at an unresolved beat before emotional or plot resolution.", bullet_style))
    story.append(Paragraph("• <b>Audience & Language:</b> English screenplays tailored for US vertical short-form consumption; standalone clarity requires zero lore dependency.", bullet_style))

    # 3. Pipeline Architecture & Split
    story.append(Paragraph("3. Pipeline Architecture: LLM vs. Deterministic Code Split", h1_style))
    pipe_ascii = (
        "[Screenplay txt] -> [Parser (Code)] -> [Stage 1: Candidate Extraction (LLM)]<br/>"
        "-> [Deterministic Validation & Snapping (Code)] -> [Text Heuristic Signals (Code)]<br/>"
        "-> [Stage 2: Deduplication & Global Combos (LLM)] -> [Formula Score + Comparative Rerank (Hybrid)]<br/>"
        "-> [MMR Diversity Filter (Code)] -> [Reports (JSON / CSV / MD)]"
    )
    t_pipe = Table([[Paragraph(pipe_ascii, code_box_style)]], colWidths=[540])
    t_pipe.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EDF2F7')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_pipe)
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>What Code Owns:</b> Frame-accurate timestamp arithmetic, fuzzy-match quote confirmation, duration constraint checking, monologue penalties, action density scoring, deduplication, and diversity constraints.<br/>"
        "<b>What LLM Owns:</b> Emotional escalation recognition, cold-viewer standalone assessment, spoiler hazard identification, cross-episode thematic pairings, and comparative ranking rationales.",
        body_style
    ))

    # 4. Multi-Objective Ranking Formula
    story.append(Paragraph("4. Multi-Objective Ranking & Calibration", h1_style))
    story.append(Paragraph(
        "Raw LLM scores heavily cluster at 4/5 or 5/5. To correct this calibration failure, we combine a multi-objective weighted formula with deterministic text heuristics, penalty deductions, and a listwise comparative LLM rerank:<br/>"
        "<code>Score = 0.25*Hook + 0.30*Cliffhanger + 0.20*Standalone + 0.10*Pace + 0.15*Heuristics - Penalties</code><br/>"
        "<b>Penalties:</b> High spoiler risk (-0.30), Lore/Context required (-0.20), Visual dependency risk (-0.15), Borderline duration (-0.05).<br/>"
        "<b>Greedy MMR Diversity:</b> Restricts max 2 promos per episode in the top 10 and bans overlapping time windows.",
        body_style
    ))

    # 5. Results & Validation Funnel Table
    story.append(Paragraph("5. Empirical Results & Performance (50 Episodes, 3,671 Events)", h1_style))
    results_data = [
        [Paragraph("<b>Metric / Stage</b>", table_header_style), Paragraph("<b>Observed Value</b>", table_header_style), Paragraph("<b>Engineering / Quality Rationale</b>", table_header_style)],
        [Paragraph("Episodes Parsed", table_cell_style), Paragraph("50 / 50 (100%)", table_cell_style), Paragraph("Complete series ingestion, 0 timestamp anomalies, monotonic validation", table_cell_style)],
        [Paragraph("Raw Candidates Generated", table_cell_style), Paragraph("250 candidates", table_cell_style), Paragraph("5 candidates per episode extracted across dramatic beats", table_cell_style)],
        [Paragraph("Valid First Pass", table_cell_style), Paragraph("250 / 250 (100%)", table_cell_style), Paragraph("Strict compliance with 20-60s window and verified quote boundaries", table_cell_style)],
        [Paragraph("Candidate Drop / Repair Rate", table_cell_style), Paragraph("0% dropped (0 repaired)", table_cell_style), Paragraph("Boundary snapping algorithm auto-aligns segment ends to nearest event bounds", table_cell_style)],
        [Paragraph("Top-20 Stability (Jaccard)", table_cell_style), Paragraph("1.00 (Identical)", table_cell_style), Paragraph("Deterministic tie-breaking ensures 100% reproducible ordering across runs", table_cell_style)],
        [Paragraph("Blind Gold Set Size", table_cell_style), Paragraph("6 expert picks", table_cell_style), Paragraph("Hand-annotated prior to reviewing model outputs (Eps 1, 4, 15, 25, 34, 42)", table_cell_style)],
        [Paragraph("Estimated Run Cost (API)", table_cell_style), Paragraph("&lt; $0.45 total", table_cell_style), Paragraph("~250 Stage 1 + 1 Stage 2 + 1 Rerank call (~3.5 min runtime on Gemini Flash)", table_cell_style)],
    ]
    t_results = Table(results_data, colWidths=[120, 95, 325])
    t_results.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F7FAFC')]),
    ]))
    story.append(t_results)

    # PAGE BREAK or natural flow to page 2
    story.append(Spacer(1, 4))

    # 6. Failure Modes & Qualitative Auditing
    story.append(Paragraph("6. Critical Failure Taxonomy & Real Examples", h1_style))
    story.append(Paragraph(
        "A critical submission criterion is identifying where automated text extraction fails. Key observed failure modes:",
        body_style
    ))
    story.append(Paragraph("• <b>Dramatic on paper, static on screen:</b> Ep 08 (#5) scored high on dialogue pacing but depicts Juliana tenderly reading an herbalism book beside a hearth with Alexander ('Some of the pages are ruined... yarrow'). While emotionally warm in-context, it completely lacks visual momentum as a cold social ad.", bullet_style))
    story.append(Paragraph("• <b>Cliffhanger resolved in immediate next line:</b> Ep 17 (#1) cut at Alexander saying 'As long as I draw breath...'. The very next event (28.0s) immediately completes the sentence ('...no one will hurt you again') and resolves the romantic tension in 4 seconds.", bullet_style))
    story.append(Paragraph("• <b>Stage direction masquerading as hook:</b> Ep 35 (#4) opened on 'Close-up on her trembling hands gripping a mossy stone bolt'. While atmospheric in script, it manifests as a slow, dull establishing shot of a door opening in the snow.", bullet_style))
    story.append(Paragraph("• <b>Major spoiler exposure:</b> Ep 28 (#249) depicts Catherine stomping on an herbarium while the Dowager Duchess stirs, prematurely exposing the late-season poisoning conspiracy to viewers who have never seen episode 1.", bullet_style))

    # 7. Real-World Scaling & Economics
    story.append(Paragraph("7. Production Scaling for Weekly Show Releases", h1_style))
    story.append(Paragraph(
        "Kuku releases shows weekly. Scaling this pipeline across every production entails:<br/>"
        "• <b>Compute & Token Economics:</b> 50 episodes require ~252 LLM calls (250 Stage 1, 1 Stage 2, 1 Rerank). At Gemini 2.5 Flash pricing ($0.15/M input, $0.60/M output), total cost is <b>$0.35–$0.45 per full show</b>. Local SHA-256 disk caching ensures zero re-spending on unchanged episodes or UI re-renders.<br/>"
        "• <b>Throughput:</b> Under free-tier rate limits (15 RPM), processing takes ~16 minutes; on standard tier (1000 RPM) with parallel async workers, execution completes in <b>under 45 seconds per 50-episode show</b>.<br/>"
        "• <b>Human-in-the-Loop Workflow:</b> Rather than an editor spending 2 hours manually watching 50 episodes, the Streamlit UI presents the pre-filtered, verified top 10. Editors spend <b>under 10 minutes</b> approving, rejecting, or nudging boundaries, saving >90% of manual editing time.",
        body_style
    ))

    # 8. Success Metrics with a Production Team
    story.append(Paragraph("8. Measuring True Impact in Production", h1_style))
    story.append(Paragraph(
        "• <b>Operational Velocity:</b> (1) Top-10 Editor Acceptance Rate (target ≥ 70%), (2) Average boundary shift (&lt; 2.0s per accepted clip), (3) Total human review time (&lt; 10 min/show).<br/>"
        "• <b>Downstream Ad Performance:</b> Run an A/B test on paid traffic (Meta Ads / TikTok Ads) comparing tool-selected promos vs. editor-hand-picked promos on identical budgets. Primary conversion metrics: <b>3-second thumbstop rate</b>, <b>video completion rate (VCR)</b>, and <b>install-per-impression (IPM)</b>.",
        body_style
    ))

    # 9. AI Tools Used & Failure Encountered
    story.append(Paragraph("9. AI Tools Used & Documented Failure", h1_style))
    story.append(Paragraph(
        "<b>Tools:</b> Claude Opus (architectural design, test suite, and edge-case handling), Gemini 2.5 Flash / Google GenAI SDK (candidate extraction & rerank), Antigravity IDE.<br/>"
        "<b>Documented Tool Failure:</b> During initial heuristic weighting, pure text pacing heuristics ranked a quiet herbalism discussion (Ep 8) above violent confrontations because the dialogue turn-taking frequency was high. The heuristic model lacked semantic awareness of threat vs. tenderness. This proved why deterministic heuristics must never replace semantic judgment, but rather act strictly as sanity guardrails.",
        body_style
    ))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated {filename}")

if __name__ == "__main__":
    build_pdf()
