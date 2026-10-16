"""Generate diagram PNGs for the LedgerLens submission deck."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon, Rectangle
import os

OUT = os.path.dirname(os.path.abspath(__file__)) + "/img"
os.makedirs(OUT, exist_ok=True)

INK = "#0F3D4C"
TEAL = "#2A7F8E"
TINT = "#E6F2F4"
AMBER = "#E0A100"
AMBER_T = "#FFF3CC"
RED = "#B3261E"
GREY = "#5F6368"
LINE = "#9AA5AB"
TXT = "#202124"
WHITE = "#FFFFFF"
plt.rcParams["font.family"] = "DejaVu Sans"


def box(ax, x, y, w, h, title, body=None, fill=WHITE, edge=LINE, lw=1.2, tsize=8.2, bsize=6.4, bold=True, tcolor=TXT, bcolor=GREY, radius=0.06):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}", fc=fill, ec=edge, lw=lw)
    ax.add_patch(p)
    if body:
        ax.text(x + w / 2, y + h / 2 + 0.11, title, ha="center", va="center", fontsize=tsize, fontweight="bold" if bold else "normal", color=tcolor)
        ax.text(x + w / 2, y + h / 2 - 0.13, body, ha="center", va="center", fontsize=bsize, color=bcolor)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=tsize, fontweight="bold" if bold else "normal", color=tcolor)


def arrow(ax, x1, y1, x2, y2, color=LINE, lw=1.3, style="-|>", ls="-", conn=None):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=12, color=color, lw=lw, linestyle=ls,
                        connectionstyle=conn or "arc3,rad=0", shrinkA=0, shrinkB=0)
    ax.add_patch(a)


def process_flow():
    fig, ax = plt.subplots(figsize=(9.4, 3.7), dpi=300)
    ax.set_xlim(0, 9.4); ax.set_ylim(0, 3.7); ax.axis("off")
    W, H = 1.5, 0.62
    ya = 2.75
    xs = [0.25, 2.05, 3.85, 5.65, 7.45]
    labels = [("Upload", "PDF, screenshots, photos"), ("Intake", "classify, quality, language"),
              ("Extractor", "values + page + bbox"), ("Cash-flow model", "deterministic Python"),
              ("Analyst memo", "cites tool outputs only")]
    for (x, (t, b)) in zip(xs, labels):
        box(ax, x, ya, W, H, t, b)
    for i in range(4):
        arrow(ax, xs[i] + W, ya + H / 2, xs[i + 1], ya + H / 2)
    ax.text(0.25, ya - 0.2, "Every figure carries a source_ref: document id, page, bounding box", fontsize=7, color=GREY, style="italic")

    yb = 1.25
    # Challenger (accent)
    box(ax, 7.45, yb, W, H, "Challenger", "battery + 12 questions", fill=AMBER_T, edge=AMBER, lw=2)
    arrow(ax, xs[4] + W / 2, ya, xs[4] + W / 2, yb + H)
    # decision diamond
    cx, cy = 5.95, yb + H / 2
    d = Polygon([(cx - 0.8, cy), (cx, cy + 0.45), (cx + 0.8, cy), (cx, cy - 0.45)], closed=True, fc=WHITE, ec=LINE, lw=1.2)
    ax.add_patch(d)
    ax.text(cx, cy + 0.07, "Underwriter", ha="center", va="center", fontsize=8.2, fontweight="bold", color=TXT)
    ax.text(cx, cy - 0.14, "accepts / dismisses", ha="center", va="center", fontsize=6.4, color=GREY)
    arrow(ax, 7.45, cy, cx + 0.8, cy)
    ax.text(7.1, cy + 0.1, "objections", ha="center", fontsize=6.4, color=GREY)
    # decision box
    box(ax, 3.1, yb, 2.0, H, "Approve / Hold / Decline", "with conditions and reasons")
    arrow(ax, cx - 0.8, cy, 5.1, cy)
    # letter
    box(ax, 0.6, yb, 2.2, H, "Customer explanation", "plain language, local language")
    arrow(ax, 3.1, cy, 2.8, cy)
    # feedback loop
    arrow(ax, cx, cy - 0.45, cx, 0.55, style="-")
    arrow(ax, cx, 0.55, 8.2, 0.55, style="-")
    arrow(ax, 8.2, 0.55, 8.2, yb, color=LINE)
    ax.text(7.07, 0.33, "decision log re-ranks the next Challenger run", ha="center", fontsize=7, color=GREY, style="italic")
    ax.text(0.25, 3.5, "AI drafts the memo, a second AI challenges it, a human decides", fontsize=10.5, fontweight="bold", color=INK)
    fig.savefig(f"{OUT}/process_flow.png", bbox_inches="tight", pad_inches=0.05, facecolor=WHITE)
    plt.close(fig)


def architecture():
    fig, ax = plt.subplots(figsize=(9.4, 4.0), dpi=300)
    ax.set_xlim(0, 9.4); ax.set_ylim(0, 4.0); ax.axis("off")

    def container(x, y, w, h, label):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc="#F7F9FA", ec="#D5DBDE", lw=1))
        ax.text(x + 0.15, y + h - 0.2, label, fontsize=8.5, fontweight="bold", color=INK, va="center")

    # Frontend
    container(0.2, 3.1, 9.0, 0.8, "Frontend  ·  React + Vite, served by Cloud Run")
    box(ax, 0.5, 3.17, 2.0, 0.45, "Portfolio · New case")
    box(ax, 2.8, 3.17, 6.2, 0.45, "Workbench: memo · evidence viewer with bbox highlight · objections · decision · audit · export", tsize=6.4)
    # Backend
    container(0.2, 0.95, 9.0, 1.95, "Backend  ·  Cloud Run (Python FastAPI + ADK)  ·  scales to zero, live Gemini within a budget; recorded runs replay free")
    box(ax, 0.5, 2.2, 1.9, 0.42, "REST API")
    box(ax, 2.7, 2.2, 2.3, 0.42, "ADK Orchestrator", fill=TINT, edge=TEAL, lw=1.8)
    agents = [("Intake", "Gemini 3.8 Flash"), ("Extractor x5", "Flash, Pro optional"), ("Analyst", "Flash, Pro optional"),
              ("Challenger", "battery + 12 Qs, tools"), ("Explainer", "Gemini 3.8 Flash")]
    ax_x = [0.5, 2.25, 4.0, 5.75, 7.5]
    for x, (t, b) in zip(ax_x, agents):
        acc = t == "Challenger"
        box(ax, x, 1.45, 1.55, 0.55, t, b, fill=AMBER_T if acc else WHITE, edge=AMBER if acc else LINE, lw=2 if acc else 1.2)
        arrow(ax, x + 0.775, 2.12, x + 0.775, 2.0)
    ax.plot([0.5 + 0.775, 7.5 + 0.775], [2.12, 2.12], color=LINE, lw=1.3)
    ax.plot([3.85, 3.85], [2.2, 2.12], color=LINE, lw=1.3)
    arrow(ax, 2.4, 2.41, 2.7, 2.41)
    box(ax, 2.9, 1.03, 6.15, 0.32, "Tools: cashflow · balance chain · image hash · PDF text-layer cross-check · date/entity checks · LLM cache · feedback priorities", tsize=5.6, bold=False, tcolor=GREY)
    arrow(ax, 4.775, 1.45, 4.775, 1.35)
    ax.plot([4.775, 4.775], [1.35, 1.35], color=LINE, lw=1.2)
    arrow(ax, 6.525, 1.45, 6.525, 1.35)
    # Data
    container(0.2, 0.1, 9.0, 0.7, "Data")
    box(ax, 0.9, 0.15, 3.0, 0.38, "Cloud Storage: documents, page renders", tsize=6.8, bold=False)
    box(ax, 4.1, 0.15, 4.95, 0.38, "Firestore: cases · extractions · memos · objections · decisions · audit · traces", tsize=6.6, bold=False)
    # vertical arrows between containers
    arrow(ax, 4.7, 3.1, 4.7, 2.9)
    arrow(ax, 1.45, 0.95, 1.45, 0.8)
    fig.savefig(f"{OUT}/architecture.png", bbox_inches="tight", pad_inches=0.05, facecolor=WHITE)
    plt.close(fig)


def wireframe(path, title_bar=True, mock_label=True):
    """Underwriter workbench mock."""
    fig, ax = plt.subplots(figsize=(9.4, 3.9), dpi=300)
    ax.set_xlim(0, 9.4); ax.set_ylim(0, 3.9); ax.axis("off")
    # app frame
    ax.add_patch(FancyBboxPatch((0.1, 0.1), 9.2, 3.7, boxstyle="round,pad=0,rounding_size=0.1", fc=WHITE, ec="#C8CED2", lw=1.2))
    ax.add_patch(Rectangle((0.1, 3.4), 9.2, 0.4, fc=INK, ec="none"))
    ax.text(0.3, 3.6, "LedgerLens  ·  Case B-2041  ·  Linh Fashion Online  ·  Ho Chi Minh City", color=WHITE, fontsize=7.5, va="center", fontweight="bold")
    ax.text(9.1, 3.6, "Status: Challenger done  ·  3 objections", color="#FFD966", fontsize=6.5, va="center", ha="right")
    # left: document viewer
    ax.add_patch(Rectangle((0.3, 0.3), 3.6, 2.9, fc="#F7F9FA", ec="#D5DBDE"))
    ax.text(0.4, 3.05, "Source: bank_statement_2026-03.pdf  ·  page 4 / 12", fontsize=6.5, color=GREY)
    for i in range(9):
        y = 2.75 - i * 0.27
        ax.add_patch(Rectangle((0.45, y), 3.3, 0.18, fc="#E3E7EA" if i != 4 else "#FFE59A", ec="none"))
        ax.text(0.5, y + 0.09, ["03-02  SHOPEE PAYOUT        VND 18,420,000", "03-03  TRANSFER OUT TO LINH T.  VND 5,000,000",
                                "03-05  NAPAS QR SALES         VND 2,310,000", "03-07  ATM WITHDRAWAL         VND 1,000,000",
                                "03-10  SHOPEE PAYOUT        VND 21,960,000", "03-12  VPBANK LOAN REPAY      VND 4,150,000",
                                "03-15  NAPAS QR SALES         VND 3,085,000", "03-20  TRANSFER IN FROM LINH T. VND 5,000,000",
                                "03-28  SHOPEE PAYOUT        VND 17,730,000"][i], fontsize=5.4, color=TXT, va="center", family="DejaVu Sans Mono")
    ax.text(0.45, 0.42, "Highlighted: the line behind the memo figure you clicked", fontsize=6, color=AMBER, style="italic")
    # right: memo
    ax.add_patch(Rectangle((4.1, 1.55), 5.0, 1.65, fc=WHITE, ec="#D5DBDE"))
    ax.text(4.2, 3.05, "Credit memo (draft by Analyst)", fontsize=7.5, fontweight="bold", color=INK)
    lines = [("Monthly revenue (6-mo avg)", "VND 58.1M", True), ("Revenue volatility", "±14%", False),
             ("Undisclosed debt service", "VND 4.15M / mo", False), ("Recommendation", "Approve with conditions", False)]
    for i, (k, v, hl) in enumerate(lines):
        y = 2.78 - i * 0.3
        ax.text(4.25, y, k, fontsize=7, color=GREY, va="center")
        ax.text(8.95, y, v, fontsize=7, color=AMBER if hl else TXT, va="center", ha="right", fontweight="bold")
        if hl:
            ax.add_patch(Rectangle((8.0, y - 0.11), 1.05, 0.22, fc="none", ec=AMBER, lw=1.2))
    ax.text(4.25, 1.63, "every figure is clickable → source highlighted on the left", fontsize=6, color=GREY, style="italic")
    # objection cards
    cards = [("Critical", "Revenue double-counted", "payout also in dashboard", RED),
             ("High", "Receipt image reused", "img#07 = img#12, new date", AMBER),
             ("Medium", "Recurring transfer", "VND 4.15M monthly, undisclosed", AMBER)]
    for i, (sev, t, b, c) in enumerate(cards):
        x = 4.1 + i * 1.7
        ax.add_patch(FancyBboxPatch((x, 0.3), 1.6, 1.1, boxstyle="round,pad=0,rounding_size=0.06", fc=WHITE, ec=c, lw=1.5))
        ax.text(x + 0.1, 1.25, sev, fontsize=6.2, color=c, fontweight="bold")
        ax.text(x + 0.1, 1.02, t, fontsize=5.8, color=TXT, fontweight="bold")
        ax.text(x + 0.1, 0.82, b, fontsize=5.8, color=GREY)
        ax.add_patch(FancyBboxPatch((x + 0.1, 0.4), 0.62, 0.24, boxstyle="round,pad=0,rounding_size=0.04", fc=INK, ec="none"))
        ax.text(x + 0.41, 0.52, "Accept", fontsize=6, color=WHITE, ha="center", va="center")
        ax.add_patch(FancyBboxPatch((x + 0.82, 0.4), 0.68, 0.24, boxstyle="round,pad=0,rounding_size=0.04", fc=WHITE, ec=LINE))
        ax.text(x + 1.16, 0.52, "Dismiss", fontsize=6, color=TXT, ha="center", va="center")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.02, facecolor=WHITE)
    plt.close(fig)


def small_mock(path, title, body_lines, accent=INK):
    fig, ax = plt.subplots(figsize=(4.4, 1.95), dpi=300)
    ax.set_xlim(0, 4.4); ax.set_ylim(0, 1.95); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.05, 0.05), 4.3, 1.85, boxstyle="round,pad=0,rounding_size=0.08", fc=WHITE, ec="#C8CED2", lw=1.2))
    ax.add_patch(Rectangle((0.05, 1.6), 4.3, 0.3, fc=accent, ec="none"))
    ax.text(0.18, 1.75, title, color=WHITE, fontsize=7, va="center", fontweight="bold")
    for i, (txt, kind) in enumerate(body_lines):
        y = 1.4 - i * 0.24
        if kind == "bar":
            ax.add_patch(Rectangle((0.2, y - 0.09), 4.0, 0.18, fc="#E3E7EA", ec="none"))
            ax.text(0.28, y, txt, fontsize=5.6, color=TXT, va="center")
        elif kind == "hl":
            ax.add_patch(Rectangle((0.2, y - 0.09), 4.0, 0.18, fc="#FFE59A", ec="none"))
            ax.text(0.28, y, txt, fontsize=5.6, color=TXT, va="center")
        elif kind == "btn":
            ax.add_patch(FancyBboxPatch((0.2, y - 0.1), 1.4, 0.2, boxstyle="round,pad=0,rounding_size=0.04", fc=accent, ec="none"))
            ax.text(0.9, y, txt, fontsize=6, color=WHITE, va="center", ha="center")
        else:
            ax.text(0.2, y, txt, fontsize=5.8, color=GREY if kind == "muted" else TXT, va="center")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.02, facecolor=WHITE)
    plt.close(fig)


if __name__ == "__main__":
    process_flow()
    architecture()
    wireframe(f"{OUT}/wireframe.png")
    small_mock(f"{OUT}/mock_upload.png", "1 · New case: upload documents",
               [("bank_statement_2026-03.pdf   12 pages   ✓ bank statement", "bar"),
                ("shopee_dashboard_03.png   ✓ seller dashboard", "bar"),
                ("receipts_batch_01.jpg … 15 files   ✓ receipts", "bar"),
                ("storefront_01.jpg   ✓ premises photo", "bar"),
                ("Intake: 19 docs classified · 2 low-quality flags · language: vi", "muted"),
                ("Run LedgerLens", "btn")])
    small_mock(f"{OUT}/mock_memo.png", "2 · Credit memo with evidence links",
               [("Monthly revenue (6-mo avg)          VND 58.1M  ⟶ p.4 L5", "hl"),
                ("Revenue volatility                        ±14%  ⟶ 6 refs", "bar"),
                ("Debt service detected          VND 4.15M / mo  ⟶ p.4 L6", "bar"),
                ("Cash buffer (days of opex)                   23  ⟶ calc", "bar"),
                ("Click any figure: the source line is highlighted in the viewer", "muted")])
    small_mock(f"{OUT}/mock_objections.png", "3 · Challenger objections",
               [("CRITICAL  Revenue double-counted (Shopee payout + dashboard)", "hl"),
                ("HIGH      Receipt image #07 reused as #12, date edited", "bar"),
                ("MEDIUM    Monthly VND 4.15M transfer looks like a loan", "bar"),
                ("Each objection: claim · evidence refs · suggested action", "muted"),
                ("Accept  /  Dismiss", "btn")], accent=AMBER)
    small_mock(f"{OUT}/mock_decision.png", "4 · Underwriter decision and customer letter",
               [("Decision: APPROVE WITH CONDITIONS", "text"),
                ("Accepted 2 objections · dismissed 1 · reason logged", "muted"),
                ("Conditions: revenue restated to VND 39.7M; disclose VPBank loan", "bar"),
                ("Customer letter (Vietnamese): generated, 142 words", "bar"),
                ("Audit log: 5 agent calls · prompt v0.3 · 2m 41s · USD 0.28", "muted")])
    print("ok")
