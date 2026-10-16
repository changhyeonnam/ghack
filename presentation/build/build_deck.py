"""Fill the AI Builder Cup submission template with LedgerLens content."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
import copy, os

# Submission links: fill these in before the final build.
VIDEO_URL = "TBD"  # public YouTube link to the demo video (3 to 4 minutes)
APP_URL = "TBD"    # Cloud Run URL of the public demo (cache_only mode)

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = HERE + "/img"
SHOTS = HERE + "/shots"
prs = Presentation(HERE + "/template_plus2.pptx")

INK = RGBColor(0x0F, 0x3D, 0x4C)
TEAL = RGBColor(0x2A, 0x7F, 0x8E)
TINT = RGBColor(0xE6, 0xF2, 0xF4)
AMBER = RGBColor(0xE0, 0xA1, 0x00)
AMBER_T = RGBColor(0xFF, 0xF3, 0xCC)
RED = RGBColor(0xB3, 0x26, 0x1E)
GREY = RGBColor(0x5F, 0x63, 0x68)
LINE = RGBColor(0xD5, 0xDB, 0xDE)
TXT = RGBColor(0x20, 0x21, 0x24)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PANEL = RGBColor(0xF7, 0xF9, 0xFA)
FONT = "Arial"

# ---------- helpers ----------

def set_title(slide, text):
    """Replace the template heading text (keeps its run formatting)."""
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            p = sh.text_frame.paragraphs[0]
            p.runs[0].text = text
            for r in p.runs[1:]:
                r.text = ""
            return sh
    return None


def tb(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, margin=0.05):
    """paras: list of dicts {t, size, bold, color, bullet, italic, align, space_after}"""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    first = True
    for pd in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = pd.get("align", PP_ALIGN.LEFT)
        if pd.get("space_after") is not None:
            p.space_after = Pt(pd["space_after"])
        if pd.get("space_before") is not None:
            p.space_before = Pt(pd["space_before"])
        runs = pd["t"] if isinstance(pd["t"], list) else [(pd["t"], {})]
        for txt, ro in runs:
            r = p.add_run()
            r.text = txt
            f = r.font
            f.name = FONT
            f.size = Pt(ro.get("size", pd.get("size", 11)))
            f.bold = ro.get("bold", pd.get("bold", False))
            f.italic = ro.get("italic", pd.get("italic", False))
            f.color.rgb = ro.get("color", pd.get("color", TXT))
        if pd.get("bullet"):
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(int(Inches(0.16))))
            pPr.set("indent", str(-int(Inches(0.16))))
            from pptx.oxml.ns import qn
            bu = pPr.makeelement(qn("a:buChar"), {"char": "•"})
            pPr.append(bu)
    return box


def card(slide, x, y, w, h, fill=WHITE, line=LINE, lw=1.0, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line; s.line.width = Pt(lw)
    s.shadow.inherit = False
    from pptx.oxml.ns import qn
    st = s._element.find(qn("p:style"))
    if st is not None:
        s._element.remove(st)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.text_frame.text = ""
    return s


def pill(slide, x, y, w, h, text, fill=INK, color=WHITE, size=8):
    s = card(slide, x, y, w, h, fill=fill, line=None, radius=0.5)
    tf = s.text_frame
    tf.margin_left = tf.margin_right = Inches(0.04); tf.margin_top = tf.margin_bottom = Inches(0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = text
    r.font.name = FONT; r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = color
    return s


def table(slide, x, y, w, h, rows, col_w, font=9.5, header_fill=INK, zebra=True, bold_first_col=False):
    nrows, ncols = len(rows), len(rows[0])
    gt = slide.shapes.add_table(nrows, ncols, Inches(x), Inches(y), Inches(w), Inches(h))
    t = gt.table
    # strip default style banding look by setting fills explicitly
    tblPr = t._tbl.tblPr
    tblPr.set("bandRow", "0"); tblPr.set("firstRow", "0")
    for i, cw in enumerate(col_w):
        t.columns[i].width = Inches(cw)
    for ri, row in enumerate(rows):
        t.rows[ri].height = Inches(h / nrows)
        for ci, val in enumerate(row):
            c = t.cell(ri, ci)
            c.margin_left = c.margin_right = Inches(0.06)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            if ri == 0:
                c.fill.fore_color.rgb = header_fill
            else:
                c.fill.fore_color.rgb = PANEL if (zebra and ri % 2 == 0) else WHITE
            tf = c.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]
            r = p.add_run(); r.text = str(val)
            r.font.name = FONT; r.font.size = Pt(font)
            r.font.bold = (ri == 0) or (bold_first_col and ci == 0)
            r.font.color.rgb = WHITE if ri == 0 else TXT
    return gt


def picture(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)


slides = list(prs.slides)
S = {i + 1: s for i, s in enumerate(slides)}  # template numbering

# ---------- Slide 1: Team details ----------
s = S[1]
for sh in s.shapes:
    if sh.has_text_frame and "Team Details" in sh.text_frame.text:
        ps = sh.text_frame.paragraphs
        fills = {"Team name: ": "Team name: Hey Merlion!", "Team leader name: ": "Team leader name: Changhyeon Nam (team: Changhyeon Nam, Hyunho Yang)",
                 "Problem Statement:": "Problem Statement: BFSI: Intelligent Risk, Fraud & Financial Experiences"}
        for p in ps:
            key = next((k for k in fills if p.runs and p.runs[0].text.strip() == k.strip()), None)
            if key:
                p.runs[0].text = fills[key]
                for r in p.runs[1:]:
                    r.text = ""
                p.runs[0].font.size = Pt(16)

# Redesigned slides (big numbers, cards, hero screenshots) inside the official template.
MONO = "Courier New"

def eyebrow(slide, text, y=1.22):
    tb(slide, 0.3, y, 9.4, 0.3, [{"t": text.upper(), "size": 9, "bold": True, "color": TEAL}])

def headline(slide, text, y=1.5, size=19, h=0.75):
    tb(slide, 0.3, y, 9.4, h, [{"t": text, "size": size, "bold": True, "color": INK}])

def bignum(slide, x, y, w, text, size=30, color=INK):
    tb(slide, x, y, w, size / 72 * 1.3, [{"t": text, "size": size, "bold": True, "color": color}], margin=0.0)

# ---------- Slide 2: Why this matters (the problem) ----------
s = S[2]
set_title(s, "Why this matters")
eyebrow(s, "The problem", y=1.18)
headline(s, "Banks are ready to lend on cash flow, but reading the records by hand costs too much, and the numbers a plain AI writes cannot be traced back to a page.", y=1.4, size=16.5, h=0.72)
# persona
card(s, 0.3, 2.25, 2.95, 3.0, fill=PANEL, line=LINE)
tb(s, 0.45, 2.33, 2.7, 0.3, [{"t": "MEET LINH", "size": 8.5, "bold": True, "color": TEAL}], margin=0.0)
tb(s, 0.45, 2.58, 2.7, 0.45, [{"t": "Shopee seller, Vietnam", "size": 14, "bold": True, "color": INK}], margin=0.0)
tb(s, 0.45, 3.02, 2.65, 1.45, [
    {"t": "Asks for VND 150M of working capital. Her sales are real.", "size": 10, "color": TXT, "space_after": 5},
    {"t": "She brings 14 documents: a bank statement PDF, monthly Shopee dashboard screenshots, supplier receipts, photos of the shop.", "size": 10, "color": TXT}], margin=0.0)
card(s, 0.45, 4.24, 2.65, 0.76, fill=AMBER_T, line=AMBER, lw=1.2)
tb(s, 0.57, 4.26, 2.45, 0.72, [{"t": "No credit file. No collateral.", "size": 11, "bold": True, "color": INK, "space_after": 2},
                              {"t": "Today her file is declined, or priced blind.", "size": 9.5, "color": RED}], anchor=MSO_ANCHOR.MIDDLE, margin=0.0)
tb(s, 0.45, 5.06, 2.7, 0.18, [{"t": "Synthetic demo case B", "size": 7, "italic": True, "color": GREY}], margin=0.0)
# causal chain
chain = [("8.8%", "of Vietnam's SMEs have a bank loan; large firms: 47.1%. Without a credit file or collateral, small firms are declined.", False),
         ("75.5%", "of Vietnamese firms cannot borrow without collateral, so banks are moving to cash-flow lending (VPBank, Vietcombank, Agribank).", False),
         ("~45 min", "to read and verify one file by hand. For a small loan, the reading costs more than the loan earns.", False),
         ("77%", "of the numbers in a memo written by a single Gemini prompt point to no page, so the underwriter has to find each one again. That prompt also caught only 15% of the planted risks.", True)]
x0 = 3.45; rh = 0.69; gy = 0.08; y = 2.25
card(s, x0 + 0.2, 2.45, 0.03, 4 * rh + 3 * gy - 0.4, fill=LINE, line=None, radius=0.0)
for i, (big, d, acc) in enumerate(chain):
    pill(s, x0 + 0.05, y + rh / 2 - 0.17, 0.34, 0.34, str(i + 1), fill=AMBER if acc else INK, color=INK if acc else WHITE, size=10)
    card(s, x0 + 0.52, y, 9.7 - x0 - 0.52, rh, fill=AMBER_T if acc else WHITE, line=AMBER if acc else LINE, lw=1.4 if acc else 1)
    tb(s, x0 + 0.65, y + 0.04, 1.2, rh - 0.08, [{"t": big, "size": 20, "bold": True, "color": INK}], anchor=MSO_ANCHOR.MIDDLE, margin=0.0)
    tb(s, x0 + 1.9, y + 0.04, 9.6 - x0 - 1.9, rh - 0.08, [{"t": d, "size": 9.5, "color": TXT}], anchor=MSO_ANCHOR.MIDDLE, margin=0.0)
    y += rh + gy
tb(s, 0.3, 5.28, 9.4, 0.22, [{"t": "Sources: 1 FiinGroup via Viet Nam News (Aug 2026) · 2 VCCI 2025 via VTV (May 2026) · 3 team estimate; ADB Asia SME Monitor 2025 · 4 our live benchmark, gemini-3.8-flash", "size": 7, "italic": True, "color": GREY}], margin=0.0)

# ---------- Slide 4: Brief about the idea (the solution) ----------
s = S[4]
set_title(s, "Brief about the idea")
eyebrow(s, "The solution", y=1.18)
headline(s, "LedgerLens reads the shoebox, shows its work, and argues against itself before a human signs.", y=1.4, size=18, h=0.7)
mech = [("1", "Read with evidence", "Answers: reading cost",
         "Gemini reads every page. Each value carries document, page and bounding box. Python computes the cash flow. A memo with an unsourced number is rejected and regenerated.",
         "14 documents, every figure sourced to a page and box, in about 2 minutes.", False),
        ("2", "Challenge", "Answers: AI trust",
         "A separate agent that never sees the writer's prompt runs deterministic checks and 12 underwriting questions, then ranks objections with evidence.",
         "Flags a reused receipt photo and VND 82.5M of own-account transfers counted as income.", True),
        ("3", "Human signs", "Keeps: accountability",
         "The underwriter accepts or dismisses each objection and signs. Every agent call is logged; decisions re-weight the next run.",
         "Linh gets the decision and the conditions to meet, in Vietnamese.", False)]
x = 0.3; cw = 2.95
for n, t, tag, d, case, acc in mech:
    card(s, x, 2.2, cw, 2.75, fill=AMBER_T if acc else WHITE, line=AMBER if acc else LINE, lw=1.5 if acc else 1)
    pill(s, x + 0.16, 2.33, 0.38, 0.38, n, fill=AMBER if acc else INK, color=INK if acc else WHITE, size=11)
    tb(s, x + 0.64, 2.3, cw - 0.75, 0.3, [{"t": t, "size": 14, "bold": True, "color": INK}], margin=0.0)
    tb(s, x + 0.64, 2.56, cw - 0.75, 0.2, [{"t": tag.upper(), "size": 7.5, "bold": True, "color": AMBER if acc else TEAL}], margin=0.0)
    tb(s, x + 0.16, 2.88, cw - 0.32, 1.25, [{"t": d, "size": 9.5, "color": TXT}], margin=0.0)
    card(s, x + 0.12, 4.12, cw - 0.24, 0.72, fill=WHITE if acc else TINT, line=None, radius=0.08)
    tb(s, x + 0.22, 4.15, cw - 0.44, 0.67, [{"t": [("In Linh's file: ", {"bold": True, "color": INK}), (case, {})], "size": 9, "color": TXT}], anchor=MSO_ANCHOR.MIDDLE, margin=0.0)
    if n != "3":
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + cw + 0.04), Inches(3.4), Inches(0.2), Inches(0.28))
        a.fill.solid(); a.fill.fore_color.rgb = RGBColor(0xB9, 0xC6, 0xC3); a.line.fill.background(); a.shadow.inherit = False
        from pptx.oxml.ns import qn as _qn
        _st = a._element.find(_qn("p:style"))
        if _st is not None: a._element.remove(_st)
    x += cw + 0.275
tb(s, 0.3, 5.05, 9.4, 0.4, [{"t": [("Grounded only in the applicant's documents. ", {"bold": True, "color": INK}), ("Guardrails: output schema, deterministic checks, a second agent, a human signature.", {})], "size": 10.5, "color": GREY}], margin=0.0)

# ---------- Slide 5: Opportunities (the impact) ----------
s = S[5]
sh = set_title(s, "Opportunities")
for p in sh.text_frame.paragraphs[1:]:
    for r in p.runs:
        r.text = ""
sh.height = Inches(0.5)
eyebrow(s, "Expected impact", y=1.18)
headline(s, "What changes, and for whom.", y=1.4, size=19, h=0.45)
cols = [("For the lender", "45 → 2", "minutes per file", "USD ~11 → 0.28 per case. Small-ticket loans become worth underwriting.", False),
        ("For the small business", "Cash flow", "not collateral, decides the loan", "Assessed on the records she already has. A no comes with reasons, in her own language.", False),
        ("For risk and audit", "77% → 0%", "of memo numbers with no page", "Every figure points to a page and box, so nothing is re-checked by hand. Planted risks caught: 90% vs 15%.", True)]
x = 0.3; cw = 3.0
for who, big, unit, d, acc in cols:
    card(s, x, 1.95, cw, 2.05, fill=AMBER_T if acc else WHITE, line=AMBER if acc else LINE, lw=1.5 if acc else 1)
    pill(s, x + 0.16, 2.07, 1.85, 0.28, who, fill=AMBER if acc else INK, color=INK if acc else WHITE, size=8.5)
    tb(s, x + 0.16, 2.45, cw - 0.3, 0.7, [{"t": big, "size": 32, "bold": True, "color": INK}], margin=0.0)
    tb(s, x + 0.16, 3.12, cw - 0.3, 0.3, [{"t": unit, "size": 10.5, "bold": True, "color": TEAL}], margin=0.0)
    tb(s, x + 0.16, 3.45, cw - 0.3, 0.75, [{"t": d, "size": 9.5, "color": TXT}], margin=0.0)
    x += cw + 0.2
card(s, 0.3, 4.15, 9.4, 0.55, fill=INK, line=None, radius=0.08)
tb(s, 0.45, 4.17, 9.1, 0.51, [{"t": [("USP   ", {"bold": True, "color": AMBER}), ("The writer and the verifier are separate agents · numbers are computed by code, never generated · every number clicks back to its source line · decisions re-weight the checks", {"color": WHITE})], "size": 9.5}], anchor=MSO_ANCHOR.MIDDLE, margin=0.0)
tb(s, 0.3, 4.82, 9.4, 0.4, [{"t": [("Back to the 8.8%: ", {"bold": True, "color": INK}), ("when reading a file costs cents and minutes instead of an hour, the loans banks decline today become worth making.", {})], "size": 11, "color": GREY}], margin=0.0)
tb(s, 0.3, 5.3, 9.4, 0.2, [{"t": "Manual baseline (45 min at USD 15/h) is a team estimate. A number counts as untraceable when no document and page stand behind it; correctness was not measured. Live gemini-3.8-flash on a small synthetic sample.", "size": 7, "italic": True, "color": GREY}], margin=0.0)

# ---------- Slide 6: Features ----------
s = S[6]
set_title(s, "List of features offered by the solution")
headline(s, "Every feature hangs on one pipeline, and the pipeline ends with a person.", y=1.22, size=18, h=0.5)
feats = [("Intake", "Multimodal intake", "PDF, screenshots, photos. Classified and quality-flagged.", False),
         ("Extract", "Evidence-linked extraction", "Doc id, page, bbox on every value. PDF text layer verifies it.", False),
         ("Cash flow", "Deterministic model", "Inflow, outflow, trend, volatility, debt service. Python, not the model.", False),
         ("Analyze", "Clickable memo", "Cites catalog figures only. Click one, the source line opens.", False),
         ("Challenge", "Battery + 12 checks", "Image hash, balance chain, dates. Ranked objections with evidence.", True),
         ("Decide", "Underwriter workbench", "Accept or dismiss, sign. Audit log. Decisions re-weight the checks.", False),
         ("Explain", "Letter and paper memo", "Customer letter in the local language. Memo prints with footnoted sources.", False)]
n = len(feats); gap = 0.1; cw = (9.4 - gap * (n - 1)) / n
x = 0.3
# spine
card(s, 0.3, 1.98, 9.4, 0.04, fill=INK, line=None, radius=0.0)
for stage, t, d, acc in feats:
    pill(s, x + 0.1, 1.86, cw - 0.2, 0.28, stage, fill=AMBER if acc else INK, color=INK if acc else WHITE, size=8.5)
    card(s, x, 2.3, cw, 2.75, fill=AMBER_T if acc else WHITE, line=AMBER if acc else LINE, lw=1.5 if acc else 1)
    tb(s, x + 0.1, 2.4, cw - 0.2, 0.8, [{"t": t, "size": 11.5, "bold": True, "color": INK}], margin=0.0)
    tb(s, x + 0.1, 3.25, cw - 0.2, 1.75, [{"t": d, "size": 9.5, "color": TXT}], margin=0.0)
    x += cw + gap
tb(s, 0.3, 5.12, 9.4, 0.3, [{"t": [("Out of scope by design: ", {"bold": True, "color": INK}), ("credit scoring, loan pricing, core-banking integration. LedgerLens informs the decision; it does not make it.", {})], "size": 9.5, "color": GREY}])

# ---------- Slide 8: Wireframes -> the moment ----------
s = S[8]
set_title(s, "Wireframes / Mock diagrams of the proposed solution")
eyebrow(s, "The product in one interaction", y=1.18)
tb(s, 0.3, 1.4, 9.4, 0.5, [{"t": "Click the number. See the line.", "size": 26, "bold": True, "color": INK}], margin=0.0)
_sc = 3.4 / 460
_p = picture(s, f"{SHOTS}/v2_evidence_c.jpg", 0.3, 1.95, h=3.4); _p.line.color.rgb = LINE; _p.line.width = Pt(0.75)
marks = [(148, 72), (318, 88), (592, 118)]
for i, (px, py) in enumerate(marks):
    cx = 0.3 + px * _sc; cy = 1.95 + py * _sc
    pill(s, cx - 0.15, cy - 0.15, 0.3, 0.3, str(i + 1), fill=AMBER, color=INK, size=10)
steps8 = [("The memo cites a figure", "Every underlined value is a catalog figure with a source. Here: VND 82,500,000, credits from the applicant's own accounts."),
          ("One click opens the evidence", "The computation (sum of 3 credits whose sender matches the account holder) and all 3 source references: pages 2, 4 and 5."),
          ("The source line lights up", "The statement page opens with the extractor's bounding box drawn on the exact row. A memo with an unsourced number is rejected and regenerated.")]
y = 1.95
for i, (t, d) in enumerate(steps8):
    acc = i == 2
    card(s, 5.2, y, 4.5, 1.05, fill=AMBER_T if acc else WHITE, line=AMBER if acc else LINE, lw=1.5 if acc else 1)
    pill(s, 5.34, y + 0.14, 0.34, 0.34, str(i + 1), fill=AMBER if acc else INK, color=INK if acc else WHITE, size=11)
    tb(s, 5.8, y + 0.1, 3.8, 0.4, [{"t": t, "size": 13.5, "bold": True, "color": INK}], anchor=MSO_ANCHOR.MIDDLE, margin=0.0)
    tb(s, 5.34, y + 0.5, 4.25, 0.55, [{"t": d, "size": 9.5, "color": TXT}], margin=0.0)
    y += 1.15

# ---------- Slide 10: Technologies ----------
s = S[10]
set_title(s, "Technologies to be used in the solution")
headline(s, "Gemini reads, ADK orchestrates, Python computes, Cloud Run serves.", y=1.22, size=18, h=0.5)
tech = [("Google Cloud", "Gemini 3.8 Flash", "Default for every agent. Measured USD 0.26-0.31 per cold case; USD 0 cached.", False),
        ("Google Cloud", "Gemini 3.1 Pro", "One env var moves Extractor, Analyst and Challenger to Pro.", False),
        ("Google Cloud", "ADK on Cloud Run", "Agent Platform: Intake, 5 Extractors, Analyst, Challenger (investigator, writer), Explainer.", False),
        ("Google Cloud", "Cloud Run + Firebase", "FastAPI backend scales to zero; React workbench on Firebase Hosting.", False),
        ("Google Cloud", "Firestore + Storage", "Cases, extractions, memos, objections, decisions, audit, traces; documents.", False),
        ("Python", "Deterministic tools", "Cash-flow model, balance chain, image hash, PDF text-layer cross-check, date and entity checks.", False),
        ("Python", "LLM cache, budget cap", "Content-hash cache per model and prompt version; hard USD cap per process.", False),
        ("Integration", "REST API", "Any loan origination system can create cases, run stages and read memos.", True)]
cw, chh, gx, gy = 2.27, 1.55, 0.1, 0.12
for i, (tag, name, desc, acc) in enumerate(tech):
    r, c = divmod(i, 4)
    x = 0.3 + c * (cw + gx); y = 1.8 + r * (chh + gy)
    card(s, x, y, cw, chh, fill=AMBER_T if acc else WHITE, line=AMBER if acc else LINE, lw=1.5 if acc else 1)
    tb(s, x + 0.14, y + 0.1, cw - 0.28, 0.25, [{"t": tag.upper(), "size": 7.5, "bold": True, "color": AMBER if acc or tag == "Python" else TEAL}], margin=0.0)
    tb(s, x + 0.14, y + 0.33, cw - 0.28, 0.4, [{"t": name, "size": 11.5, "bold": True, "color": INK}], margin=0.0)
    tb(s, x + 0.14, y + 0.72, cw - 0.28, 0.8, [{"t": desc, "size": 9, "color": GREY}], margin=0.0)
tb(s, 0.3, 5.15, 9.4, 0.3, [{"t": "Grounding: only the applicant's documents; every value must carry source {doc_id, page, bbox}. No separate OCR: Gemini reads rendered pages.", "size": 9, "italic": True, "color": GREY}])

# ---------- Slide 13: Benchmark ----------
s = S[13]
set_title(s, "Prototype performance report / Benchmarking")
headline(s, "LedgerLens caught 90% of the planted risks on live Gemini output; a single prompt on the same documents caught 15%.", y=1.22, size=17, h=0.7)
# hero numbers
card(s, 0.3, 1.95, 4.5, 2.0, fill=AMBER_T, line=AMBER, lw=1.5)
tb(s, 0.45, 2.0, 2.2, 0.3, [{"t": "LEDGERLENS", "size": 9, "bold": True, "color": AMBER}], margin=0.0)
tb(s, 0.45, 2.4, 2.3, 1.0, [{"t": "90%", "size": 60, "bold": True, "color": INK}], margin=0.0)
tb(s, 0.45, 3.4, 2.2, 0.5, [{"t": "of planted risks caught", "size": 11, "color": TXT}, {"t": "small synthetic sample, read as indicative", "size": 8.5, "color": GREY}], margin=0.0)
tb(s, 2.75, 2.0, 2.0, 0.3, [{"t": "SINGLE PROMPT", "size": 9, "bold": True, "color": GREY}], margin=0.0)
tb(s, 2.75, 2.4, 2.0, 1.0, [{"t": "15%", "size": 60, "bold": True, "color": RGBColor(0xB0, 0xB8, 0xBE)}], margin=0.0)
tb(s, 2.75, 3.4, 2.0, 0.5, [{"t": "same documents", "size": 11, "color": GREY}, {"t": "and same model", "size": 8.5, "color": GREY}], margin=0.0)
card(s, 0.3, 4.1, 2.2, 1.25, fill=WHITE, line=LINE)
tb(s, 0.42, 4.15, 2.0, 0.6, [{"t": "100%", "size": 30, "bold": True, "color": INK}], margin=0.0)
tb(s, 0.42, 4.75, 2.0, 0.55, [{"t": "of memo numbers trace to a page (single prompt: 23%)", "size": 9.5, "color": GREY}], margin=0.0)
card(s, 2.6, 4.1, 2.2, 1.25, fill=WHITE, line=LINE)
tb(s, 2.72, 4.15, 2.0, 0.6, [{"t": "~2 min", "size": 30, "bold": True, "color": INK}], margin=0.0)
tb(s, 2.72, 4.75, 2.0, 0.55, [{"t": "per case cold, USD 0.26-0.31; cached re-run USD 0", "size": 9.5, "color": GREY}], margin=0.0)
rows = [["Metric", "Target", "Result"],
        ["Risks caught (strict)", "≥ 80%", "90% (single prompt: 15%)"],
        ["Traceable numbers", "100%", "100% (single prompt: 23%)"],
        ["Objections on clean case A", "≤ 20%", "none"],
        ["Extraction row accuracy*", "≥ 97%", "100%"],
        ["Evidence-link accuracy*", "≥ 95%", "100%"],
        ["Time per case (cold)", "≤ 180 s", "~2 min"],
        ["Cost per case (cold)", "≤ USD 0.50", "USD 0.26-0.31"]]
table(s, 5.0, 1.95, 4.7, 2.25, rows, [1.85, 0.8, 2.05], font=9, bold_first_col=True)
card(s, 5.0, 4.28, 4.7, 1.12, fill=PANEL, line=LINE)
tb(s, 5.1, 4.31, 4.52, 1.08, [{"t": [("How measured. ", {"bold": True}), ("Live gemini-3.8-flash runs, 2026-10-15/16, on three synthetic businesses with team-planted risks. Strict scoring: an objection counts only if it carries the risk's identifying amount or document, one objection per risk. ", {}), ("Traceable = a memo number with a document and page behind it; correctness not measured. The sample is small, so read every percentage as indicative. Missed: dashboard gross vs payout, COD vs cash deposits. Recommendation matched on C; A gave approve_with_conditions (expected approve), B request_more_documents (expected approve_with_conditions). *Clean born-digital synthetic PDFs; real scans will be lower.", {})], "size": 7.5, "color": TXT}], margin=0.0)

# ---------- Slide 6: Process flow ----------
s = S[7]
set_title(s, "Process flow diagram")
picture(s, f"{IMG}/process_flow.png", 0.5, 1.28, h=3.8)
tb(s, 0.3, 5.12, 9.4, 0.3, [{"t": "Three lanes: the loan officer uploads, the agents read and challenge, the underwriter decides. Decisions flow back into the Challenger's priorities.", "size": 9.5, "italic": True, "color": GREY}])

# ---------- Slide 8: Architecture ----------
s = S[9]
set_title(s, "Architecture diagram of the proposed solution")
picture(s, f"{IMG}/architecture.png", 0.9, 1.28, h=3.95)


# ---------- Slide 11: Cost ----------
s = S[11]
set_title(s, "Estimated implementation cost")
tb(s, 0.3, 1.25, 9.4, 0.45, [{"t": "Measured: USD 0.26-0.31 per case on a cold Flash run, USD 0 on a cached re-run", "size": 14, "bold": True, "color": INK}])
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
cd = CategoryChartData()
cd.categories = ["LedgerLens cold run, case B (14 docs)", "LedgerLens cold run, case C (11 docs)", "Single-prompt baseline (no checks)", "LedgerLens cached re-run"]
cd.add_series("USD per case", (0.306, 0.257, 0.015, 0.0))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.3), Inches(1.75), Inches(5.7), Inches(3.5), cd)
ch = gf.chart; ch.has_legend = False; ch.has_title = True
ch.chart_title.text_frame.text = "Cost per case, USD (gemini-3.8-flash, live run 2026-10-15)"
tp = ch.chart_title.text_frame.paragraphs[0]; tp.runs[0].font.size = Pt(10.5); tp.runs[0].font.bold = True; tp.runs[0].font.color.rgb = INK; tp.runs[0].font.name = FONT
pl = ch.plots[0]; pl.has_data_labels = True; pl.gap_width = 55
pl.data_labels.number_format = '0.000'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(10.5); pl.data_labels.font.bold = True; pl.data_labels.font.color.rgb = INK; pl.data_labels.font.name = FONT
ser = pl.series[0]; ser.format.fill.solid(); ser.format.fill.fore_color.rgb = TEAL
for _i in (0, 1):
    _pt = ser.points[_i]; _pt.format.fill.solid(); _pt.format.fill.fore_color.rgb = AMBER
p2 = ser.points[2]; p2.format.fill.solid(); p2.format.fill.fore_color.rgb = RGBColor(0xB0, 0xB8, 0xBE)
ca = ch.category_axis; ca.tick_labels.font.size = Pt(9.5); ca.tick_labels.font.name = FONT; ca.tick_labels.font.color.rgb = TXT; ca.format.line.color.rgb = LINE; ca.has_major_gridlines = False
ca.reverse_order = True
va = ch.value_axis; va.visible = False; va.has_major_gridlines = False; va.maximum_scale = 0.38; va.minimum_scale = 0.0
rows = [["Assumption", "Value"],
        ["Gemini 3.8 Flash list price", "USD 0.75 / 3.75 per 1M tokens"],
        ["Measured cold run", "~2 min and USD 0.26-0.31 per case"],
        ["Cached re-run", "USD 0 (content-hash LLM cache)"],
        ["Public demo", "Replays the recorded live Gemini run, USD 0; only the customer letter calls Gemini (~USD 0.0015)"],
        ["Hosting", "Cloud Run scales to zero; Firestore and Storage in free tier"],
        ["Guardrail", "Budget-cap env var stops Gemini calls once spent"],
        ["Build", "2 engineers, 4 days, free tier and trial credits"]]
table(s, 6.3, 1.8, 3.4, 3.4, rows, [1.35, 2.05], font=8.5, bold_first_col=True)

def framed(slide, path, x, y, w=None, h=None):
    p = picture(slide, path, x, y, w=w, h=h)
    p.line.color.rgb = LINE; p.line.width = Pt(0.75)
    return p

# ---------- Slide 12: Snapshots, end to end ----------
s = S[12]
set_title(s, "Snapshots of the prototype")
shots = [("v2_newcase.jpg", "1", "New case", "Applicant details, then the raw documents. Intake classifies and quality-flags them."),
         ("v2_evidence_c.jpg", "2", "Click a number, see the line", "Evidence panel with computation and all sources; the statement opens with the bounding box highlighted."),
         ("v2_receipt_c.jpg", "3", "Challenger objections", "Critical: two receipt photos are the same image with an edited date. Evidence chips open the photo."),
         ("v2_decision_c.jpg", "4", "The underwriter signs", "Outcome, conditions and rationale, written to the audit log; accept/dismiss rates re-weight the checks.")]
for i, (f, n, t, d) in enumerate(shots):
    r, c = divmod(i, 2)
    x = 0.3 + c * 3.45; y = 1.3 + r * 2.1
    framed(s, f"{SHOTS}/{f}", x, y, h=1.95)
    pill(s, x + 0.08, y + 0.08, 0.28, 0.28, n, fill=AMBER, size=9)
cy = 1.3
for f, n, t, d in shots:
    pill(s, 7.25, cy + 0.02, 0.28, 0.28, n, fill=AMBER, size=9)
    tb(s, 7.6, cy - 0.04, 2.1, 0.4, [{"t": t, "size": 11, "bold": True, "color": INK}])
    tb(s, 7.25, cy + 0.34, 2.45, 0.72, [{"t": d, "size": 8.5, "color": GREY}])
    cy += 1.06

# ---------- Slide 14: Future development ----------
s = S[14]
set_title(s, "Additional details / Future development")
picture(s, f"{IMG}/roadmap.png", 0.3, 1.3, w=9.4)
tb(s, 0.3, 5.05, 9.4, 0.4, [{"t": "Humans decide, every figure and decision is traceable, the prototype uses watermarked synthetic data only, and production keeps documents and model endpoints in-region.", "size": 9.5, "italic": True, "color": GREY}])

# ---------- Slide 14: Links ----------
s = S[15]
sh = set_title(s, "Provide links to your:")
for p in sh.text_frame.paragraphs[1:]:
    for r in p.runs:
        r.text = ""
sh.height = Inches(0.5)
links = [("GitHub public repository", "github.com/changhyeonnam/ghack", "English README, architecture, run instructions, synthetic-data notice, presentation/"),
         ("Demo video (3 to 4 minutes)", VIDEO_URL, "Problem in 20 seconds, click-to-source and Challenger scenes, benchmark near the end"),
         ("Final product", APP_URL, "Cloud Run service; each browser gets its own copy of the three demo cases (Reset demo). Scales to zero; demo cases replay the recorded live Gemini run (only the customer letter calls Gemini live), so judging costs nothing")]
y = 1.3
for t, u, d in links:
    card(s, 0.3, y, 9.4, 1.2, fill=PANEL, line=LINE)
    tb(s, 0.5, y + 0.15, 3.4, 0.5, [{"t": t, "size": 15, "bold": True, "color": INK}])
    tb(s, 0.5, y + 0.65, 3.4, 0.45, [{"t": u, "size": 12, "color": TEAL}])
    tb(s, 4.1, y + 0.15, 5.4, 0.95, [{"t": d, "size": 11.5, "color": GREY}], anchor=MSO_ANCHOR.MIDDLE)
    y += 1.33
tb(s, 0.3, 5.3, 9.4, 0.25, [{"t": "Links are inserted at submission on 18 October 2026.", "size": 10, "italic": True, "color": GREY}])

# ---------- Slide 16: Appendix, Challenger checks ----------
s = S[16]
src = [sh for sh in S[4].shapes if sh.has_text_frame and sh.text_frame.text.strip()][0]
new = copy.deepcopy(src._element)
s.shapes._spTree.append(new)
hd = s.shapes[-1]
hd.text_frame.paragraphs[0].runs[0].text = "Appendix: the Challenger's 12 fixed checks"
picture(s, f"{IMG}/checks_map.png", 0.3, 1.3, w=9.4)

# ---------- Slide 17: Appendix, more screens ----------
s = S[17]
set_title(s, "Appendix: portfolio, cash flow and audit views")
more = [("v2_portfolio.jpg", "Portfolio", "Cases in review, open objections and unsourced numbers across the book; filters by status."),
        ("v2_cashflow_c.jpg", "Cash flow", "Deterministic monthly model: inflow, net, trend, volatility, end-of-month share, repayment capacity."),
        ("v2_audit_c.jpg", "Audit timeline", "Every stage and agent call with version, model and prompt; the trail a regulator can read.")]
x = 0.3
for f, t, d in more:
    framed(s, f"{SHOTS}/{f}", x, 1.3, h=1.9)
    tb(s, x, 3.3, 3.05, 0.35, [{"t": t, "size": 12, "bold": True, "color": INK}])
    tb(s, x, 3.65, 3.05, 1.0, [{"t": d, "size": 9.5, "color": GREY}])
    x += 3.175
tb(s, 0.3, 4.8, 9.4, 0.5, [{"t": "Also in the build: dark and light themes, PDF text-layer cross-check on every extracted amount, content-hash LLM cache, cache_only demo mode, budget cap, printable paper memo with footnoted sources.", "size": 9.5, "italic": True, "color": GREY}])


# ---------- delete slide 3 (template instructions) (template instructions) ----------
sldIdLst = prs.slides._sldIdLst
ids = list(sldIdLst)
target = ids[2]
prs.part.drop_rel(target.rId)
sldIdLst.remove(target)

out = os.path.join(os.path.dirname(HERE), "LedgerLens_AI_Builder_Cup_Submission.pptx") if os.path.basename(HERE) == "build" else HERE + "/LedgerLens_AI_Builder_Cup_Submission.pptx"
prs.save(out)
print("saved", out)
