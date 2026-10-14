"""Shopee-like seller centre captures for case B (PIL, 1600x1000 PNG) + the monthly sales plan
that the bank statement must agree with (payout batches, COD value)."""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from profiles import days_in_month, fmt_amount, font, norm_bbox, round_to, save_png, text_size, watermark

W, H = 1600, 1000
ORANGE = (238, 77, 45)
GREY = (120, 120, 120)
DARK = (34, 34, 34)
LINE = (229, 229, 229)

FOLLOWERS = {1: 12_400, 2: 12_900, 3: 9_800, 4: 13_600, 5: 13_900, 6: 14_200}  # T09 in March
RATING = {1: 4.9, 2: 4.9, 3: 4.8, 4: 4.9, 5: 4.9, 6: 4.9}
BASE_GMV = {12: 44_600_000, 1: 48_200_000, 2: 41_650_000, 3: 52_600_000, 4: 55_100_000, 5: 58_300_000, 6: 61_050_000}
PRODUCTS = ["Áo thun basic cotton", "Váy hoa vintage", "Quần jean ống rộng", "Set đồ bộ nữ",
            "Áo sơ mi linen"]


def plan_months(rng: random.Random):
    """Plan Dec 2025..Jun 2026. Dec has no dashboard (T10); Jun has no bank statement (T10)."""
    plan = []
    for (y, m) in [(2025, 12), (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6)]:
        gmv = BASE_GMV[m] + round_to(rng.uniform(-900_000, 900_000), 10_000)
        ratio = rng.uniform(0.885, 0.915)
        payout = round_to(gmv * ratio, 1000)
        cod_value = round_to(gmv * rng.uniform(0.28, 0.36), 10_000)
        orders = int(gmv / rng.uniform(145_000, 165_000))
        visitors = orders * rng.randint(27, 34)
        days = list(days_in_month(y, m))
        weights = [rng.uniform(0.6, 1.4) * (1.35 if d.weekday() >= 5 else 1.0) for d in days]
        s = sum(weights)
        daily = [round_to(gmv * w / s, 1000) for w in weights]
        daily[-1] += gmv - sum(daily)
        k = rng.randint(2, 4)
        batch_days = {2: [14, 28], 3: [9, 19, 29], 4: [7, 14, 21, 28]}[k]
        amounts = []
        wts = [rng.uniform(0.7, 1.3) for _ in range(k)]
        for wgt in wts[:-1]:
            amounts.append(round_to(payout * wgt / sum(wts), 1000))
        amounts.append(payout - sum(amounts))
        batches = [(date(y, m, bd), a) for bd, a in zip(batch_days, amounts)]
        nxt = days[-1] + timedelta(days=1)
        plan.append({
            "year": y, "month": m, "gross_sales": gmv, "payout": payout, "cod_value": cod_value,
            "orders": orders, "visitors": visitors, "followers": FOLLOWERS.get(m), "rating": RATING.get(m),
            "daily": daily, "payout_batches": batches, "data_as_of": nxt,
            "shop_name": "Linh Fashion VN" if m == 3 else "Linh Fashion Official",
            "period_start": days[0], "period_end": days[-1],
        })
    return plan


def _vn(n: int) -> str:
    return fmt_amount(n, "VND")


def render_dashboard(mp: dict, out_png: Path, rng: random.Random) -> dict:
    img = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(img)
    f_logo = font("sans_black", 30)
    f_uni = font("unicode", 18)
    f_uni_s = font("unicode", 15)
    f_title = font("sans_bold", 30)
    f_val = font("sans_bold", 31)
    f_dong = font("unicode", 22)
    f_lab = font("unicode", 16)
    f_small = font("unicode", 13)
    f_tab = font("unicode", 16)
    f_tab_b = font("sans_bold", 16)

    # top bar
    d.rectangle([0, 0, W, 60], fill=ORANGE)
    d.text((24, 11), "Shopee", font=f_logo, fill="white")
    d.text((150, 20), "Kênh Người Bán • Seller Centre", font=f_uni, fill=(255, 230, 220))
    d.text((W - 330, 20), "linhfashion.official", font=f_uni, fill="white")
    d.ellipse([W - 80, 14, W - 48, 46], fill=(255, 255, 255))
    d.text((W - 71, 20), "L", font=font("sans_bold", 20), fill=ORANGE)

    # sidebar
    d.rectangle([0, 60, 200, H], fill="white")
    d.line([200, 60, 200, H], fill=LINE, width=1)
    menu = ["Trang chủ", "Đơn hàng", "Sản phẩm", "Marketing", "Tài chính",
            "Dữ liệu", "Chăm sóc khách hàng", "Cài đặt"]
    for i, mname in enumerate(menu):
        y = 96 + i * 52
        if mname == "Dữ liệu":
            d.rectangle([0, y - 12, 200, y + 30], fill=(255, 240, 235))
            d.rectangle([0, y - 12, 4, y + 30], fill=ORANGE)
            d.text((28, y), mname, font=f_uni, fill=ORANGE)
        else:
            d.text((28, y), mname, font=f_uni, fill=(70, 70, 70))

    X0 = 224
    # title
    d.text((X0, 82), mp["shop_name"], font=f_title, fill=DARK)
    tw, _ = text_size(d, mp["shop_name"], f_title)
    d.rounded_rectangle([X0 + tw + 16, 90, X0 + tw + 130, 118], radius=6, fill=(255, 236, 230))
    d.text((X0 + tw + 26, 94), "Yêu thích+", font=f_small, fill=ORANGE)
    d.text((X0, 124), "Phân tích bán hàng • Business Insights", font=f_uni_s, fill=GREY)

    # period selector + data as of
    per = f"Khung thời gian: {mp['period_start']:%d/%m/%Y} – {mp['period_end']:%d/%m/%Y}  ▾"
    d.rounded_rectangle([X0, 156, X0 + 470, 192], radius=4, outline=(200, 200, 200), fill="white")
    d.text((X0 + 12, 165), per, font=f_uni_s, fill=DARK)
    asof = f"Dữ liệu tính đến / Data as of {mp['data_as_of']:%d/%m/%Y} 08:{rng.randint(10, 59):02d} (GMT+7)"
    d.text((X0 + 500, 165), asof, font=f_uni_s, fill=GREY)

    # KPI cards
    cards = [
        ("gross_sales", "Doanh số • Gross sales", _vn(mp["gross_sales"]), True, f"▲ {rng.uniform(1.5, 9.5):.1f}% vs tháng trước"),
        ("orders", "Đơn hàng • Orders", _vn(mp["orders"]), False, f"▲ {rng.uniform(0.5, 7.0):.1f}%"),
        ("payout", "Thanh toán • Total payout", _vn(mp["payout"]), True, "đã chuyển về TK ngân hàng"),
        ("cod_value", "Đơn COD • COD orders value", _vn(mp["cod_value"]), True, f"{round(100 * mp['cod_value'] / mp['gross_sales'])}% doanh số"),
        ("followers", "Người theo dõi • Followers", _vn(mp["followers"]), False, "shop followers"),
        ("rating", "Đánh giá shop • Shop rating", f"{mp['rating']:.1f}", False, "★★★★★ / 5.0"),
    ]
    bboxes = {}
    cw, gap, cy0, ch = 212, 16, 210, 130
    for i, (key, label, val, is_money, sub) in enumerate(cards):
        x = X0 + i * (cw + gap)
        d.rounded_rectangle([x, cy0, x + cw, cy0 + ch], radius=8, fill="white", outline=LINE)
        fl = f_lab
        while text_size(d, label, fl)[0] > cw - 26 and fl.size > 11:
            fl = font("unicode", fl.size - 1)
        d.text((x + 14, cy0 + 14), label, font=fl, fill=GREY)
        vx = x + 14
        vy = cy0 + 50
        bx0, by0, bx1, by1 = None, None, None, None
        if is_money:
            d.text((vx, vy + 4), "₫", font=f_dong, fill=DARK)
            bb = d.textbbox((vx, vy + 4), "₫", font=f_dong)
            bx0, by0 = bb[0], bb[1]
            vx = bb[2] + 2
        fv = f_val
        while text_size(d, val, fv)[0] > cw - (vx - x) - 10 and fv.size > 18:
            fv = font("sans_bold", fv.size - 2)
        d.text((vx, vy), val, font=fv, fill=DARK)
        bb = d.textbbox((vx, vy), val, font=fv)
        bx0 = bb[0] if bx0 is None else min(bx0, bb[0])
        by0 = bb[1] if by0 is None else min(by0, bb[1])
        bx1, by1 = bb[2], max(bb[3], by0 + 10)
        bboxes[key] = norm_bbox(bx0 - 2, by0 - 2, bx1 + 2, by1 + 2, W, H)
        d.text((x + 14, cy0 + 98), sub, font=f_small, fill=(70, 160, 90) if sub.startswith("▲") else GREY)

    # bar chart
    cx0, cy1, cx1, cy2 = X0, 360, 1096, 770
    d.rounded_rectangle([cx0, cy1, cx1, cy2], radius=8, fill="white", outline=LINE)
    d.text((cx0 + 18, cy1 + 14), "Doanh số theo ngày • Daily sales (₫)", font=f_uni, fill=DARK)
    daily = mp["daily"]
    px0, py0, px1, py1 = cx0 + 70, cy1 + 60, cx1 - 24, cy2 - 46
    mx = max(daily)
    step = 500_000
    while mx / step > 6:
        step *= 2
    top = (int(mx / step) + 1) * step
    for k in range(0, int(top / step) + 1):
        yv = py1 - (py1 - py0) * (k * step / top)
        d.line([px0, yv, px1, yv], fill=(238, 238, 238))
        d.text((cx0 + 14, yv - 8), f"{k * step / 1_000_000:.1f}tr", font=f_small, fill=GREY)
    n = len(daily)
    bw = (px1 - px0) / n
    for i, v in enumerate(daily):
        x = px0 + i * bw
        hgt = (py1 - py0) * v / top
        d.rectangle([x + bw * 0.18, py1 - hgt, x + bw * 0.82, py1], fill=ORANGE if i % 7 not in (5, 6) else (250, 150, 120))
        if i % 5 == 0 or i == n - 1:
            d.text((x + bw * 0.2, py1 + 8), f"{i + 1:02d}/{mp['month']:02d}", font=f_small, fill=GREY)

    # payout history table
    tx0, tx1 = 1120, 1576
    d.rounded_rectangle([tx0, cy1, tx1, cy2], radius=8, fill="white", outline=LINE)
    d.text((tx0 + 18, cy1 + 14), "Lịch sử thanh toán • Payout history", font=f_uni, fill=DARK)
    y = cy1 + 60
    d.text((tx0 + 18, y), "Ngày / Date", font=f_small, fill=GREY)
    d.text((tx0 + 250, y), "Số tiền / Amount", font=f_small, fill=GREY)
    y += 26
    for bd, amt in mp["payout_batches"]:
        d.line([tx0 + 18, y - 4, tx1 - 18, y - 4], fill=LINE)
        d.text((tx0 + 18, y), bd.strftime("%d/%m/%Y"), font=f_tab, fill=DARK)
        d.text((tx0 + 250, y), f"₫{_vn(amt)}", font=f_tab, fill=DARK)
        d.text((tx0 + 410, y + 2), "✓", font=f_tab, fill=(70, 160, 90))
        y += 36
    d.line([tx0 + 18, y - 4, tx1 - 18, y - 4], fill=(200, 200, 200))
    d.text((tx0 + 18, y), "Tổng / Total", font=f_tab_b, fill=DARK)
    d.text((tx0 + 250, y), f"₫{_vn(mp['payout'])}", font=f_tab_b, fill=DARK)
    y += 60
    d.text((tx0 + 18, y), f"Lượt truy cập / Visitors: {_vn(mp['visitors'])}", font=f_uni_s, fill=GREY)
    bb = d.textbbox((tx0 + 18, y), f"Lượt truy cập / Visitors: {_vn(mp['visitors'])}", font=f_uni_s)
    bboxes["visitors"] = norm_bbox(bb[0], bb[1], bb[2], bb[3], W, H)
    y += 30
    conv = 100 * mp["orders"] / mp["visitors"]
    d.text((tx0 + 18, y), f"Tỷ lệ chuyển đổi / Conversion: {conv:.2f}%", font=f_uni_s, fill=GREY)
    y += 30
    d.text((tx0 + 18, y), f"Đơn COD / COD orders: {_vn(int(mp['orders'] * mp['cod_value'] / mp['gross_sales']))}", font=f_uni_s, fill=GREY)

    # top products table
    ty0 = 790
    d.rounded_rectangle([X0, ty0, tx1, 952], radius=8, fill="white", outline=LINE)
    d.text((X0 + 18, ty0 + 12), "Sản phẩm bán chạy • Top products", font=f_uni, fill=DARK)
    cols = [X0 + 18, X0 + 520, X0 + 760, X0 + 1000]
    hdr = ["Sản phẩm / Product", "Đã bán / Sold", "Doanh số / Sales", "Tồn kho / Stock"]
    for cx, hname in zip(cols, hdr):
        d.text((cx, ty0 + 46), hname, font=f_small, fill=GREY)
    shares = [0.31, 0.24, 0.17, 0.12]
    prods = PRODUCTS[:4]
    for i, (pname, sh) in enumerate(zip(prods, shares)):
        y = ty0 + 72 + i * 22
        sold = int(mp["orders"] * sh * rng.uniform(0.9, 1.1))
        d.text((cols[0], y), pname, font=f_small, fill=DARK)
        d.text((cols[1], y), str(sold), font=f_small, fill=DARK)
        d.text((cols[2], y), f"₫{_vn(round_to(mp['gross_sales'] * sh, 1000))}", font=f_small, fill=DARK)
        d.text((cols[3], y), str(rng.randint(12, 140)), font=f_small, fill=DARK)

    img = watermark(img, scale=0.9)
    save_png(img, out_png)
    return bboxes


def ground_truth_dashboards(plans_rendered: list[tuple[dict, str, dict]]) -> list[dict]:
    out = []
    for mp, fname, bboxes in plans_rendered:
        traps = ["T01", "T02", "T03", "T10"] if mp["month"] != 6 else ["T02", "T10"]
        if mp["month"] == 3:
            traps.append("T09")
        out.append({
            "filename": fname, "platform": "Shopee", "shop_name": mp["shop_name"],
            "period_start": mp["period_start"].isoformat(), "period_end": mp["period_end"].isoformat(),
            "data_as_of": mp["data_as_of"].isoformat(), "currency": "VND",
            "metrics": {
                "gross_sales": mp["gross_sales"], "orders": mp["orders"], "payout": mp["payout"],
                "cod_value": mp["cod_value"], "followers": mp["followers"], "rating": mp["rating"],
                "visitors": mp["visitors"],
            },
            "payout_batches": [{"date": bd.isoformat(), "amount": a} for bd, a in mp["payout_batches"]],
            "bboxes": bboxes, "trap_ids": traps,
        })
    return out
