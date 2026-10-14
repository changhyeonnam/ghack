"""Receipt photos: case A supplier receipts (thermal + handwritten 'nota') and case B logistics
drop-off receipts (GHN / J&T thermal). PIL renders a flat document, then `photo_effect` turns it
into a phone-photo look."""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from profiles import days_in_month, fmt_amount, font, norm_bbox, photo_effect, round_to, save_jpg, text_size, watermark

PAPER = (247, 244, 234)
INK = (35, 35, 40)

# --------------------------------------------------------------------------------------
# Case A plan
# --------------------------------------------------------------------------------------
A_MERCHANTS = {
    "Toko Grosir Makmur": {"prefix": "TGM", "addr": "Jl. Ciledug Raya No. 88, Jakarta Selatan", "tel": "021-7391xxxx", "transfer": True},
    "Grosir Sembako Barokah": {"prefix": "GSB", "addr": "Pasar Kebayoran Lama Blok C-12", "tel": "0812-9xxx-4410", "transfer": True},
    "CV Sumber Rejeki": {"prefix": "SR", "addr": "Jl. Raya Pondok Indah No. 21", "tel": "021-7501xxxx", "transfer": True},
    "Toko Plastik Anugerah": {"prefix": "TPA", "addr": "Pasar Mayestik Lt.1 No.44", "tel": "0813-1xxx-2203", "transfer": False},
    "Agen Minuman Sinar Jaya": {"prefix": "SJ", "addr": "Jl. Bintaro Utama Blok B-7", "tel": "021-7367xxxx", "transfer": False},
}
A_HAND_MERCHANTS = {
    "Agen Gas & Galon Pak Udin": {"addr": "Gg. Mawar III No. 5"},
    "Warung Sayur Bu Tini": {"addr": "Pasar Kebayoran Lama"},
    "Toko Telur Pak Yanto": {"addr": "Jl. Ciledug Raya Gg. 4"},
}
A_ITEMS = [
    ("Beras Premium 25kg", 310_000), ("Minyak Goreng 2L", 34_000), ("Gula Pasir 1kg", 17_500),
    ("Mie Instan 1 dus (40)", 112_000), ("Telur Ayam 1 peti 15kg", 420_000), ("Kopi Sachet 1 renceng", 12_000),
    ("Tepung Terigu 1kg", 13_000), ("Kecap Manis 600ml", 24_000), ("Sabun Mandi 1 lusin", 48_000),
    ("Deterjen 800g", 21_000), ("Teh Celup 1 dus", 55_000), ("Susu Kental Manis 1 dus", 460_000),
    ("Air Mineral 1 dus (48)", 42_000), ("Snack Ringan 1 dus", 98_000), ("Biskuit 1 dus", 130_000),
    ("Bawang Merah 1kg", 38_000), ("Cabai Rawit 1kg", 65_000), ("Garam 1kg", 9_000),
    ("Kantong Plastik 1 pak", 15_000), ("Tisu 1 dus", 86_000), ("Shampo Sachet 1 renceng", 18_000),
    ("Minuman Botol 1 krat", 72_000), ("Pasta Gigi 1 lusin", 96_000), ("Obat Nyamuk 1 dus", 54_000),
]
A_HAND_ITEMS = {
    "Agen Gas & Galon Pak Udin": [("Gas LPG 3kg", 22_000), ("Galon isi ulang", 6_000), ("Gas LPG 12kg", 215_000)],
    "Warung Sayur Bu Tini": [("Sayur campur", 25_000), ("Tomat 1kg", 14_000), ("Kentang 1kg", 18_000), ("Wortel 1kg", 12_000),
                             ("Bawang putih 1kg", 36_000), ("Cabai merah 1kg", 48_000)],
    "Toko Telur Pak Yanto": [("Telur ayam 1 peti", 410_000), ("Telur puyuh 1kg", 38_000), ("Telur bebek 1 tray", 85_000)],
}


def plan_receipts_a(rng: random.Random) -> list[dict]:
    recs = []
    months = [1, 1, 1, 2, 2, 3, 3, 3, 4, 4, 5, 5, 5, 6, 6]
    hand_slots = {2, 7, 12}  # indices that are handwritten
    hand_names = list(A_HAND_MERCHANTS)
    printed_names = list(A_MERCHANTS)
    counters = {m: rng.randint(400, 1800) for m in printed_names}
    transfer_count = 0
    for i, month in enumerate(months):
        days = [d for d in days_in_month(2026, month) if d.weekday() < 6]
        d = rng.choice(days)
        if i in hand_slots:
            merchant = hand_names[len([k for k in hand_slots if k < i])]
            pool = A_HAND_ITEMS[merchant]
            items = []
            for name, price in rng.sample(pool, min(len(pool), rng.randint(2, 3))):
                qty = rng.randint(2, 12) if price < 50_000 else rng.randint(1, 3)
                items.append({"description": f"{name} x{qty}", "qty": qty, "unit_price": price, "amount": qty * price})
            total = sum(it["amount"] for it in items)
            while total < 300_000:
                it = rng.choice(items)
                it["qty"] += 1
                it["amount"] = it["qty"] * it["unit_price"]
                it["description"] = it["description"].rsplit(" x", 1)[0] + f" x{it['qty']}"
                total = sum(x["amount"] for x in items)
            recs.append({
                "filename": f"receipt_{i + 1:02d}.jpg", "merchant": merchant, "date": d,
                "receipt_number": f"{rng.randint(1, 99):03d}", "currency": "IDR", "total": total,
                "direction": "purchase", "handwritten": True, "items": items, "paid_by_transfer": False,
                "merchant_meta": A_HAND_MERCHANTS[merchant],
            })
            continue
        merchant = rng.choice(printed_names)
        meta = A_MERCHANTS[merchant]
        items = []
        for name, price in rng.sample(A_ITEMS, rng.randint(3, 7)):
            qty = rng.randint(1, 6) if price < 100_000 else rng.randint(1, 3)
            items.append({"description": name, "qty": qty, "unit_price": price, "amount": qty * price})
        total = sum(it["amount"] for it in items)
        guard = 0
        while (total < 300_000 or total > 3_000_000) and guard < 50:
            guard += 1
            it = rng.choice(items)
            if total < 300_000:
                it["qty"] += 1
            elif it["qty"] > 1:
                it["qty"] -= 1
            it["amount"] = it["qty"] * it["unit_price"]
            total = sum(x["amount"] for x in items)
        counters[merchant] += rng.randint(3, 40)
        paid = meta["transfer"] and transfer_count < 6 and rng.random() < 0.75
        if paid:
            transfer_count += 1
        recs.append({
            "filename": f"receipt_{i + 1:02d}.jpg", "merchant": merchant, "date": d,
            "receipt_number": f"{meta['prefix']}-{counters[merchant]:04d}", "currency": "IDR", "total": total,
            "direction": "purchase", "handwritten": False, "items": items, "paid_by_transfer": paid,
            "merchant_meta": meta,
        })
    return recs


# --------------------------------------------------------------------------------------
# Thermal receipt renderer
# --------------------------------------------------------------------------------------
def _thermal(lines: list[tuple[str, str, str]], width=560, seed=0):
    """lines: (text, align, style) with align in l/c/r and style in n/b/big. Returns flat image + row boxes."""
    f_n = font("mono", 21)
    f_b = font("mono_bold", 21)
    f_big = font("mono_bold", 27)
    lh = 29
    h = 90 + lh * len(lines) + 140
    img = Image.new("RGB", (width, h), PAPER)
    d = ImageDraw.Draw(img)
    y = 44
    boxes = []
    for text, align, style in lines:
        f = {"n": f_n, "b": f_b, "big": f_big}[style]
        if text == "---":
            d.text((18, y), "-" * 40, font=f_n, fill=INK)
        else:
            tw, th = text_size(d, text, f)
            x = {"l": 20, "c": (width - tw) // 2, "r": width - 20 - tw}[align]
            d.text((x, y), text, font=f, fill=INK)
        boxes.append([14, y - 2, width - 14, y + lh - 2])
        y += lh if style != "big" else lh + 8
    # barcode
    r = random.Random(seed)
    bx = 90
    y += 20
    while bx < width - 90:
        wbar = r.choice([2, 2, 3, 4])
        d.rectangle([bx, y, bx + wbar, y + 54], fill=INK)
        bx += wbar + r.choice([2, 3, 4])
    # fade (thermal paper prints slightly unevenly)
    return img, boxes


def render_receipt_printed(rec: dict, out: Path, seed: int) -> dict:
    meta = rec["merchant_meta"]
    cur = rec["currency"]
    lines = [
        (rec["merchant"].upper(), "c", "big"),
        (meta["addr"], "c", "n"),
        (f"Telp {meta['tel']}", "c", "n"),
        ("---", "l", "n"),
        (f"No. Nota : {rec['receipt_number']}", "l", "n"),
        (f"Tanggal  : {rec['date']:%d/%m/%Y} {random.Random(seed).randint(8, 17):02d}:{random.Random(seed + 1).randint(0, 59):02d}", "l", "n"),
        (f"Kasir    : {random.Random(seed + 2).choice(['RINA', 'DEDI', 'YUNI', 'AGUS'])}", "l", "n"),
        ("Pelanggan: WARUNG IBU SARI", "l", "n"),
        ("---", "l", "n"),
    ]
    item_line_idx = []
    for it in rec["items"]:
        lines.append((it["description"], "l", "n"))
        qty_line = f"  {it['qty']} x {fmt_amount(it['unit_price'], cur):>10}"
        amt = fmt_amount(it["amount"], cur)
        pad = 40 - len(qty_line) - len(amt)
        lines.append((qty_line + " " * max(1, pad) + amt, "l", "n"))
        item_line_idx.append(len(lines) - 1)
    lines.append(("---", "l", "n"))
    tot = fmt_amount(rec["total"], cur)
    lines.append((f"TOTAL{tot:>35}", "l", "b"))
    total_idx = len(lines) - 1
    if rec["paid_by_transfer"]:
        lines.append((f"TRANSFER{tot:>32}", "l", "n"))
        lines.append(("KEMBALI" + f"{'0':>33}", "l", "n"))
    else:
        cash = round_to(rec["total"] + 60_000, 50_000)
        lines.append((f"TUNAI{fmt_amount(cash, cur):>35}", "l", "n"))
        lines.append((f"KEMBALI{fmt_amount(cash - rec['total'], cur):>33}", "l", "n"))
    lines.append(("---", "l", "n"))
    lines.append(("TERIMA KASIH", "c", "b"))
    lines.append(("Barang yang sudah dibeli", "c", "n"))
    lines.append(("tidak dapat ditukar/dikembalikan", "c", "n"))
    flat, boxes = _thermal(lines, seed=seed)
    img, mb = photo_effect(flat, seed=seed, pad=50)
    W, H = img.size
    img = watermark(img, scale=0.8)
    save_jpg(img, out)
    b = mb(boxes[total_idx])
    return {"total_bbox": norm_bbox(*b, W, H), "image_size": [W, H]}


# --------------------------------------------------------------------------------------
# Handwritten 'nota' renderer
# --------------------------------------------------------------------------------------
def render_receipt_handwritten(rec: dict, out: Path, seed: int) -> dict:
    r = random.Random(seed)
    width, height = 640, 860
    img = Image.new("RGB", (width, height), (255, 246, 214))
    d = ImageDraw.Draw(img)
    f_head = font("sans_bold", 28)
    f_small = font("sans", 15)
    hand = r.choice(["hand", "hand2", "hand3"])
    f_hand = font(hand, 27)
    f_hand_big = font(hand, 34)
    ink = r.choice([(25, 35, 110), (30, 30, 30), (20, 60, 130)])
    # printed pad header
    d.text((30, 26), rec["merchant"].upper(), font=f_head, fill=(120, 20, 20))
    d.text((30, 62), rec["merchant_meta"]["addr"], font=f_small, fill=(90, 90, 90))
    d.text((width - 150, 30), "NOTA", font=f_head, fill=(120, 20, 20))
    d.text((width - 150, 66), "No.", font=f_small, fill=(90, 90, 90))
    d.text((width - 115, 56), rec["receipt_number"], font=f_hand, fill=ink)
    d.text((30, 100), "Tanggal:", font=f_small, fill=(90, 90, 90))
    d.text((100, 88), f"{rec['date'].day}/{rec['date'].month}/{rec['date'].year % 100}", font=f_hand, fill=ink)
    d.text((300, 100), "Kepada Yth:", font=f_small, fill=(90, 90, 90))
    d.text((395, 86), "Warung Ibu Sari", font=f_hand, fill=ink)
    # table
    cols = [30, 120, 400, 510, width - 30]
    top, rowh, nrows = 140, 52, 9
    d.rectangle([cols[0], top, cols[-1], top + rowh * (nrows + 1)], outline=(150, 60, 60), width=2)
    for i in range(1, nrows + 1):
        d.line([cols[0], top + rowh * i, cols[-1], top + rowh * i], fill=(200, 120, 120), width=1)
    for cx in cols[1:-1]:
        d.line([cx, top, cx, top + rowh * (nrows + 1)], fill=(150, 60, 60), width=2)
    for cx, name in zip(cols, ["Banyaknya", "Nama Barang", "Harga", "Jumlah"]):
        d.text((cx + 8, top + 16), name, font=f_small, fill=(120, 20, 20))
    boxes = {}
    y = top + rowh + 8
    for it in rec["items"]:
        jit = r.randint(-3, 3)
        name = it["description"].rsplit(" x", 1)[0]
        d.text((cols[0] + 20 + r.randint(-3, 3), y + jit), str(it["qty"]), font=f_hand, fill=ink)
        d.text((cols[1] + 12 + r.randint(-3, 3), y + jit), name, font=f_hand, fill=ink)
        d.text((cols[2] + 8, y + jit), fmt_amount(it["unit_price"], "IDR"), font=f_hand, fill=ink)
        d.text((cols[3] + 8, y + jit), fmt_amount(it["amount"], "IDR"), font=f_hand, fill=ink)
        y += rowh
    ty = top + rowh * (nrows + 1) + 14
    d.text((cols[2] - 110, ty + 6), "Jumlah Rp.", font=f_small, fill=(120, 20, 20))
    d.text((cols[3] + 2, ty - 6), fmt_amount(rec["total"], "IDR"), font=f_hand_big, fill=ink)
    tb = d.textbbox((cols[3] + 2, ty - 6), fmt_amount(rec["total"], "IDR"), font=f_hand_big)
    d.line([cols[3], ty + 38, cols[-1], ty + 38], fill=ink, width=2)
    d.line([cols[3], ty + 42, cols[-1], ty + 42], fill=ink, width=2)
    # "Lunas" stamp + signature scribble
    d.text((60, ty + 10), "Tanda terima,", font=f_small, fill=(90, 90, 90))
    pts = []
    x0, y0 = 70, ty + 70
    for k in range(40):
        pts.append((x0 + k * 4 + r.randint(-2, 2), y0 + int(18 * __import__("math").sin(k / 2.2)) + r.randint(-2, 2)))
    d.line(pts, fill=ink, width=3)
    d.text((70, ty + 95), "LUNAS", font=font("sans_bold", 22), fill=(200, 40, 40))
    d.rectangle([62, ty + 90, 150, ty + 124], outline=(200, 40, 40), width=2)
    flat = img
    img, mb = photo_effect(flat, seed=seed, pad=50, noise=5.5)
    W, H = img.size
    img = watermark(img, scale=0.8)
    save_jpg(img, out)
    b = mb([tb[0] - 4, tb[1] - 4, tb[2] + 4, tb[3] + 4])
    return {"total_bbox": norm_bbox(*b, W, H), "image_size": [W, H]}


def ground_truth_receipts_a(recs: list[dict], extras: dict) -> list[dict]:
    out = []
    for r in recs:
        out.append({
            "filename": r["filename"], "merchant": r["merchant"], "date": r["date"].isoformat(),
            "receipt_number": r["receipt_number"], "currency": r["currency"], "total": r["total"],
            "direction": r["direction"], "handwritten": r["handwritten"],
            "paid_by_bank_transfer": r["paid_by_transfer"],
            "items": [{"description": it["description"] if r["handwritten"] else f"{it['description']} x{it['qty']}",
                       "amount": it["amount"]} for it in r["items"]],
            "total_bbox": extras[r["filename"]]["total_bbox"], "image_size": extras[r["filename"]]["image_size"],
            "trap_ids": [],
        })
    return out


# --------------------------------------------------------------------------------------
# Case B logistics receipts (GHN / J&T)
# --------------------------------------------------------------------------------------
def plan_logistics_b(rng: random.Random) -> list[dict]:
    def waybills(prefix, n, seed):
        r = random.Random(seed)
        items = []
        for i in range(n):
            wgt = r.choice([250, 300, 350, 450, 500, 600, 750, 900, 1200])
            fee = {250: 18_000, 300: 18_000, 350: 20_000, 450: 22_000, 500: 22_000, 600: 25_000, 750: 27_000, 900: 30_000, 1200: 36_000}[wgt]
            cod = r.choice([0, 0, 189_000, 259_000, 320_000, 415_000, 540_000, 680_000])
            items.append({"description": f"{prefix}{r.randint(100000, 999999)}A ({wgt}g)", "weight_g": wgt, "amount": fee, "cod": cod})
        return items

    recs = []
    specs = [
        ("ghn_receipt_01.jpg", "GHN", "GHN-2187", date(2026, 1, 22), 7, 101),
        ("ghn_receipt_02.jpg", "GHN", "GHN-2231", date(2026, 2, 11), 6, 102),  # T08 original
        ("ghn_receipt_03.jpg", "GHN", "GHN-2305", date(2026, 3, 27), 8, 103),
        ("ghn_receipt_04.jpg", "GHN", "GHN-2378", date(2026, 4, 22), 5, 104),
        ("ghn_receipt_05.jpg", "GHN", "GHN-2231", date(2026, 3, 11), 6, 102),  # T08 duplicate (same seed)
        ("jt_receipt_01.jpg", "J&T", "JT-77109", date(2026, 5, 6), 7, 106),
    ]
    for fname, carrier, number, d, n, seed in specs:
        items = waybills("GHN" if carrier == "GHN" else "JT", n, seed)
        recs.append({
            "filename": fname, "carrier": carrier, "receipt_number": number, "date": d, "items": items,
            "total": sum(i["amount"] for i in items), "cod_collected": sum(i["cod"] for i in items),
            "time": f"{random.Random(seed).randint(9, 17):02d}:{random.Random(seed + 7).randint(0, 59):02d}",
            "staff": random.Random(seed + 3).choice(["NV0421 - T.HUNG", "NV0377 - M.TRANG", "NV0502 - Q.BAO"]),
            "photo_seed": 5000 + seed,
            "trap_ids": ["T08"] if number == "GHN-2231" else [],
        })
    return recs


def render_logistics(rec: dict, out: Path) -> dict:
    ghn = rec["carrier"] == "GHN"
    lines = [
        ("GHN EXPRESS" if ghn else "J&T EXPRESS", "c", "big"),
        ("GIAO HANG NHANH (synthetic)" if ghn else "CHUYEN PHAT NHANH (synthetic)", "c", "n"),
        ("BC TAN BINH 02 - 128 CONG HOA, P.4" if ghn else "BUU CUC TAN BINH 05 - 77 TRUONG CHINH", "c", "n"),
        ("Hotline 1900 xxxx", "c", "n"),
        ("---", "l", "n"),
        ("BIEN NHAN GUI HANG / PICKUP RECEIPT", "c", "b"),
        (f"So bien nhan : {rec['receipt_number']}", "l", "n"),
        (f"Ngay gio     : {rec['date']:%d/%m/%Y} {rec['time']}", "l", "n"),
        ("Nguoi gui    : LINH FASHION OFFICIAL", "l", "n"),
        ("SDT          : 09xx xxx 331", "l", "n"),
        ("Dia chi lay  : 45/12 CONG HOA, TAN BINH", "l", "n"),
        ("---", "l", "n"),
        ("MA VAN DON            KL(g)      CUOC", "l", "b"),
    ]
    for it in rec["items"]:
        code = it["description"].split(" ")[0]
        lines.append((f"{code:<20}{it['weight_g']:>6}{fmt_amount(it['amount'], 'VND'):>12}", "l", "n"))
    lines += [
        ("---", "l", "n"),
        (f"Tong so kien : {len(rec['items'])}", "l", "n"),
        (f"Tong cuoc    : {fmt_amount(rec['total'], 'VND')}", "l", "b"),
        (f"Thu ho (COD) : {fmt_amount(rec['cod_collected'], 'VND')}", "l", "n"),
        ("Hinh thuc TT : TRU VAO VI " + ("GHN" if ghn else "J&T"), "l", "n"),
        ("---", "l", "n"),
        (f"Nhan vien: {rec['staff']}", "l", "n"),
        ("Cam on quy khach!", "c", "b"),
        ("Tra cuu don: ghn.vn/tracking" if ghn else "Tra cuu don: jtexpress.vn", "c", "n"),
    ]
    flat, boxes = _thermal(lines, seed=rec["photo_seed"])
    img, mb = photo_effect(flat, seed=rec["photo_seed"], pad=50)
    W, H = img.size
    img = watermark(img, scale=0.8)
    save_jpg(img, out)
    total_idx = next(i for i, l in enumerate(lines) if l[0].startswith("Tong cuoc"))
    date_idx = next(i for i, l in enumerate(lines) if l[0].startswith("Ngay gio"))
    return {"total_bbox": norm_bbox(*mb(boxes[total_idx]), W, H), "date_bbox": norm_bbox(*mb(boxes[date_idx]), W, H),
            "image_size": [W, H]}


def ground_truth_logistics(recs: list[dict], extras: dict) -> list[dict]:
    out = []
    for r in recs:
        e = extras[r["filename"]]
        o = {
            "filename": r["filename"], "merchant": "GHN Express" if r["carrier"] == "GHN" else "J&T Express",
            "date": r["date"].isoformat(), "receipt_number": r["receipt_number"], "currency": "VND",
            "total": r["total"], "direction": "expense", "handwritten": False, "doc_type": "logistics_receipt",
            "cod_collected": r["cod_collected"], "parcels": len(r["items"]),
            "items": [{"description": it["description"], "amount": it["amount"]} for it in r["items"]],
            "total_bbox": e["total_bbox"], "date_bbox": e["date_bbox"], "image_size": e["image_size"],
            "trap_ids": r["trap_ids"],
        }
        if r["filename"] == "ghn_receipt_05.jpg":
            o["duplicate_of"] = "ghn_receipt_02.jpg"
        out.append(o)
    return out
