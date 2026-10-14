"""Fill the AI Builder Cup submission template with LedgerLens content."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
import copy, os

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
        fills = {"Team name: ": "Team name: LedgerLens", "Team leader name: ": "Team leader name: Changhyeon (SK Telecom, AI CIC)",
                 "Problem Statement:": "Problem Statement: BFSI: Intelligent Risk, Fraud & Financial Experiences"}
        for p in ps:
            key = next((k for k in fills if p.runs and p.runs[0].text.strip() == k.strip()), None)
            if key:
                p.runs[0].text = fills[key]
                for r in p.runs[1:]:
                    r.text = ""
                p.runs[0].font.size = Pt(16)

# ---------- Slide 2: Why this matters ----------
s = S[2]
set_title(s, "Why this matters")
picture(s, f"{IMG}/problem_chain.png", 0.3, 1.25, w=9.4)
tb(s, 0.3, 5.22, 9.4, 0.3, [{"t": "Sources: IFC MSME Finance · FiinGroup via Viet Nam News, Aug 2026 · ADB Asia SME Monitor 2025 · Bank Indonesia, Aug 2026 · VCCI Private Economic Report 2025 and VTV, May 2026", "size": 8, "italic": True, "color": GREY}])

# ---------- Slide 4: Brief about the idea ----------
s = S[4]
set_title(s, "Brief about the idea")
picture(s, f"{IMG}/journey.png", 0.3, 1.3, w=9.4)
tb(s, 0.3, 5.05, 9.4, 0.4, [{"t": [("In one sentence: ", {"bold": True, "color": INK}), ("the first credit memo where every number can be clicked back to its source, and a second AI tries to break it before a human signs.", {"italic": True})], "size": 11, "color": TXT}])

# ---------- Slide 5: Opportunities ----------
s = S[5]
sh = set_title(s, "Opportunities")
for p in sh.text_frame.paragraphs[1:]:
    for r in p.runs:
        r.text = ""
sh.height = Inches(0.5)
picture(s, f"{IMG}/before_after.png", 0.3, 1.25, w=9.4)
card(s, 0.3, 4.85, 9.4, 0.55, fill=AMBER_T, line=AMBER, lw=1.2)
tb(s, 0.45, 4.88, 9.1, 0.5, [{"t": [("Why it is different: ", {"bold": True}), ("the memo is written by one agent and attacked by another, every figure is computed by code and linked to its source, and the underwriter's decisions re-rank the next run. A memo, not a score.", {})], "size": 10, "color": TXT}], anchor=MSO_ANCHOR.MIDDLE)

# ---------- Slide 6: Features ----------
s = S[6]
set_title(s, "List of features offered by the solution")
picture(s, f"{IMG}/feature_pipeline.png", 0.3, 1.3, w=9.4)
tb(s, 0.3, 5.05, 9.4, 0.35, [{"t": "Out of scope by design: credit scoring, loan pricing, core-banking integration. LedgerLens informs the decision; it does not make it.", "size": 9.5, "italic": True, "color": GREY}])

# ---------- Slide 6: Process flow ----------
s = S[7]
set_title(s, "Process flow diagram")
picture(s, f"{IMG}/process_flow.png", 0.5, 1.28, h=3.8)
tb(s, 0.3, 5.12, 9.4, 0.3, [{"t": "Three lanes: the loan officer uploads, the agents read and challenge, the underwriter decides. Decisions flow back into the Challenger's priorities.", "size": 9.5, "italic": True, "color": GREY}])

# ---------- Slide 8: Wireframes -> the underwriter's screen ----------
s = S[8]
set_title(s, "Wireframes / Mock diagrams of the proposed solution")
_p = picture(s, f"{SHOTS}/v2_memo.jpg", 0.3, 1.3, w=6.3); _p.line.color.rgb = LINE; _p.line.width = Pt(0.75)
callouts = [("1", "Memo with a recommendation", "Headline, conditions and every figure drafted by the Analyst, from catalog figures only"),
            ("2", "Underlined numbers are evidence", "Click one: the source page opens with the bounding box highlighted"),
            ("3", "Unsourced 0, in the header", "Enforced by the output schema; a miss becomes a Challenger objection"),
            ("4", "Pipeline, cost, calls", "Five stages with timings; USD and LLM-call counters per case; Export memo prints a paper memo")]
y = 1.3
for n, t, d in callouts:
    card(s, 6.85, y, 2.85, 0.95, fill=PANEL, line=LINE)
    pill(s, 6.97, y + 0.14, 0.3, 0.3, n, fill=INK, size=9)
    tb(s, 7.35, y + 0.08, 2.3, 0.4, [{"t": t, "size": 10.5, "bold": True, "color": INK}])
    tb(s, 6.97, y + 0.46, 2.65, 0.5, [{"t": d, "size": 8.5, "color": GREY}])
    y += 1.03
tb(s, 0.3, 5.26, 6.5, 0.25, [{"t": "Live prototype, case B: 14 documents, 130 figures, 0 unsourced, 12 objections.", "size": 8.5, "italic": True, "color": GREY}])

# ---------- Slide 8: Architecture ----------
s = S[9]
set_title(s, "Architecture diagram of the proposed solution")
picture(s, f"{IMG}/architecture.png", 0.4, 1.26, h=3.82)
tb(s, 0.3, 5.12, 9.4, 0.3, [{"t": "One Google Cloud project end to end. Every agent call is cached by content hash, so re-runs are free and deterministic.", "size": 10, "italic": True, "color": GREY}])

# ---------- Slide 10: Technologies ----------
s = S[10]
set_title(s, "Technologies to be used in the solution")
picture(s, f"{IMG}/tech_stack.png", 0.3, 1.3, w=9.4)
tb(s, 0.3, 5.1, 9.4, 0.35, [{"t": "Output schema requires source {doc_id, page, bbox} on every value. LEDGERLENS_MODEL_PRO=gemini-3.1-pro-preview switches the heavy agents to Pro.", "size": 9.5, "italic": True, "color": GREY}])

# ---------- Slide 11: Cost ----------
s = S[11]
set_title(s, "Estimated implementation cost")
tb(s, 0.3, 1.25, 9.4, 0.45, [{"t": "Cheap enough for small loans: about USD 0.10 per case on Flash, zero on a re-run", "size": 14, "bold": True, "color": INK}])
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
cd = CategoryChartData()
cd.categories = ["Manual review (45 min at USD 15/h)", "LedgerLens, Gemini 3.1 Pro upgrade", "LedgerLens, Gemini 3.8 Flash default", "LedgerLens, cached re-run"]
cd.add_series("USD per case", (11.25, 0.40, 0.10, 0.0))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.3), Inches(1.75), Inches(5.7), Inches(3.5), cd)
ch = gf.chart; ch.has_legend = False; ch.has_title = True
ch.chart_title.text_frame.text = "Cost per case, USD"
tp = ch.chart_title.text_frame.paragraphs[0]; tp.runs[0].font.size = Pt(10.5); tp.runs[0].font.bold = True; tp.runs[0].font.color.rgb = INK; tp.runs[0].font.name = FONT
pl = ch.plots[0]; pl.has_data_labels = True; pl.gap_width = 55
pl.data_labels.number_format = '0.00'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(10.5); pl.data_labels.font.bold = True; pl.data_labels.font.color.rgb = INK; pl.data_labels.font.name = FONT
ser = pl.series[0]; ser.format.fill.solid(); ser.format.fill.fore_color.rgb = TEAL
p0 = ser.points[0]; p0.format.fill.solid(); p0.format.fill.fore_color.rgb = RGBColor(0xB0, 0xB8, 0xBE)
p2 = ser.points[2]; p2.format.fill.solid(); p2.format.fill.fore_color.rgb = AMBER
ca = ch.category_axis; ca.tick_labels.font.size = Pt(9.5); ca.tick_labels.font.name = FONT; ca.tick_labels.font.color.rgb = TXT; ca.format.line.color.rgb = LINE; ca.has_major_gridlines = False
ca.reverse_order = True
va = ch.value_axis; va.visible = False; va.has_major_gridlines = False; va.maximum_scale = 13.5
rows = [["Assumption", "Value"],
        ["Gemini 3.8 Flash list price", "USD 0.75 / 3.75 per 1M tokens"],
        ["Gemini 3.1 Pro list price", "USD 2.00 / 12.00 per 1M tokens"],
        ["Tokens per 20-document case", "60-90k input, 15-25k output"],
        ["Hosting", "Cloud Run scales to zero; Firestore and Storage in free tier"],
        ["Guardrail", "Budget-cap env var stops Gemini calls once spent"],
        ["Build", "4 engineers, 4 days, free tier and trial credits"]]
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

# ---------- Slide 13: Benchmark ----------
s = S[13]
set_title(s, "Prototype performance report / Benchmarking")
tb(s, 0.3, 1.25, 9.4, 0.45, [{"t": "19 of 20 planted traps caught, zero unsourced numbers. A single prompt on the same documents caught none.", "size": 14, "bold": True, "color": INK}])
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
cd = CategoryChartData()
cd.categories = ["Planted traps caught (of 20)", "Unsourced numbers in memo"]
cd.add_series("Single prompt", (0, 6))
cd.add_series("LedgerLens", (19, 0))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.3), Inches(1.75), Inches(4.3), Inches(3.5), cd)
ch = gf.chart; ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False
ch.legend.font.size = Pt(9.5); ch.legend.font.name = FONT; ch.legend.font.color.rgb = TXT
ch.has_title = False
pl = ch.plots[0]; pl.has_data_labels = True; pl.gap_width = 80; pl.overlap = -10
pl.data_labels.number_format = '0'; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(11); pl.data_labels.font.bold = True; pl.data_labels.font.color.rgb = INK; pl.data_labels.font.name = FONT
pl.series[0].format.fill.solid(); pl.series[0].format.fill.fore_color.rgb = RGBColor(0xB0, 0xB8, 0xBE)
pl.series[1].format.fill.solid(); pl.series[1].format.fill.fore_color.rgb = AMBER
ca = ch.category_axis; ca.tick_labels.font.size = Pt(9.5); ca.tick_labels.font.name = FONT; ca.tick_labels.font.color.rgb = TXT; ca.format.line.color.rgb = LINE; ca.has_major_gridlines = False
va = ch.value_axis; va.visible = False; va.has_major_gridlines = False; va.maximum_scale = 22
rows = [["Metric", "Target", "Result"],
        ["Trap recall", "≥ 16 / 20", "19 / 20"],
        ["Unsourced numbers", "0", "0 (baseline 6)"],
        ["Objections on clean case A", "≤ 20%", "0"],
        ["Extraction row accuracy", "≥ 97%", "100%"],
        ["Evidence-link accuracy", "≥ 95%", "100%"],
        ["Time per case", "≤ 180 s", "4.5 s"],
        ["Cost per case", "≤ USD 0.50", "USD 0.00"]]
table(s, 4.85, 1.75, 4.85, 2.55, rows, [2.25, 1.1, 1.5], font=9, bold_first_col=True)
card(s, 4.85, 4.42, 4.85, 0.9, fill=AMBER_T, line=AMBER, lw=1.2)
tb(s, 4.98, 4.46, 4.6, 0.85, [{"t": [("How measured. ", {"bold": True}), ("Run of 2026-10-14 in mock mode: full pipeline plus the deterministic Challenger battery, no Gemini calls, 3 synthetic businesses, 43 documents, answer key traps.json. Baseline is a stub in this mode; a live Gemini 3.8 Flash run replaces both before submission.", {})], "size": 8.5, "color": TXT}])

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
links = [("GitHub public repository", "github.com/<team>/ledgerlens", "English README, architecture, run instructions, synthetic-data notice"),
         ("Demo video (3 minutes)", "YouTube public link", "Problem in 20 seconds, click-to-source and Challenger scenes, benchmark at 2:20"),
         ("Final product", "ledgerlens-<hash>.a.run.app", "Cloud Run service, three demo cases preloaded, warm through evaluation")]
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

out = HERE + "/LedgerLens_AI_Builder_Cup_Submission.pptx"
prs.save(out)
print("saved", out)
