import tempfile
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

DARK = colors.HexColor('#0D0D0D')
ACCENT = colors.HexColor('#1A73E8')
GREEN = colors.HexColor('#1B8A4C')
RED = colors.HexColor('#C0392B')
AMBER = colors.HexColor('#D97706')
LIGHT_BG = colors.HexColor('#F8F9FA')
BORDER = colors.HexColor('#E0E0E0')
GOLD = colors.HexColor('#B8860B')
WHITE = colors.white

def make_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles['title'] = ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=22,
        textColor=DARK, alignment=TA_CENTER, spaceAfter=4, leading=28)
    styles['subtitle'] = ParagraphStyle('subtitle', fontName='Helvetica', fontSize=11,
        textColor=colors.HexColor('#555555'), alignment=TA_CENTER, spaceAfter=16)
    styles['section'] = ParagraphStyle('section', fontName='Helvetica-Bold', fontSize=13,
        textColor=ACCENT, spaceBefore=16, spaceAfter=6, leading=18)
    styles['body'] = ParagraphStyle('body', fontName='Helvetica', fontSize=10,
        textColor=DARK, leading=15, spaceAfter=6)
    styles['bold_body'] = ParagraphStyle('bold_body', fontName='Helvetica-Bold', fontSize=10,
        textColor=DARK, leading=15, spaceAfter=4)
    styles['small'] = ParagraphStyle('small', fontName='Helvetica', fontSize=9,
        textColor=colors.HexColor('#666666'), leading=13)
    styles['verdict'] = ParagraphStyle('verdict', fontName='Helvetica-BoldOblique', fontSize=11,
        textColor=GREEN, leading=16, spaceAfter=8, leftIndent=10)
    styles['winner_name'] = ParagraphStyle('winner_name', fontName='Helvetica-Bold', fontSize=16,
        textColor=GOLD, alignment=TA_CENTER, spaceAfter=4)
    styles['dissent'] = ParagraphStyle('dissent', fontName='Helvetica-Oblique', fontSize=10,
        textColor=RED, leading=14, spaceAfter=6, leftIndent=10)
    styles['data_point'] = ParagraphStyle('data_point', fontName='Helvetica', fontSize=10,
        textColor=DARK, leading=14, leftIndent=20, spaceAfter=3)

    return styles

def score_bar(score, max_score=10, width=12):
    filled = int((score / max_score) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {score}/10"

def generate_debate_pdf(question, realtime_data, round1, round2, final_result):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = make_styles()
    story = []
    now = datetime.now().strftime("%B %d, %Y — %H:%M UTC")

    # ── COVER ──────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("100 BRAIN DEBATE REPORT", styles['title']))
    story.append(Paragraph(f"Generated: {now}", styles['subtitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    # Question box
    q_data = [[Paragraph(f"<b>QUESTION:</b> {question}", styles['bold_body'])]]
    q_table = Table(q_data, colWidths=[16.5*cm])
    q_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EBF3FD')),
        ('TEXTCOLOR', (0,0), (-1,-1), DARK),
        ('PADDING', (0,0), (-1,-1), 12),
        ('ROUNDEDCORNERS', [6]),
        ('BOX', (0,0), (-1,-1), 0.5, ACCENT),
    ]))
    story.append(q_table)
    story.append(Spacer(1, 0.5*cm))

    # ── WINNER SECTION ─────────────────────────────────────
    winner = final_result.get("winner", {})
    story.append(Paragraph("WINNER", styles['section']))

    rating = winner.get('overall_rating', 0)
    conf = winner.get('confidence_level', 'N/A')
    conf_color = GREEN if conf == 'HIGH' else (AMBER if conf == 'MEDIUM' else RED)

    win_data = [
        [Paragraph(f"🏆 {winner.get('persona', 'Unknown')}", styles['winner_name'])],
        [Paragraph(f"Overall Rating: <b>{rating}/10</b>   |   Confidence: <b>{conf}</b>   |   {score_bar(rating)}", styles['bold_body'])],
    ]
    win_table = Table(win_data, colWidths=[16.5*cm])
    win_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FFFBEA')),
        ('PADDING', (0,0), (-1,-1), 10),
        ('BOX', (0,0), (-1,-1), 1, GOLD),
        ('LINEBELOW', (0,0), (0,0), 0.5, BORDER),
    ]))
    story.append(win_table)
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Final Verdict:", styles['bold_body']))
    story.append(Paragraph(winner.get('final_verdict', ''), styles['verdict']))

    story.append(Paragraph("Why This Argument Won:", styles['bold_body']))
    story.append(Paragraph(winner.get('why_won', ''), styles['body']))

    story.append(Paragraph("Key Data Points:", styles['bold_body']))
    for i, dp in enumerate(winner.get('key_data_points', []), 1):
        story.append(Paragraph(f"  {i}.  {dp}", styles['data_point']))

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Caveats & Conditions:", styles['bold_body']))
    story.append(Paragraph(winner.get('caveats', 'None specified'), styles['small']))

    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(f"<b>BOTTOM LINE:</b> {final_result.get('bottom_line', '')}", styles['verdict']))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))

    # ── TOP 5 DEBATERS ────────────────────────────────────
    story.append(Paragraph("TOP 5 DEBATERS", styles['section']))

    medals = ["🥇", "🥈", "🥉", "4th", "5th"]
    rank_colors = [
        colors.HexColor('#FFF8E1'),
        colors.HexColor('#F5F5F5'),
        colors.HexColor('#FBE9E7'),
        colors.HexColor('#F9F9F9'),
        colors.HexColor('#F9F9F9'),
    ]

    top5 = final_result.get("top_5", [])
    for i, d in enumerate(top5[:5]):
        score = d.get('score', 0)
        medal = medals[i] if i < len(medals) else str(i+1)
        bg = rank_colors[i] if i < len(rank_colors) else WHITE

        header = f"<b>{medal} {d.get('persona', '')}</b>   Score: {score}/10   {score_bar(score, width=8)}"
        rows = [
            [Paragraph(header, styles['bold_body'])],
            [Paragraph(f"<b>Position:</b> {d.get('position', '')}", styles['body'])],
            [Paragraph(f"<b>Strongest Argument:</b> {d.get('strongest_argument', '')}", styles['body'])],
            [Paragraph(f"<b>Weakness:</b> {d.get('weakness', '')}", styles['small'])],
        ]
        t = Table(rows, colWidths=[16.5*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 0.5, BORDER),
            ('LINEBELOW', (0,0), (0,0), 0.5, BORDER),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.2*cm))

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Strongest Dissenting View:", styles['bold_body']))
    story.append(Paragraph(final_result.get('dissenting_view', ''), styles['dissent']))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))

    # ── ROUND 1 SUMMARY ───────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("ROUND 1 — INITIAL POSITIONS (Top 20 shown)", styles['section']))
    story.append(Paragraph(
        "All 100 personas formed their initial position. Below are the top 20 by confidence score.",
        styles['small']
    ))
    story.append(Spacer(1, 0.3*cm))

    positions = round1.get("positions", [])
    if positions:
        positions_sorted = sorted(positions, key=lambda x: x.get('confidence', 0), reverse=True)[:20]
        table_data = [["#", "Persona", "Position", "Confidence", "Key Data"]]
        for p in positions_sorted:
            conf_val = p.get('confidence', 0)
            table_data.append([
                str(p.get('id', '')),
                Paragraph(p.get('persona', ''), styles['small']),
                Paragraph(p.get('position', ''), styles['small']),
                f"{conf_val}%",
                Paragraph(p.get('key_data_point', '')[:120], styles['small']),
            ])

        col_widths = [1*cm, 3.5*cm, 3.5*cm, 2*cm, 6.5*cm]
        r1_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        r1_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), ACCENT),
            ('TEXTCOLOR', (0,0), (-1,0), WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('PADDING', (0,0), (-1,-1), 5),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT_BG]),
            ('GRID', (0,0), (-1,-1), 0.3, BORDER),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(r1_table)
    else:
        story.append(Paragraph("Round 1 data not available in structured format.", styles['small']))

    # ── ROUND 2 CLASHES ───────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("ROUND 2 — TOP DEBATERS CLASH", styles['section']))

    top_debaters = round2.get("top_debaters", [])
    if top_debaters:
        for d in top_debaters[:10]:
            rows = [
                [Paragraph(f"<b>{d.get('persona', '')}</b>   Strength: {d.get('strength_score', 0)}/10   Updated Confidence: {d.get('updated_confidence', 0)}%", styles['bold_body'])],
                [Paragraph(f"<b>Original Position:</b> {d.get('original_position', '')}", styles['small'])],
                [Paragraph(f"<b>Counter Attack:</b> {d.get('counter_attack', '')}", styles['body'])],
                [Paragraph(f"<b>Defense:</b> {d.get('defense', '')}", styles['body'])],
                [Paragraph(f"<b>Key Evidence:</b> {d.get('key_evidence', '')}", styles['small'])],
            ]
            t = Table(rows, colWidths=[16.5*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,0), colors.HexColor('#F0F4FF')),
                ('BACKGROUND', (0,1), (-1,-1), WHITE),
                ('PADDING', (0,0), (-1,-1), 7),
                ('BOX', (0,0), (-1,-1), 0.5, BORDER),
                ('LINEBELOW', (0,0), (0,0), 0.5, ACCENT),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.2*cm))

        emerging = round2.get("emerging_consensus", "")
        if emerging:
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(f"<b>Emerging Consensus After Round 2:</b> {emerging}", styles['body']))

        eliminated = round2.get("eliminated", [])
        if eliminated:
            elim_text = ", ".join(eliminated[:8])
            story.append(Paragraph(f"<b>Eliminated Arguments:</b> {elim_text}", styles['small']))
    else:
        story.append(Paragraph("Round 2 data not available in structured format.", styles['small']))

    # ── REAL-TIME DATA USED ───────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Paragraph("REAL-TIME DATA USED IN DEBATE", styles['section']))
    clean_data = realtime_data[:1500].replace('<', '').replace('>', '').replace('&', 'and')
    story.append(Paragraph(clean_data, styles['small']))

    # ── FOOTER ────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        f"Generated by 100 Brain Debate Bot  •  Powered by Kimi K2.6 via NVIDIA + Tavily  •  {now}",
        styles['small']
    ))

    doc.build(story)
    return tmp.name
