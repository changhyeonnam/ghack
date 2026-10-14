"""Case C handwritten ledger pages (PIL): lined notebook paper, handwriting font, Filipino headers.

Pages: p1 Enero, p2 Pebrero, p3 Marso, p4 Abril, p5 Mayo, p6 "Abril" (= p3 re-photographed with the
month header changed, trap T15), p7 Hunyo, p8 Buod (half-year summary)."""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from profiles import FIL_MONTHS, days_in_month, font, norm_bbox, photo_effect, round_to, save_jpg, watermark

JOBS = [
    ("Change oil - Toyota Vios", 1500, 2200), ("Brake pads - Honda City", 2800, 4200),
    ("Tune up - Mitsubishi Mirage", 2500, 3800), ("Aircon cleaning - Innova", 2200, 3500),
    ("Battery replace - Hyundai Accent", 4500, 6000), ("Palit gulong x2 - Fortuner", 4000, 6000),
    ("Wheel alignment - Montero", 1500, 2500), ("Check engine - Avanza", 1800, 3200),
    ("Fan belt - Hilux", 1600, 2600), ("Clutch adjust - Wigo", 1500, 2400),
    ("Underchassis - Civic", 2600, 4200), ("Palit bumbilya + wiper - Vios", 1500, 1900),
    ("Radiator flush - Adventure", 2000, 3000), ("Palit brake fluid - Mirage", 1500, 2100),
    ("Suspension bushing - Innova", 3500, 5500), ("Overhaul deposit - L300", 5000, 6000),
    ("Change oil + filter - Raize", 1800, 2600), ("Alternator repair - Crosswind", 3800, 5800),
    ("Aircon freon - City", 1800, 2800), ("Palit shock absorber - Xpander", 4200, 6000),
]
EXPENSES = [
    ("Bili parts - Banawe", 1800, 5200), ("Langis 4L x5 (gastos)", 2000, 2800), ("Sweldo ni Boy", 3500, 4500),
    ("Kuryente - Meralco (cash)", 1200, 2400), ("Tubig + yelo", 300, 600), ("Bili sandpaper, grease", 400, 900),
    ("Pamasahe - delivery parts", 250, 500), ("Bayad welding gas", 900, 1500),
]
HOLIDAYS = {date(2026, 1, 1), date(2026, 4, 2), date(2026, 4, 3), date(2026, 4, 9), date(2026, 5, 1), date(2026, 6, 12)}


def plan_ledger(rng: random.Random) -> dict[int, list[dict]]:
    """Return {month: [entries]} for the 6 genuine months. Entries carry date/day/description/amount/kind."""
    months = {}
    for m in range(1, 7):
        entries = []
        exp_days = set(rng.sample([d for d in days_in_month(2026, m) if d.weekday() < 6 and d.day > 2], rng.randint(2, 4)))
        week_sum = 0.0
        last_in_week = None
        days = list(days_in_month(2026, m))
        if m == 3:  # March page stops at the 30th so the re-labelled copy (T15) has only valid April days
            days = days[:-1]
        for d in days:
            if d.weekday() == 6:  # Sunday closed
                continue
            skip = d in HOLIDAYS or rng.random() < 0.17
            if not skip:
                job, lo, hi = rng.choice(JOBS)
                amt = float(round_to(rng.uniform(lo, hi), 50))
                entries.append({"date": d, "day": d.day, "description": job, "amount": amt, "kind": "income"})
                week_sum += amt
                last_in_week = d
            if d in exp_days:
                ename, lo, hi = rng.choice(EXPENSES)
                entries.append({"date": d, "day": d.day, "description": ename, "amount": float(round_to(rng.uniform(lo, hi), 50)),
                                "kind": "expense"})
            # close the week on Saturday (or month end)
            if (d.weekday() == 5 or d == days[-1]) and week_sum > 0:
                entries.append({"date": d, "day": d.day, "description": "Kabuuan ng linggo", "amount": week_sum,
                                "kind": "weekly_total"})
                week_sum = 0.0
        months[m] = entries
    return months


def income_list(months: dict[int, list[dict]]):
    return [(e["date"], e["amount"]) for m in months.values() for e in m if e["kind"] == "income"]


def _page_header(d, f_big, f_mid, business, period):
    d.text((80, 58), business, font=f_big, fill=(25, 30, 90))
    bb = d.textbbox((80, 58), business, font=f_big)
    d.text((bb[2] + 24, 70), f"·  {period}", font=f_mid, fill=(25, 30, 90))
    d.line([80, 128, 1120, 128], fill=(25, 30, 90), width=3)


def render_ledger_page(entries: list[dict], period_label: str, seed: int, business="Reyes Auto Repair",
                       summary: bool = False):
    """Render a ledger page. Returns (flat_image, row_boxes). Deterministic for (entries, seed)."""
    r = random.Random(seed)
    W, H = 1200, 1600
    img = Image.new("RGB", (W, H), (251, 248, 238))
    d = ImageDraw.Draw(img)
    # notebook rules
    for y in range(180, H - 40, 44):
        d.line([40, y, W - 40, y], fill=(176, 196, 222), width=2)
    d.line([150, 40, 150, H - 40], fill=(222, 120, 120), width=3)
    # punched holes
    for y in (300, 800, 1300):
        d.ellipse([18, y - 14, 46, y + 14], fill=(225, 222, 215), outline=(200, 196, 190))
    f_big = font("hand", 52)
    f_mid = font("hand", 40)
    f_row = font("hand", 29)
    f_hdr = font("hand", 32)
    ink = (28, 34, 92)
    _page_header(d, f_big, f_mid, business, period_label)
    boxes = []
    if summary:
        d.text((170, 150), "Buwan", font=f_hdr, fill=ink)
        d.text((560, 150), "Kita", font=f_hdr, fill=ink)
        d.text((820, 150), "Gastos", font=f_hdr, fill=ink)
        d.text((1020, 150), "Neto", font=f_hdr, fill=ink)
        y = 222
        for e in entries:
            jit = r.randint(-2, 2)
            d.text((170 + r.randint(-2, 2), y + jit), e["description"], font=f_row, fill=ink)
            d.text((560, y + jit), f"{e['income']:,.0f}", font=f_row, fill=ink)
            d.text((820, y + jit), f"{e['expense']:,.0f}", font=f_row, fill=ink)
            d.text((1020, y + jit), f"{e['amount']:,.0f}", font=f_row, fill=ink)
            boxes.append([150, y - 8, W - 40, y + 36])
            y += 44 if not e.get("total") else 44
            if e.get("total"):
                d.line([540, y - 50, 1160, y - 50], fill=ink, width=2)
        y += 30
        d.text((170, y), "Kabuuang kita Enero-Hunyo 2026:", font=f_row, fill=ink)
        d.text((820, y), f"{sum(e['income'] for e in entries if not e.get('total')):,.0f}", font=f_row, fill=ink)
        boxes.append([150, y - 8, W - 40, y + 36])
        return img, boxes
    d.text((62, 150), "Petsa", font=f_hdr, fill=ink)
    d.text((172, 150), "Deskripsyon", font=f_hdr, fill=ink)
    d.text((1000, 150), "Halaga", font=f_hdr, fill=ink)
    y = 222
    for e in entries:
        jit = r.randint(-2, 2)
        xj = r.randint(-3, 3)
        if e["kind"] == "weekly_total":
            d.text((172 + xj, y + jit), e["description"], font=f_row, fill=ink)
            amt = f"= {e['amount']:,.0f}"
            tb = d.textbbox((0, 0), amt, font=f_row)
            d.text((1150 - tb[2], y + jit), amt, font=f_row, fill=ink)
            d.line([960, y + 38, 1152, y + 38], fill=ink, width=2)
        else:
            d.text((70 + xj, y + jit), str(e["day"]), font=f_row, fill=ink)
            desc = e["description"]
            d.text((172 + xj, y + jit), desc, font=f_row, fill=ink)
            amt = f"{e['amount']:,.0f}" if e["kind"] == "income" else f"-{e['amount']:,.0f}"
            tb = d.textbbox((0, 0), amt, font=f_row)
            d.text((1150 - tb[2], y + jit), amt, font=f_row, fill=ink)
        boxes.append([44, y - 8, W - 40, y + 36])
        y += 44
    return img, boxes


def build_pages(months: dict[int, list[dict]]):
    """Return page specs in render order (p1..p8)."""
    def with_month(entries, m):
        out = []
        for e in entries:
            e2 = dict(e)
            e2["date"] = date(2026, m, e["day"])
            out.append(e2)
        return out

    pages = [
        {"filename": "ledger_p1.jpg", "month": 1, "entries": months[1], "seed": 101},
        {"filename": "ledger_p2.jpg", "month": 2, "entries": months[2], "seed": 102},
        {"filename": "ledger_p3.jpg", "month": 3, "entries": months[3], "seed": 103},
        {"filename": "ledger_p4.jpg", "month": 4, "entries": months[4], "seed": 104},
        {"filename": "ledger_p5.jpg", "month": 5, "entries": months[5], "seed": 105},
        # T15: same page as p3, header says Abril; entries identical (dates re-labelled to April)
        {"filename": "ledger_p6.jpg", "month": 4, "entries": with_month(months[3], 4), "seed": 103,
         "duplicate_of": "ledger_p3.jpg", "trap_ids": ["T15"]},
        {"filename": "ledger_p7.jpg", "month": 6, "entries": months[6], "seed": 107},
    ]
    summary = []
    for m in range(1, 7):
        inc = sum(e["amount"] for e in months[m] if e["kind"] == "income")
        exp = sum(e["amount"] for e in months[m] if e["kind"] == "expense")
        summary.append({"date": list(days_in_month(2026, m))[-1], "day": None, "description": FIL_MONTHS[m],
                        "income": inc, "expense": exp, "amount": inc - exp, "kind": "monthly_total"})
    pages.append({"filename": "ledger_p8.jpg", "month": None, "entries": summary, "seed": 108, "summary": True,
                  "period_label": "Buod Enero-Hunyo 2026"})
    return pages


def render_pages(pages: list[dict], out_dir: Path) -> list[dict]:
    gt = []
    row_counter = 0
    for p in pages:
        label = p.get("period_label") or f"{FIL_MONTHS[p['month']]} 2026"
        flat, boxes = render_ledger_page(p["entries"], label, p["seed"], summary=p.get("summary", False))
        angle = random.Random(p["seed"] * 7 + 1).uniform(-1.3, 1.3)
        img, mb = photo_effect(flat, seed=p["seed"], angle=angle, pad=45, noise=4.5, bg=(72, 60, 52))
        W, H = img.size
        img = watermark(img, scale=1.1)
        save_jpg(img, out_dir / p["filename"], quality=82)
        entries = []
        for e, b in zip(p["entries"], boxes):
            row_counter += 1
            ent = {
                "row_id": f"L{row_counter:04d}", "date": e["date"].isoformat(), "description": e["description"],
                "amount": e["amount"], "kind": e["kind"], "bbox": norm_bbox(*mb(b), W, H),
            }
            if e["kind"] == "monthly_total":
                ent["income"] = e["income"]
                ent["expense"] = e["expense"]
            entries.append(ent)
        item = {
            "filename": p["filename"], "period_label": label, "business_name_header": "Reyes Auto Repair",
            "month": f"2026-{p['month']:02d}" if p["month"] else None, "image_size": [W, H],
            "income_total": sum(e["amount"] for e in p["entries"] if e["kind"] == "income"),
            "entries": entries, "trap_ids": list(p.get("trap_ids", [])),
        }
        if p.get("duplicate_of"):
            item["duplicate_of"] = p["duplicate_of"]
        if p["filename"] in ("ledger_p1.jpg", "ledger_p2.jpg", "ledger_p4.jpg", "ledger_p5.jpg", "ledger_p7.jpg"):
            item["trap_ids"].append("T19")
        gt.append(item)
    return gt
