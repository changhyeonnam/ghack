"""Story diagrams for the LedgerLens deck: problem chain, journey, before/after, feature pipeline, tech stack, roadmap.
All text is measured against its box and shrunk if needed (never below 5.6 pt)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle
from diagrams import arrow, INK, TEAL, TINT, AMBER, AMBER_T, RED, GREY, LINE, TXT, WHITE, OUT

PANEL = "#F7F9FA"
_FIG = {}


def fig(w, h):
    f, ax = plt.subplots(figsize=(w, h), dpi=300)
    ax.set_position([0, 0, 1, 1])  # data units == inches, so text can be measured against boxes
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    _FIG["f"] = f; _FIG["ax"] = ax
    return f, ax


def save(f, name):
    f.savefig(f"{OUT}/{name}", bbox_inches="tight", pad_inches=0.04, facecolor=WHITE)
    plt.close(f)


def rbox(ax, x, y, w, h, fill=WHITE, edge=LINE, lw=1.2, r=0.08):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fill, ec=edge, lw=lw))


def text(ax, x, y, s, size=8, color=TXT, bold=False, ha="left", va="center", style="normal", maxw=None):
    """Draw text; if maxw (inches) is given, shrink font until the widest line fits."""
    t = ax.text(x, y, s, fontsize=size, color=color, fontweight="bold" if bold else "normal", ha=ha, va=va, style=style)
    if maxw:
        f = _FIG["f"]; r = f.canvas.get_renderer()
        while True:
            bb = t.get_window_extent(renderer=r)
            w_in = bb.width / f.dpi
            if w_in <= maxw or t.get_fontsize() <= 5.6:
                break
            t.set_fontsize(t.get_fontsize() - 0.3)
    return t


def badge(ax, cx, cy, s, fill=INK, color=WHITE, r=0.14, size=8):
    ax.add_patch(Circle((cx, cy), r, fc=fill, ec="none"))
    ax.text(cx, cy, s, fontsize=size, color=color, ha="center", va="center", fontweight="bold")


def title(ax, s, y):
    text(ax, 0.2, y, s, 10.5, INK, True, maxw=9.0)


# ------------------------------------------------------------------ A. problem chain
def problem_chain():
    f, ax = fig(9.4, 3.9)
    y0, h = 1.6, 1.7
    xs = [0.2, 2.35, 4.7, 7.5]; ws = [1.85, 2.05, 2.5, 1.7]
    pad = 0.12
    # box 1
    rbox(ax, xs[0], y0, ws[0], h, fill=PANEL)
    text(ax, xs[0] + pad, y0 + h - 0.2, "They run the economy", 8.5, INK, True, maxw=ws[0] - 2 * pad)
    text(ax, xs[0] + pad, y0 + 1.1, "64M", 20, INK, True)
    text(ax, xs[0] + pad, y0 + 0.74, "MSMEs in Indonesia alone", 7.2, TXT, maxw=ws[0] - 2 * pad)
    text(ax, xs[0] + pad, y0 + 0.54, "97% of jobs, 60% of GDP", 7.2, TXT, maxw=ws[0] - 2 * pad)
    text(ax, xs[0] + pad, y0 + 0.2, "Bank Indonesia, Aug 2026", 6.3, GREY, style="italic", maxw=ws[0] - 2 * pad)
    # box 2 with mini bars
    rbox(ax, xs[1], y0, ws[1], h, fill=PANEL)
    text(ax, xs[1] + pad, y0 + h - 0.2, "But they cannot borrow", 8.5, INK, True, maxw=ws[1] - 2 * pad)
    text(ax, xs[1] + pad, y0 + 1.22, "Vietnam: share with a bank loan", 6.6, GREY, maxw=ws[1] - 2 * pad)
    bx = xs[1] + pad; bw = 1.2
    ax.add_patch(Rectangle((bx, y0 + 0.94), bw * 0.471, 0.16, fc=TEAL, ec="none"))
    text(ax, bx + bw * 0.471 + 0.05, y0 + 1.02, "47.1% large firms", 6.6, TXT)
    ax.add_patch(Rectangle((bx, y0 + 0.68), bw * 0.088, 0.16, fc=AMBER, ec="none"))
    text(ax, bx + bw * 0.088 + 0.05, y0 + 0.76, "8.8% SMEs", 6.8, TXT, True)
    text(ax, xs[1] + pad, y0 + 0.44, "70% of emerging-market MSMEs", 6.6, TXT, maxw=ws[1] - 2 * pad)
    text(ax, xs[1] + pad, y0 + 0.3, "lack adequate financing", 6.6, TXT, maxw=ws[1] - 2 * pad)
    text(ax, xs[1] + pad, y0 + 0.1, "FiinGroup, Aug 2026 · IFC", 6.3, GREY, style="italic", maxw=ws[1] - 2 * pad)
    # box 3
    rbox(ax, xs[2], y0, ws[2], h, fill=PANEL)
    text(ax, xs[2] + pad, y0 + h - 0.2, "Because banks cannot read them", 8.5, INK, True, maxw=ws[2] - 2 * pad)
    lines = [("75.5% have no acceptable collateral", "VCCI Private Economic Report 2025"),
             ("Records are PDFs, screenshots, receipts", "no credit file, nothing a scorecard can use"),
             ("Reading them costs more than the loan earns", "high cost, low return for the lender (ADB 2025)")]
    yy = y0 + 1.18
    for a, b in lines:
        text(ax, xs[2] + pad, yy, a, 7.2, INK, True, maxw=ws[2] - 2 * pad)
        text(ax, xs[2] + pad, yy - 0.16, b, 6.3, GREY, maxw=ws[2] - 2 * pad)
        yy -= 0.4
    # box 4
    rbox(ax, xs[3], y0, ws[3], h, fill="#FDECEA", edge=RED, lw=1.5)
    text(ax, xs[3] + pad, y0 + h - 0.2, "So they are", 8.5, INK, True, maxw=ws[3] - 2 * pad)
    text(ax, xs[3] + pad, y0 + 1.02, "Declined,", 13, RED, True, maxw=ws[3] - 2 * pad)
    text(ax, xs[3] + pad, y0 + 0.72, "or lent blind at", 8.5, TXT, maxw=ws[3] - 2 * pad)
    text(ax, xs[3] + pad, y0 + 0.52, "high rates", 8.5, TXT, maxw=ws[3] - 2 * pad)
    text(ax, xs[3] + pad, y0 + 0.2, "PH: 3.9% of bank credit (ADB)", 6.3, GREY, style="italic", maxw=ws[3] - 2 * pad)
    for i in range(3):
        arrow(ax, xs[i] + ws[i], y0 + h / 2, xs[i + 1], y0 + h / 2, lw=1.6)
    # opening band
    rbox(ax, 0.2, 0.25, 9.0, 1.0, fill=AMBER_T, edge=AMBER, lw=1.6)
    text(ax, 0.38, 1.0, "The opening", 8.5, AMBER, True)
    text(ax, 0.38, 0.72, "VPBank, Vietcombank and Agribank are moving from collateral to cash-flow lending (VTV, May 2026).", 7.6, TXT, maxw=8.6)
    text(ax, 0.38, 0.47, "Cash-flow lending means someone has to read the cash flow. That reading is what LedgerLens makes fast, sourced and auditable.", 7.6, TXT, True, maxw=8.6)
    arrow(ax, xs[2] + ws[2] / 2, 1.25, xs[2] + ws[2] / 2, y0, color=AMBER, lw=1.6)
    title(ax, "Small businesses run Southeast Asia's economy but cannot get a loan, because nobody can afford to read their records", 3.6)
    save(f, "problem_chain.png")


# ------------------------------------------------------------------ B. journey
def journey():
    f, ax = fig(9.4, 3.5)
    # left: shoebox
    rbox(ax, 0.2, 0.55, 2.0, 2.5, fill=PANEL)
    text(ax, 0.32, 2.85, "What the borrower has", 8.3, INK, True, maxw=1.8)
    docs = ["Mobile-banking statement PDF", "Shopee dashboard screenshots", "Paper receipts, handwritten ledger", "Photos of the shop"]
    yy = 2.5
    for d in docs:
        ax.add_patch(FancyBboxPatch((0.32, yy - 0.17), 1.76, 0.36, boxstyle="round,pad=0,rounding_size=0.05", fc=WHITE, ec=LINE))
        text(ax, 0.42, yy + 0.01, d, 6.6, TXT, maxw=1.6)
        yy -= 0.46
    text(ax, 0.32, 0.7, "Unstructured. No credit file.", 6.8, GREY, style="italic", maxw=1.8)
    # center: three stages
    cx = [2.5, 4.4, 6.3]; W = 1.6; H = 1.15; yc = 1.2
    stages = [("Read with evidence", ["Gemini reads every value with", "doc id, page and bbox; the PDF", "text layer verifies it."], False),
              ("Challenge", ["A second agent runs 12", "underwriting checks and", "raises ranked objections."], True),
              ("Human signs", ["The underwriter accepts or", "dismisses each objection,", "decides, and it is logged."], False)]
    for i, (t, lines, acc) in enumerate(stages):
        rbox(ax, cx[i], yc, W, H, fill=AMBER_T if acc else WHITE, edge=AMBER if acc else INK, lw=1.8 if acc else 1.3)
        badge(ax, cx[i] + 0.2, yc + H - 0.22, str(i + 1), fill=AMBER if acc else INK, r=0.12, size=7)
        text(ax, cx[i] + 0.38, yc + H - 0.22, t, 8, INK, True, maxw=W - 0.45)
        for j, l in enumerate(lines):
            text(ax, cx[i] + 0.1, yc + 0.66 - j * 0.2, l, 6.4, TXT, maxw=W - 0.2)
    arrow(ax, 2.2, 1.78, cx[0], 1.78, lw=1.6)
    for i in range(2):
        arrow(ax, cx[i] + W, 1.78, cx[i + 1], 1.78, lw=1.6)
    arrow(ax, cx[2] + W, 1.78, 8.2, 1.78, lw=1.6)
    ax.plot([cx[0], cx[2] + W], [2.75, 2.75], color=LINE, lw=1)
    text(ax, (cx[0] + cx[2] + W) / 2, 2.9, "LedgerLens  ·  about 2 minutes and about USD 0.28 per case (measured, cold run)", 7.6, GREY, ha="center")
    # feedback loop
    arrow(ax, cx[2] + W / 2, yc, cx[2] + W / 2, 0.78, style="-", color=AMBER)
    arrow(ax, cx[2] + W / 2, 0.78, cx[1] + W / 2, 0.78, style="-", color=AMBER)
    arrow(ax, cx[1] + W / 2, 0.78, cx[1] + W / 2, yc, color=AMBER)
    text(ax, (cx[1] + cx[2] + W) / 2, 0.6, "decisions re-rank the next Challenger run", 6.6, GREY, ha="center", style="italic")
    # right: outputs
    rbox(ax, 8.2, 0.55, 1.05, 2.5, fill=TINT, edge=TEAL, lw=1.3)
    text(ax, 8.725, 2.85, "What the bank gets", 7.2, INK, True, ha="center", maxw=0.95)
    outs = [["Memo, every", "number clickable"], ["Objections", "resolved"], ["Decision and", "audit log"], ["Letter in the", "customer's language"]]
    yy = 2.42
    for o in outs:
        for j, l in enumerate(o):
            text(ax, 8.725, yy - j * 0.16, l, 6.2, TXT, ha="center", maxw=0.95)
        yy -= 0.5
    title(ax, "LedgerLens turns the shoebox into a credit memo a bank can trust", 3.3)
    save(f, "journey.png")


# ------------------------------------------------------------------ C. before / after lanes
def before_after():
    f, ax = fig(9.4, 3.6)
    stages = ["Collect", "Read", "Assess", "Decide", "Explain"]
    xs = [1.4, 2.82, 4.24, 5.66, 7.08]; W = 1.3
    for x, st in zip(xs, stages):
        text(ax, x + W / 2, 3.05, st, 8.5, INK, True, ha="center")
    ax.plot([1.4, 8.38], [2.92, 2.92], color=LINE, lw=1)
    lanes = [("Today", 1.85, PANEL, LINE,
              [["Same PDFs,", "screenshots, receipts"], ["Read by hand,", "retyped into Excel"], ["Collateral and", "gut feel"], ["Decline, or price", "blind at high rates"], ["No reason the", "customer can read"]]),
             ("With\nLedgerLens", 0.55, AMBER_T, AMBER,
              [["Same documents,", "uploaded as one case"], ["~2 min, every figure", "linked to its line"], ["Challenger raises", "12 checks as objections"], ["Underwriter signs", "with evidence in hand"], ["Letter in the", "customer's language"]])]
    for name, y, fill, edge, notes in lanes:
        text(ax, 0.2, y + 0.45, name, 8.5, INK, True, maxw=1.1)
        for x, n in zip(xs, notes):
            rbox(ax, x, y, W, 0.9, fill=fill, edge=edge, lw=1.5 if edge == AMBER else 1.1)
            for j, l in enumerate(n):
                text(ax, x + W / 2, y + 0.55 - j * 0.2, l, 6.6, TXT, ha="center", maxw=W - 0.12)
        for i in range(4):
            arrow(ax, xs[i] + W, y + 0.45, xs[i + 1], y + 0.45, lw=1.2, color=edge if edge == AMBER else LINE)
    # impact column
    imp = [("~2 min", "per file, end to end"), ("~0.28", "USD per case, cold"), ("0 vs 62", "unsourced numbers")]
    yy = 2.75
    for big, small in imp:
        rbox(ax, 8.55, yy - 0.8, 0.75, 0.8, fill=TINT, edge=TEAL, lw=1.1)
        text(ax, 8.925, yy - 0.3, big, 8, INK, True, ha="center", maxw=0.68)
        text(ax, 8.925, yy - 0.58, small, 5.6, GREY, ha="center", maxw=0.7)
        yy -= 0.9
    title(ax, "What changes for the lender: the same documents, read in about 2 minutes, every number defensible", 3.4)
    save(f, "before_after.png")


# ------------------------------------------------------------------ D. feature pipeline
def feature_pipeline():
    f, ax = fig(9.4, 3.6)
    stages = [("Intake", "Gemini Flash"), ("Extract", "Gemini, 5 doc types"), ("Cash flow", "Python"),
              ("Analyze", "Analyst agent"), ("Challenge", "Challenger agent"), ("Decide", "Underwriter"), ("Explain", "Explainer agent")]
    n = len(stages); W = 1.2; gap = (9.0 - n * W) / (n - 1); xs = [0.2 + i * (W + gap) for i in range(n)]
    ys = 2.35
    ax.plot([xs[0] + W / 2, xs[-1] + W / 2], [ys + 0.28, ys + 0.28], color=INK, lw=2, zorder=1)
    for x, (t, m) in zip(xs, stages):
        acc = t == "Challenge"
        rbox(ax, x, ys, W, 0.56, fill=AMBER_T if acc else WHITE, edge=AMBER if acc else INK, lw=1.8 if acc else 1.3)
        text(ax, x + W / 2, ys + 0.37, t, 8, INK, True, ha="center", maxw=W - 0.1)
        text(ax, x + W / 2, ys + 0.17, m, 6.0, GREY, ha="center", maxw=W - 0.1)
    feats = [("MUST", ["Multimodal", "intake"], ["PDF, screenshots,", "photos; classified,", "quality-flagged"]),
             ("MUST", ["Evidence-linked", "extraction"], ["doc id, page, bbox on", "every value; PDF text-", "layer cross-check"]),
             ("MUST", ["Deterministic", "cash-flow model"], ["inflow, outflow,", "trend, volatility,", "debt service"]),
             ("MUST", ["Clickable", "memo"], ["cites catalog", "figures only; click", "opens the source"]),
             ("MUST", ["Battery +", "12 questions"], ["image hash, balance", "chain, dates;", "ranked objections"]),
             ("MUST", ["Underwriter", "workbench"], ["accept / dismiss, sign;", "audit log; decisions", "re-weight the checks"]),
             ("SHOULD", ["Letter and", "paper memo"], ["customer letter in", "local language; memo", "prints with footnotes"])]
    for x, (tag, t, d) in zip(xs, feats):
        arrow(ax, x + W / 2, ys, x + W / 2, 1.8, lw=1.1)
        rbox(ax, x, 0.3, W, 1.5, fill=PANEL, edge=LINE)
        tw = 0.5 if tag == "MUST" else 0.64
        ax.add_patch(FancyBboxPatch((x + 0.1, 1.52), tw, 0.17, boxstyle="round,pad=0,rounding_size=0.08", fc=INK if tag == "MUST" else TEAL, ec="none"))
        text(ax, x + 0.1 + tw / 2, 1.605, tag, 5.2, WHITE, True, ha="center")
        for j, l in enumerate(t):
            text(ax, x + 0.1, 1.3 - j * 0.17, l, 7.2, INK, True, maxw=W - 0.18)
        for j, l in enumerate(d):
            text(ax, x + 0.1, 0.78 - j * 0.16, l, 5.9, TXT, maxw=W - 0.18)
    title(ax, "Every feature hangs on one pipeline, and the pipeline ends with a person", 3.35)
    save(f, "feature_pipeline.png")


# ------------------------------------------------------------------ E. tech stack
def tech_stack():
    f, ax = fig(9.4, 3.7)
    layers = [("Experience", "React + Vite on Cloud Run: portfolio, new case, workbench, evidence viewer, print export", "One screen per decision; dark and light themes", True),
              ("Agents", "ADK: Intake · Extractor x5 · Analyst · Challenger (investigator, writer) · Explainer", "Challenger never sees the Analyst prompt", True),
              ("Models", "Gemini 3.8 Flash for every agent · Gemini 3.1 Pro optional for the heavy agents", "One env var switches to Pro", True),
              ("Tools", "Python: cash-flow model · balance chain · image hash · PDF text-layer cross-check · date/entity checks", "Numbers computed, never generated; the text layer verifies what Gemini read", False),
              ("Data", "Firestore: cases, extractions, memos, objections, decisions, audit, traces · Cloud Storage: documents", "Accept/dismiss rates become Challenger priorities", True),
              ("Run", "Cloud Run, scales to zero · content-hash LLM cache · cache_only demo · budget cap", "Re-runs and evaluation cost nothing", True)]
    h = 0.4; gap = 0.07; y = 3.05
    for name, what, why, g in layers:
        rbox(ax, 0.2, y - h, 1.25, h, fill=INK if g else TEAL, edge="none", r=0.06)
        text(ax, 0.825, y - h / 2, name, 8, WHITE, True, ha="center")
        rbox(ax, 1.55, y - h, 5.3, h, fill=PANEL, edge=LINE)
        text(ax, 1.67, y - h / 2, what, 6.8, TXT, maxw=5.05)
        rbox(ax, 6.95, y - h, 2.25, h, fill=WHITE, edge=LINE)
        text(ax, 7.07, y - h / 2, why, 6.6, GREY, style="italic", maxw=2.0)
        y -= h + gap
    for i in range(len(layers) - 1):
        yt = 3.05 - (i + 1) * (h + gap) + gap
        arrow(ax, 0.825, yt, 0.825, yt - gap, lw=1.0)
    text(ax, 1.67, 3.18, "What", 7, GREY, True)
    text(ax, 7.07, 3.18, "Why this choice", 7, GREY, True)
    ly = 3.05 - 6 * (h + gap) - 0.08
    ax.add_patch(Rectangle((1.55, ly - 0.05), 0.14, 0.11, fc=INK, ec="none")); text(ax, 1.75, ly, "Google Cloud", 6.3, GREY)
    ax.add_patch(Rectangle((2.6, ly - 0.05), 0.14, 0.11, fc=TEAL, ec="none")); text(ax, 2.8, ly, "Open source", 6.3, GREY)
    title(ax, "One Google Cloud project, from the underwriter's screen down to the cache", 3.5)
    save(f, "tech_stack.png")


# ------------------------------------------------------------------ F. roadmap with limits
def roadmap():
    f, ax = fig(9.4, 3.5)
    phases = [("Pilot", "Q1 2027", ["One SEA bank or MFI, real consented SME files;", "underwriter decisions replace synthetic traps"], 0.2, 2.9),
              ("Integrate", "Q2–Q3 2027", ["Open-banking feeds (Brankas, Finverse) beside PDFs;", "hooks into loan origination systems"], 3.25, 2.9),
              ("Scale", "2028", ["Same pattern for trade finance and micro-insurance;", "shared Challenger check library"], 6.3, 2.9)]
    y = 2.0; h = 0.9
    for i, (t, when, lines, x, w) in enumerate(phases):
        rbox(ax, x, y, w, h, fill=TINT if i == 0 else PANEL, edge=TEAL if i == 0 else LINE, lw=1.5 if i == 0 else 1.1)
        tt = text(ax, x + 0.12, y + h - 0.2, t, 9, INK, True)
        bb = tt.get_window_extent(renderer=f.canvas.get_renderer()); tw = bb.width / f.dpi
        text(ax, x + 0.12 + tw + 0.1, y + h - 0.2, when, 7, TEAL, True)
        for j, l in enumerate(lines):
            text(ax, x + 0.12, y + 0.42 - j * 0.18, l, 6.6, TXT, maxw=w - 0.24)
        if i < 2:
            arrow(ax, x + w, y + h / 2, phases[i + 1][3], y + h / 2, lw=1.4)
    ax.plot([0.2, 9.2], [y - 0.12, y - 0.12], color=LINE, lw=1)
    limits = [("Synthetic benchmark", ["A small synthetic sample with planted risks;", "real-data results come with the pilot."], 0.2, 0),
              ("Forged documents", ["Hash and balance-chain checks catch crude edits.", "Open-banking data closes the gap for the rest."], 3.25, 1),
              ("Platform sellers", ["Shopee and Grab already lend to their own sellers.", "We target banks and MFIs lending outside platforms."], 6.3, None)]
    text(ax, 0.2, 1.72, "What we do not claim yet, and which phase answers it", 8, GREY, True)
    for t, lines, x, ph in limits:
        rbox(ax, x, 0.3, 2.9, 1.2, fill=WHITE, edge=AMBER, lw=1.2)
        text(ax, x + 0.12, 1.3, t, 8, AMBER, True)
        for j, l in enumerate(lines):
            text(ax, x + 0.12, 0.92 - j * 0.2, l, 6.6, TXT, maxw=2.66)
        if ph is not None:
            arrow(ax, x + 1.45, 1.5, phases[ph][3] + phases[ph][4] / 2, y, color=AMBER, lw=1.3)
        else:
            text(ax, x + 0.12, 0.45, "positioning, not a feature", 6, GREY, style="italic")
    title(ax, "Where this goes next, and what we do not claim yet", 3.3)
    save(f, "roadmap.png")





# ------------------------------------------------------------------ G. process flow as swimlanes
def process_flow2():
    f, ax = fig(9.4, 3.95)
    lanes = [("Loan officer", 2.85, 0.72), ("LedgerLens agents", 1.6, 1.15), ("Underwriter", 0.2, 1.3)]
    for name, y, h in lanes:
        ax.add_patch(FancyBboxPatch((0.2, y), 9.0, h, boxstyle="round,pad=0,rounding_size=0.06", fc=PANEL, ec="#E3E7EA", lw=1))
        text(ax, 0.32, y + h / 2, name, 7.8, INK, True, maxw=1.0)
    ax.plot([1.4, 1.4], [0.2, 3.57], color="#D5DBDE", lw=1)
    H = 0.56
    def step(n, t, d, x, w, y, fill=WHITE, edge=INK, bfill=INK, lw=1.3):
        rbox(ax, x, y, w, H, fill=fill, edge=edge, lw=lw)
        badge(ax, x + 0.18, y + H / 2, n, fill=bfill, r=0.11, size=6.5)
        text(ax, x + 0.36, y + H / 2 + 0.1, t, 7.2, INK, True, maxw=w - 0.44)
        text(ax, x + 0.36, y + H / 2 - 0.12, d, 6.0, GREY, maxw=w - 0.44)
    # lane 1
    y1 = 2.85 + (0.72 - H) / 2
    step("1", "Create case, upload", "PDFs, screenshots, photos", 1.6, 1.75, y1)
    step("9", "Decision + letter", "in the applicant's language", 7.3, 1.75, y1, fill=TINT, edge=TEAL, bfill=TEAL)
    # lane 2
    y2 = 1.6 + 1.15 - 0.12 - H
    steps = [("2", "Intake", "classify, quality flags", 1.6, 1.3, False),
             ("3", "Extract", "Gemini, source on every value", 3.05, 1.6, False),
             ("4", "Cash flow", "Python, deterministic", 4.8, 1.3, False),
             ("5", "Analyst memo", "cites catalog figures only", 6.2, 1.4, False),
             ("6", "Challenger", "battery + 12 checks", 7.75, 1.4, True)]
    for n, t, d, x, w, acc in steps:
        step(n, t, d, x, w, y2, fill=AMBER_T if acc else WHITE, edge=AMBER if acc else INK, bfill=AMBER if acc else INK, lw=1.8 if acc else 1.3)
    for i in range(len(steps) - 1):
        arrow(ax, steps[i][3] + steps[i][4], y2 + H / 2, steps[i + 1][3], y2 + H / 2, lw=1.3)
    text(ax, 1.6, 1.72, "about 2 minutes, about USD 0.28 (cold; cached re-run USD 0), every figure carries doc id · page · bbox", 6.2, GREY, style="italic")
    # lane 3
    y3 = 0.38
    step("7", "Review memo", "click any number to its line", 1.6, 1.85, y3)
    dx, dy = 4.5, y3 + H / 2
    ax.add_patch(plt.Polygon([(dx - 0.8, dy), (dx, dy + 0.36), (dx + 0.8, dy), (dx, dy - 0.36)], closed=True, fc=WHITE, ec=INK, lw=1.3))
    text(ax, dx, dy + 0.07, "Each objection", 6.8, INK, True, ha="center")
    text(ax, dx, dy - 0.1, "accept or dismiss", 6.0, GREY, ha="center")
    step("8", "Sign decision", "conditions, rationale", 6.0, 1.5, y3)
    arrow(ax, 3.45, dy, dx - 0.8, dy, lw=1.3)
    arrow(ax, dx + 0.8, dy, 6.0, dy, lw=1.3)
    # 1 -> 2
    arrow(ax, 2.25, y1, 2.25, y2 + H, lw=1.3)
    # 6 -> 7 : down to a connector line, then left to box 7
    cx6 = 7.75 + 0.7; yc = 1.22
    arrow(ax, cx6, y2, cx6, yc, style="-", lw=1.3)
    ax.plot([cx6, 2.52], [yc, yc], color="#9AA5AB", lw=1.3)
    arrow(ax, 2.52, yc, 2.52, y3 + H, lw=1.3)
    text(ax, 2.65, yc + 0.11, "objections, severity-ranked, with evidence", 6.0, GREY, ha="left", style="italic")
    # 8 -> 9 via Explainer (teal), and feedback 8 -> 6 (amber dashed)
    arrow(ax, 7.5, dy, 9.05, dy, style="-", color=TEAL)
    arrow(ax, 9.05, dy, 9.05, y1, color=TEAL, lw=1.3)
    text(ax, 7.15, y1 + H / 2, "Explainer agent writes the letter", 6.0, TEAL, style="italic", ha="right", maxw=3.6)
    arrow(ax, 6.75, y3 + H, 6.75, y2, color=AMBER, lw=1.3, ls="--")
    text(ax, 6.85, 1.38, "decisions re-weight the checks", 6.0, AMBER, style="italic", ha="left", maxw=1.6)
    title(ax, "One pass through LedgerLens: documents in, a signed and explained decision out", 3.78)
    save(f, "process_flow.png")


# ------------------------------------------------------------------ H. architecture (same visual system)
def architecture2():
    f, ax = fig(9.4, 4.5)
    def cont(y, h, label):
        ax.add_patch(FancyBboxPatch((0.2, y), 9.0, h, boxstyle="round,pad=0,rounding_size=0.08", fc=PANEL, ec="#D5DBDE", lw=1))
        text(ax, 0.34, y + h - 0.2, label, 8, INK, True, maxw=8.6)
    # Frontend: y 3.3 .. 4.2
    cont(3.3, 0.9, "Frontend  ·  React + Vite, served by Cloud Run")
    rbox(ax, 0.4, 3.4, 1.9, 0.44, fill=WHITE, edge=LINE); text(ax, 1.35, 3.62, "Portfolio · New case", 7.4, INK, True, ha="center", maxw=1.7)
    rbox(ax, 2.45, 3.4, 6.6, 0.44, fill=WHITE, edge=LINE); text(ax, 5.75, 3.62, "Workbench: memo · evidence viewer with bbox highlight · objections · decision · audit · print export", 7, INK, True, ha="center", maxw=6.3)
    arrow(ax, 4.7, 3.3, 4.7, 3.12, lw=1.3)
    # Backend: y 0.95 .. 3.1
    cont(0.95, 2.15, "Backend  ·  Cloud Run (Python FastAPI + ADK)  ·  scales to zero  ·  live Gemini within a budget; recorded runs replay free")
    rbox(ax, 0.4, 2.3, 1.7, 0.44, fill=WHITE, edge=LINE); text(ax, 1.25, 2.52, "REST API", 7.4, INK, True, ha="center")
    rbox(ax, 2.4, 2.3, 2.1, 0.44, fill=TINT, edge=TEAL, lw=1.6); text(ax, 3.45, 2.52, "ADK Orchestrator", 7.4, INK, True, ha="center")
    arrow(ax, 2.1, 2.52, 2.4, 2.52, lw=1.3)
    agents = [("Intake", "Gemini 3.8 Flash", False), ("Extractor x5", "Flash · Pro optional", False), ("Analyst", "Flash · Pro optional", False),
              ("Challenger", "investigator → writer", True), ("Explainer", "Gemini 3.8 Flash", False)]
    xs = [0.4, 2.15, 3.9, 5.65, 7.4]; W = 1.6; ya = 1.52
    ax.plot([xs[0] + W / 2, xs[-1] + W / 2], [2.16, 2.16], color="#9AA5AB", lw=1.3)
    ax.plot([3.45, 3.45], [2.3, 2.16], color="#9AA5AB", lw=1.3)
    for x, (t, m, acc) in zip(xs, agents):
        arrow(ax, x + W / 2, 2.16, x + W / 2, ya + 0.5, lw=1.3)
        rbox(ax, x, ya, W, 0.5, fill=AMBER_T if acc else WHITE, edge=AMBER if acc else LINE, lw=1.6 if acc else 1.1)
        text(ax, x + W / 2, ya + 0.32, t, 7.4, INK, True, ha="center", maxw=W - 0.1)
        text(ax, x + W / 2, ya + 0.14, m, 6.0, GREY, ha="center", maxw=W - 0.1)
    rbox(ax, 2.6, 1.03, 6.45, 0.34, fill=WHITE, edge=LINE)
    text(ax, 5.825, 1.2, "Tools: cash-flow model · balance chain · image hash · PDF text-layer cross-check · date/entity checks · LLM cache · feedback priorities", 6.2, GREY, ha="center", maxw=6.2)
    arrow(ax, xs[2] + W / 2, ya, xs[2] + W / 2, 1.37, lw=1.1)
    arrow(ax, xs[3] + W / 2, ya, xs[3] + W / 2, 1.37, lw=1.1)
    # Data: y 0.1 .. 0.78
    arrow(ax, 1.25, 0.95, 1.25, 0.8, lw=1.3)
    cont(0.08, 0.72, "Data")
    rbox(ax, 1.0, 0.15, 3.0, 0.4, fill=WHITE, edge=LINE); text(ax, 2.5, 0.35, "Cloud Storage: documents, page renders", 6.8, TXT, ha="center", maxw=2.8)
    rbox(ax, 4.2, 0.15, 4.85, 0.4, fill=WHITE, edge=LINE); text(ax, 6.625, 0.35, "Firestore: cases · extractions · memos · objections · decisions · audit · traces", 6.8, TXT, ha="center", maxw=4.65)
    title(ax, "One Google Cloud project end to end; every agent call is cached by content hash", 4.35)
    save(f, "architecture.png")


# ------------------------------------------------------------------ I. checks map (appendix)
def checks_map():
    f, ax = fig(9.4, 3.9)
    rbox(ax, 0.2, 3.0, 9.0, 0.5, fill=AMBER_T, edge=AMBER, lw=1.6)
    text(ax, 4.7, 3.25, "Challenger: deterministic battery first, then 12 fixed questions with tools, then case-specific ones", 8, INK, True, ha="center", maxw=8.6)
    groups = [("Revenue quality", [("1", "Revenue double-counted", False), ("2", "Seasonal vs one-off inflows", False), ("10", "Month-end revenue clustering", False)]),
              ("Round trips", [("3", "Self-transfers, own accounts", False)]),
              ("Document integrity", [("4", "Receipt images reused/edited", True), ("8", "Premises photo vs sales", False), ("11", "Names, addresses consistent", False), ("12", "Language, currency vs location", False)]),
              ("Periods and balances", [("5", "Dashboard vs statement period", True), ("6", "Balance continuity, every row", True)]),
              ("Hidden debt", [("7", "Recurring loan-like debits", False)]),
              ("Sourcing", [("9", "Every figure has a source", True)])]
    n = len(groups); W = 1.42; gap = (9.0 - n * W) / (n - 1); xs = [0.2 + i * (W + gap) for i in range(n)]
    for x, (g, checks) in zip(xs, groups):
        arrow(ax, x + W / 2, 3.0, x + W / 2, 2.72, lw=1.1)
        rbox(ax, x, 2.4, W, 0.32, fill=INK, edge="none", r=0.05)
        text(ax, x + W / 2, 2.56, g, 6.8, WHITE, True, ha="center", maxw=W - 0.1)
        y = 2.3
        for num, t, tool in checks:
            rbox(ax, x, y - 0.5, W, 0.46, fill=WHITE, edge=AMBER if tool else LINE, lw=1.3 if tool else 1)
            badge(ax, x + 0.16, y - 0.27, num, fill=AMBER if tool else INK, r=0.1, size=5.8)
            text(ax, x + 0.32, y - 0.2, t, 5.9, TXT, maxw=W - 0.38)
            text(ax, x + 0.32, y - 0.37, "deterministic tool" if tool else "agent reasoning + evidence", 5.3, AMBER if tool else GREY, maxw=W - 0.38)
            y -= 0.54
    text(ax, 0.2, 0.12, "Amber = enforced by a deterministic tool, so a finding is guaranteed to surface. Grey = reasoned by the Challenger with evidence references.", 6.3, GREY, style="italic", maxw=9.0)
    title(ax, "Twelve fixed checks in six families; four of them are enforced by deterministic tools", 3.72)
    save(f, "checks_map.png")


if __name__ == "__main__":
    problem_chain(); journey(); before_after(); feature_pipeline(); tech_stack(); roadmap(); process_flow2(); architecture2(); checks_map()
    print("ok")
