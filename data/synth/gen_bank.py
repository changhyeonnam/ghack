"""Bank statement generation: transaction simulation per case + ReportLab rendering with bboxes.

Transactions are plain dicts:
  {date, description, counterparty, debit, credit, trap_ids, ref, mode}
`mode` is None, "freeze" (credit shown but balance does not move - T11) or ("drop", amount)
(balance falls by an extra amount with no row - T12).
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from profiles import (
    EN_MONTHS,
    WATERMARK,
    days_in_month,
    fmt_amount,
    fmt_date_local,
    font_path,
    iso,
    norm_bbox,
    round_to,
)

# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _tx(d: date, desc: str, debit=0, credit=0, counterparty=None, traps=None, mode=None, order=5):
    return {
        "date": d,
        "description": desc,
        "counterparty": counterparty,
        "debit": debit,
        "credit": credit,
        "trap_ids": list(traps or []),
        "mode": mode,
        "order": order,  # intra-day ordering hint
    }


def _ref(rng: random.Random, d: date, prefix: str) -> str:
    return f"{prefix}{d:%y%m%d}{rng.randint(0, 99999):05d}"


def _sorted(txs):
    return sorted(txs, key=lambda t: (t["date"], t["order"], t["description"]))


def assign_balances(txs, opening):
    """Fill `balance_after` honouring the planted modes. Returns (closing, min_balance)."""
    bal = opening
    mn = opening
    for t in txs:
        if t.get("mode") == "freeze":
            t["balance_after"] = bal  # credit shown, balance does not move (T11)
        elif isinstance(t.get("mode"), tuple) and t["mode"][0] == "drop":
            bal = bal + t["credit"] - t["debit"] - t["mode"][1]
            t["balance_after"] = bal
        else:
            bal = bal + t["credit"] - t["debit"]
            t["balance_after"] = bal
        mn = min(mn, bal)
    return bal, mn


def _pick_days(rng: random.Random, days, k, weekdays_only=False, lo=1, hi=31):
    pool = [d for d in days if lo <= d.day <= hi and (not weekdays_only or d.weekday() < 5)]
    k = min(k, len(pool))
    return sorted(rng.sample(pool, k))


def _split(rng: random.Random, total: int, k: int, step: int, jitter=0.35):
    """Split `total` into k positive parts that are multiples of `step` (last absorbs remainder)."""
    weights = [rng.uniform(1 - jitter, 1 + jitter) for _ in range(k)]
    s = sum(weights)
    parts = [round_to(total * w / s, step) for w in weights[:-1]]
    parts.append(total - sum(parts))
    return parts


# --------------------------------------------------------------------------------------
# Case A - Warung Ibu Sari (IDR) - clean
# --------------------------------------------------------------------------------------
A_SUPPLIERS = ["TOKO GROSIR MAKMUR", "GROSIR SEMBAKO BAROKAH", "CV SUMBER REJEKI"]
A_CUSTOMERS = ["BUDI SANTOSO", "RINA WULANDARI", "AGUS PRASETYO", "DEWI LESTARI", "HENDRA KUSUMA", "SITI AMINAH"]


def build_case_a(rng: random.Random, matched_receipts):
    """matched_receipts: list of dicts {date, merchant, total} that are paid by bank transfer."""
    txs = []
    for mi, month in enumerate(range(1, 7)):
        growth = 1 + 0.035 * mi
        days = list(days_in_month(2026, month))
        inflow = 0
        # QRIS settlements (acquirer settles the previous day's QR sales)
        for d in _pick_days(rng, days, 14):
            amt = round_to(rng.uniform(850_000, 1_750_000) * growth, 1000)
            inflow += amt
            txs.append(_tx(d, f"QRIS SETTLEMENT MID 9360{rng.randint(1000, 9999)} - PENJUALAN", credit=amt,
                           counterparty="QRIS ACQUIRER", order=1))
        # weekly cash deposits at the branch
        for d in [d for d in days if d.weekday() == 0]:
            amt = round_to(rng.uniform(2_100_000, 3_400_000) * growth, 50_000)
            inflow += amt
            txs.append(_tx(d, "SETOR TUNAI - CABANG KEBAYORAN LAMA", credit=amt, counterparty=None, order=2))
        # occasional customer transfers (catering / bulk orders)
        for d in _pick_days(rng, days, rng.randint(1, 2)):
            amt = round_to(rng.uniform(400_000, 1_200_000), 5000)
            cust = rng.choice(A_CUSTOMERS)
            inflow += amt
            txs.append(_tx(d, f"TRF DARI {cust} - PESANAN SEMBAKO", credit=amt, counterparty=cust, order=3))

        fixed = 0
        # rent (clearly labelled) on the 1st
        txs.append(_tx(date(2026, month, 1), f"SEWA KIOS BULAN {month:02d}/2026 - H. MAHMUD", debit=2_500_000,
                       counterparty="H. MAHMUD (PEMILIK KIOS)", order=0))
        fixed += 2_500_000
        # utilities (amounts vary month to month)
        pln = round_to(rng.uniform(330_000, 480_000), 1000)
        txs.append(_tx(rng.choice(days[4:11]), "PLN LISTRIK PASCABAYAR - ID PEL 5412xxxx", debit=pln, counterparty="PLN"))
        pdam = round_to(rng.uniform(95_000, 140_000), 500)
        txs.append(_tx(rng.choice(days[8:16]), "PDAM AIR BERSIH - TAGIHAN BULANAN", debit=pdam, counterparty="PDAM"))
        net = round_to(rng.uniform(165_000, 240_000), 1000)
        txs.append(_tx(rng.choice(days[19:26]), "INTERNET WIFI NUSANET - TAGIHAN", debit=net, counterparty="NUSANET"))
        fixed += pln + pdam + net
        # ATM cash withdrawals
        for d in _pick_days(rng, days, rng.randint(1, 2)):
            amt = round_to(rng.uniform(500_000, 1_500_000), 100_000)
            fixed += amt
            txs.append(_tx(d, "TARIK TUNAI ATM - ATM NUSANTARA 0231", debit=amt))
        # monthly admin fee
        txs.append(_tx(days[-1], "BIAYA ADMIN BULANAN", debit=15_000, counterparty=None, order=9))
        fixed += 15_000
        # receipts paid by transfer
        for r in [r for r in matched_receipts if r["date"].month == month]:
            txs.append(_tx(r["date"], f"TRF KE {r['merchant'].upper()} - PEMBELIAN STOK", debit=r["total"],
                           counterparty=r["merchant"].upper(), order=4))
            fixed += r["total"]
        # remaining supplier purchases so that outflow ~ 93-97 % of inflow
        target = int(inflow * rng.uniform(0.93, 0.97)) - fixed
        k = rng.randint(3, 4)
        parts = _split(rng, max(target, 3_000_000), k, 50_000)
        for d, amt in zip(_pick_days(rng, days, k, weekdays_only=True, lo=2), parts):
            sup = rng.choice(A_SUPPLIERS)
            txs.append(_tx(d, f"TRF KE {sup} - PEMBELIAN STOK", debit=amt, counterparty=sup, order=4))
    txs = _sorted(txs)
    opening = 4_350_000
    closing, mn = assign_balances(txs, opening)
    if mn < 300_000:
        opening += round_to(300_000 - mn, 50_000)
        closing, mn = assign_balances(txs, opening)
    for t in txs:
        t["ref"] = _ref(rng, t["date"], "FT")
    return {"opening": opening, "closing": closing, "txs": txs}


# --------------------------------------------------------------------------------------
# Case B - Linh Fashion Online (VND) - traps T01, T03-T07, T11-T14
# --------------------------------------------------------------------------------------
B_CUSTOMERS = ["TRAN THI HOA", "LE MINH TUAN", "PHAM THU TRANG", "VO QUOC BAO", "DANG NGOC ANH", "BUI THI THU",
               "HOANG VAN NAM", "NGO THI KIM"]


def build_case_b(rng: random.Random, months_plan):
    """months_plan: list of dicts for Dec 2025..May 2026:
       {year, month, payout_batches:[(date, amt)], cod_value, gross_sales}
    """
    txs = []
    own_account = {1: 24_000_000, 3: 31_000_000, 5: 27_500_000}  # T04, T05, T06
    own_day = {1: 9, 3: 27, 5: 8}
    own_trap = {1: "T04", 3: "T05", 5: "T06"}
    for mp in months_plan:
        y, m = mp["year"], mp["month"]
        days = list(days_in_month(y, m))
        credits = 0
        # Shopee payouts (T01 - same money as dashboard gross sales)
        for d, amt in mp["payout_batches"]:
            credits += amt
            txs.append(_tx(d, f"CHUYEN TIEN TU SHOPEE PAYOUT - KY {d:%d%m}", credit=amt, counterparty="SHOPEE VIETNAM",
                           traps=["T01"] if m != 12 else [], order=1))
        # COD cash deposits (T03)
        k = rng.randint(3, 5)
        parts = _split(rng, mp["cod_value"], k, 100_000)
        for d, amt in zip(_pick_days(rng, days, k, lo=3), parts):
            credits += amt
            txs.append(_tx(d, "NOP TIEN MAT - PGD TAN BINH", credit=amt, counterparty=None, traps=["T03"], order=2))
        # direct orders paid by transfer
        for d in _pick_days(rng, days, rng.randint(3, 5)):
            cust = rng.choice(B_CUSTOMERS)
            amt = round_to(rng.uniform(900_000, 4_200_000), 10_000)
            credits += amt
            txs.append(_tx(d, f"THANH TOAN DON HANG - {cust}", credit=amt, counterparty=cust, order=3))
        if m == 2:  # T11 - balance does not move
            txs.append(_tx(date(2026, 2, 17), "THANH TOAN DON HANG SI - TRAN THI HOA", credit=18_500_000,
                           counterparty="TRAN THI HOA", traps=["T11"], mode="freeze", order=3))
        if m in own_account and y == 2026:  # T04-T06
            txs.append(_tx(date(y, m, own_day[m]), "CHUYEN TIEN TU NGUYEN THI LINH - VCB", credit=own_account[m],
                           counterparty="NGUYEN THI LINH (VCB)", traps=[own_trap[m]], order=2))
        if m == 3:  # T07 - family round trip
            txs.append(_tx(date(2026, 3, 14), "NHAN TU NGUYEN VAN LONG - CHUYEN KHOAN", credit=50_000_000,
                           counterparty="NGUYEN VAN LONG", traps=["T07"], order=2))
            txs.append(_tx(date(2026, 3, 20), "CHUYEN DEN NGUYEN VAN LONG - HOAN TRA", debit=50_000_000,
                           counterparty="NGUYEN VAN LONG", traps=["T07"], order=2))

        other = 0
        # T13 FE Credit instalment on the 5th
        txs.append(_tx(date(y, m, 5), "CHUYEN DEN FE CREDIT - TRA GOP", debit=3_250_000, counterparty="FE CREDIT",
                       traps=["T13"], order=1))
        other += 3_250_000
        # T14 SPayLater around the 20th
        txs.append(_tx(date(y, m, rng.choice([19, 20, 21])), "SPAYLATER THANH TOAN", debit=1_480_000,
                       counterparty="SPAYLATER", traps=["T14"], order=1))
        other += 1_480_000
        # rent, clearly labelled
        txs.append(_tx(date(y, m, 2), f"TIEN THUE NHA T{m:02d}/{y} - NGUYEN THI MAI", debit=6_500_000,
                       counterparty="NGUYEN THI MAI (CHU NHA)", order=0))
        other += 6_500_000
        # shipping
        ship_days = _pick_days(rng, days, 3, lo=4)
        ship_rows = []
        for i, d in enumerate(ship_days):
            amt = round_to(rng.uniform(800_000, 2_600_000), 1000)
            desc = "THANH TOAN J&T EXPRESS - CUOC VC" if i == 2 else "THANH TOAN GHN EXPRESS - CUOC VC"
            cp = "J&T EXPRESS" if i == 2 else "GHN EXPRESS"
            t = _tx(d, desc, debit=amt, counterparty=cp)
            ship_rows.append(t)
            txs.append(t)
            other += amt
        if m == 4:  # T12 - a deleted debit row: balance jumps down 7,200,000 after this row
            ship_rows[1]["mode"] = ("drop", 7_200_000)
            ship_rows[1]["trap_ids"].append("T12")
        # ads
        for d in _pick_days(rng, days, rng.randint(1, 2)):
            amt = round_to(rng.uniform(1_500_000, 3_500_000), 100_000)
            other += amt
            txs.append(_tx(d, "SHOPEE ADS - NAP TIEN QUANG CAO", debit=amt, counterparty="SHOPEE ADS"))
        # utilities
        evn = round_to(rng.uniform(900_000, 1_600_000), 1000)
        txs.append(_tx(rng.choice(days[6:14]), "TIEN DIEN EVNHCMC - MA KH PE0100xxxx", debit=evn, counterparty="EVNHCMC"))
        water = round_to(rng.uniform(150_000, 300_000), 1000)
        txs.append(_tx(rng.choice(days[9:17]), "TIEN NUOC SAWACO", debit=water, counterparty="SAWACO"))
        mobile = round_to(rng.uniform(200_000, 350_000), 1000)
        txs.append(_tx(rng.choice(days[21:27]), "CUOC DI DONG VINATEL", debit=mobile, counterparty="VINATEL"))
        txs.append(_tx(rng.choice(days[12:19]), "INTERNET CAP QUANG - THANH TOAN", debit=250_000, counterparty="ISP"))
        other += evn + water + mobile + 250_000
        # ATM + small card spend
        for d in _pick_days(rng, days, 2):
            amt = round_to(rng.uniform(2_000_000, 5_000_000), 500_000)
            other += amt
            txs.append(_tx(d, "RUT TIEN ATM - ATM SGMK Q.TAN BINH", debit=amt))
        for d in _pick_days(rng, days, rng.randint(2, 3)):
            amt = round_to(rng.uniform(150_000, 650_000), 1000)
            other += amt
            txs.append(_tx(d, rng.choice(["THANH TOAN QR - SIEU THI COOP", "GRAB - THANH TOAN THE",
                                          "THANH TOAN QR - CUA HANG VPP"]), debit=amt))
        txs.append(_tx(days[-1], "PHI DICH VU SMS BANKING", debit=11_000, order=9))
        other += 11_000
        # stock purchases so that outflow ~ 92-97 % of ordinary inflow
        target = int(credits * rng.uniform(0.92, 0.97)) - other
        k = rng.randint(3, 4)
        parts = _split(rng, max(target, 10_000_000), k, 100_000)
        for i, (d, amt) in enumerate(zip(_pick_days(rng, days, k, weekdays_only=True, lo=3), parts)):
            if i % 2 == 0:
                txs.append(_tx(d, "CHUYEN DEN XUONG MAY MINH ANH - TIEN HANG", debit=amt, counterparty="XUONG MAY MINH ANH", order=4))
            else:
                txs.append(_tx(d, "THANH TOAN NCC VAI - CHO TAN BINH", debit=amt, counterparty="NCC VAI TAN BINH", order=4))
    txs = _sorted(txs)
    opening = 38_000_000
    closing, mn = assign_balances(txs, opening)
    if mn < 2_000_000:
        opening += round_to(2_000_000 - mn, 1_000_000)
        closing, mn = assign_balances(txs, opening)
    for t in txs:
        t["ref"] = _ref(rng, t["date"], "SGMK")
    return {"opening": opening, "closing": closing, "txs": txs}


# --------------------------------------------------------------------------------------
# Case C - Reyes Auto Repair (PHP) - traps T16-T19
# --------------------------------------------------------------------------------------
C_CUSTOMERS = ["ANA SANTOS", "JOSE RAMOS", "MARK VILLANUEVA", "LIZA GARCIA", "RICO BAUTISTA", "CARLA MENDOZA",
               "PAOLO CRUZ", "GRACE TAN"]


def _week_income(ledger_income, monday: date) -> float:
    start = monday - timedelta(days=7)
    end = monday - timedelta(days=1)
    return sum(a for d, a in ledger_income if start <= d <= end)


def build_case_c(rng: random.Random, ledger_income):
    """ledger_income: list of (date, amount) for genuine ledger cash income (all 6 months)."""
    def month_txs(y, m):
        days = list(days_in_month(y, m))
        out = []
        for d in days:
            if d.weekday() == 0:  # Monday cash deposit = previous week's ledger cash (T19)
                amt = _week_income(ledger_income, d)
                if amt > 0:
                    out.append(_tx(d, "CASH DEPOSIT - BRANCH 0045 QUIAPO", credit=amt, traps=["T19"], order=1))
            if d.weekday() == 4:  # Friday informal lender (T18)
                out.append(_tx(d, "GCASH TRANSFER TO JUAN DELA CRUZ", debit=3000.0, counterparty="JUAN DELA CRUZ",
                               traps=["T18"], order=3))
        out.append(_tx(date(y, m, 10), "BDO AUTO LOAN PAYMENT - 4411xxxx", debit=14_800.0, counterparty="BDO AUTO LOAN",
                       traps=["T17"], order=2))
        for d in _pick_days(rng, days, rng.randint(2, 3)):
            cust = rng.choice(C_CUSTOMERS)
            out.append(_tx(d, f"GCASH TRANSFER FROM {cust}", credit=float(round_to(rng.uniform(1200, 5500), 50)),
                           counterparty=cust, order=2))
        d = rng.choice(days)
        cust = rng.choice(C_CUSTOMERS)
        out.append(_tx(d, f"INSTAPAY FROM {cust} - CAR REPAIR", credit=float(round_to(rng.uniform(2500, 7500), 50)),
                       counterparty=cust, order=2))
        for d in _pick_days(rng, days, rng.randint(2, 3), weekdays_only=True):
            out.append(_tx(d, "DEBIT CARD PURCHASE - AUTOPARTS PLUS BANAWE", debit=float(round_to(rng.uniform(1800, 9500), 10)),
                           counterparty="AUTOPARTS PLUS", order=4))
        d = rng.choice(days[10:25])
        out.append(_tx(d, "FUND TRANSFER TO LUBRICANTS TRADING CORP", debit=float(round_to(rng.uniform(3000, 7000), 50)),
                       counterparty="LUBRICANTS TRADING CORP", order=4))
        out.append(_tx(rng.choice(days[12:20]), "MERALCO BILL PAYMENT", debit=round(rng.uniform(2100, 3600), 2), counterparty="MERALCO"))
        out.append(_tx(rng.choice(days[14:22]), "MAYNILAD BILL PAYMENT", debit=round(rng.uniform(380, 720), 2), counterparty="MAYNILAD"))
        out.append(_tx(rng.choice(days[3:9]), "SMARTLINK POSTPAID PLAN", debit=999.0, counterparty="SMARTLINK"))
        for d in _pick_days(rng, days, rng.randint(2, 3)):
            out.append(_tx(d, "ATM WITHDRAWAL - MPSB ATM QUIAPO", debit=float(round_to(rng.uniform(2000, 8000), 500))))
        out.append(_tx(rng.choice(days[15:28]), "INSTAPAY TO MARIA REYES", debit=float(round_to(rng.uniform(2000, 4000), 500)),
                       counterparty="MARIA REYES"))
        interest = round(rng.uniform(2.1, 4.9), 2)
        out.append(_tx(days[-1], "INTEREST CREDIT", credit=interest, order=8))
        out.append(_tx(days[-1], "WITHHOLDING TAX ON INTEREST", debit=round(interest * 0.2, 2), order=9))
        return out

    sections = []
    # Jan + Feb chained; Feb closing must equal 48,950.00 exactly
    jan = _sorted(month_txs(2026, 1))
    feb = _sorted(month_txs(2026, 2))
    both = jan + feb
    net = sum(t["credit"] - t["debit"] for t in both)
    opening = round(48_950.00 - net, 2)
    closing, mn = assign_balances(both, opening)
    if mn < 500:
        extra = round_to(500 - mn + 499, 500)
        opening = round(opening + extra, 2)
        feb.append(_tx(date(2026, 2, 26), "ATM WITHDRAWAL - MPSB ATM QUIAPO", debit=float(extra)))
        feb = _sorted(feb)
        both = jan + feb
        closing, mn = assign_balances(both, opening)
    assert abs(closing - 48_950.00) < 0.005, closing
    jan_close = jan[-1]["balance_after"]
    sections.append({"year": 2026, "month": 1, "opening": opening, "closing": jan_close, "txs": jan})
    sections.append({"year": 2026, "month": 2, "opening": jan_close, "closing": 48_950.00, "txs": feb})
    # May + Jun: opening 61,400.00 (does not chain from February - T16)
    may = _sorted(month_txs(2026, 5))
    jun = _sorted(month_txs(2026, 6))
    later = may + jun
    closing2, mn2 = assign_balances(later, 61_400.00)
    assert mn2 > 0, mn2
    may_close = may[-1]["balance_after"]
    sections.append({"year": 2026, "month": 5, "opening": 61_400.00, "closing": may_close, "txs": may})
    sections.append({"year": 2026, "month": 6, "opening": may_close, "closing": closing2, "txs": jun})
    may[0]["trap_ids"].append("T16")
    for s in sections:
        for t in s["txs"]:
            t["balance_after"] = round(t["balance_after"], 2)
            t["ref"] = _ref(rng, t["date"], "MP")
        s["closing"] = round(s["closing"], 2)
        s["opening"] = round(s["opening"], 2)
    return {"opening": opening, "closing": round(closing2, 2), "sections": sections}


# --------------------------------------------------------------------------------------
# Rendering (ReportLab) with bbox capture
# --------------------------------------------------------------------------------------
LABELS = {
    "id": {
        "title": "LAPORAN MUTASI REKENING",
        "subtitle": "Rekening Tabungan Usaha • Ekspor dari aplikasi mobile banking",
        "cols": ["Tanggal", "No. Ref", "Keterangan", "Debit", "Kredit", "Saldo"],
        "opening": "SALDO AWAL",
        "closing": "SALDO AKHIR",
        "holder": "Nama Pemilik",
        "acct": "No. Rekening",
        "period": "Periode",
        "currency": "Mata Uang",
        "branch": "Kantor Cabang",
        "branch_v": "KCP Kebayoran Lama, Jakarta Selatan",
        "generated": "Dicetak",
        "page": "Halaman {p} dari {n}",
        "footer": "Dokumen ini dibuat secara elektronik dan sah tanpa tanda tangan.",
        "cont": "(lanjutan)",
    },
    "vi": {
        "title": "SAO KÊ TÀI KHOẢN / ACCOUNT STATEMENT",
        "subtitle": "Tài khoản thanh toán • Xuất từ ứng dụng ngân hàng số",
        "cols": ["Ngày GD", "Số tham chiếu", "Diễn giải", "Ghi nợ", "Ghi có", "Số dư"],
        "opening": "SỐ DƯ ĐẦU KỲ",
        "closing": "SỐ DƯ CUỐI KỲ",
        "holder": "Chủ tài khoản",
        "acct": "Số tài khoản",
        "period": "Kỳ sao kê",
        "currency": "Loại tiền",
        "branch": "Chi nhánh",
        "branch_v": "PGD Tân Bình, TP. Hồ Chí Minh",
        "generated": "Ngày xuất",
        "page": "Trang {p} / {n}",
        "footer": "Sao kê điện tử, không cần chữ ký. / Electronic statement, no signature required.",
        "cont": "(tiếp theo)",
    },
    "en": {
        "title": "STATEMENT OF ACCOUNT",
        "subtitle": "Business Savings Account • Exported from mobile banking",
        "cols": ["Date", "Reference", "Description", "Debit", "Credit", "Balance"],
        "opening": "BALANCE FORWARD",
        "closing": "ENDING BALANCE",
        "holder": "Account Name",
        "acct": "Account No.",
        "period": "Statement Period",
        "currency": "Currency",
        "branch": "Branch",
        "branch_v": "Quiapo Branch, Manila",
        "generated": "Generated",
        "page": "Page {p} of {n}",
        "footer": "This is a system-generated statement. Date format MM/DD/YYYY.",
        "cont": "(continued)",
    },
}

PAGE_W, PAGE_H = A4
MARGIN = 36
ROW_H = 15.5
ROWS_FIRST = 32
ROWS_NEXT = 42
COL_W = [52, 70, 193, 68, 68, 72]  # sums to 523 = PAGE_W - 2*MARGIN


def _register_fonts():
    if "ArialUni" in pdfmetrics.getRegisteredFontNames():
        return
    p = font_path("unicode")
    if p:
        pdfmetrics.registerFont(TTFont("ArialUni", p))
    else:  # pragma: no cover
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        pdfmetrics.registerFont(TTFont("ArialUni", font_path("sans")))


def render_statement(out_pdf: Path, case: dict, sections: list[dict], lang: str, generated_on: date,
                     section_titles: bool, period_start: date, period_end: date) -> dict:
    """Draw the statement. Returns {"pages": n, "rows": [...], "sections": [...]} with bboxes."""
    _register_fonts()
    L = LABELS[lang]
    cur = case["currency"]
    country = case["country"]
    FONT = "ArialUni"

    # ---- build the line list ----
    lines = []
    for si, s in enumerate(sections):
        if si > 0 and section_titles:
            lines.append(("break", None))
        if section_titles:
            lines.append(("title", f"{EN_MONTHS[s['month']].upper()} {s['year']}"))
        lines.append(("open", si))
        for t in s["txs"]:
            lines.append(("tx", t))
        lines.append(("close", si))

    # ---- paginate ----
    pages: list[list] = [[]]
    cap = ROWS_FIRST
    used = 0
    for kind, payload in lines:
        units = 2 if kind == "title" else 1
        if kind == "break" or used + units > cap:
            pages.append([])
            cap = ROWS_NEXT
            used = 0
            if kind == "break":
                continue
        pages[-1].append((kind, payload))
        used += units
    n_pages = len(pages)

    c = rl_canvas.Canvas(str(out_pdf), pagesize=A4, invariant=1)
    c.setTitle(f"{case['bank_name']} - statement - {case['account_holder']}")
    c.setAuthor(case["bank_name"])
    c.setSubject("SYNTHETIC DEMO DATA")

    result = {"pages": n_pages, "rows": [], "sections": [{} for _ in sections]}
    x_cols = [MARGIN]
    for w in COL_W[:-1]:
        x_cols.append(x_cols[-1] + w)

    def draw_watermark():
        c.saveState()
        c.setFillGray(0.86)
        c.setFont("Helvetica-Bold", 42)
        c.translate(PAGE_W / 2, PAGE_H / 2)
        c.rotate(35)
        c.drawCentredString(0, -60, WATERMARK)
        c.drawCentredString(0, 160, WATERMARK)
        c.drawCentredString(0, -280, WATERMARK)
        c.restoreState()

    def draw_header(page_idx: int) -> float:
        """Returns the y (ReportLab coords) where the table may start."""
        y = PAGE_H - MARGIN
        # bank logo block
        c.setFillColorRGB(*({"ID": (0.05, 0.38, 0.62), "VN": (0.72, 0.12, 0.18), "PH": (0.0, 0.45, 0.35)}[country]))
        c.rect(MARGIN, y - 22, 22, 22, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(MARGIN + 11, y - 16, case["bank_short"][0])
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(MARGIN + 28, y - 16, case["bank_name"])
        c.setFont(FONT, 8)
        c.setFillGray(0.35)
        c.drawRightString(PAGE_W - MARGIN, y - 10, L["page"].format(p=page_idx + 1, n=n_pages))
        c.drawRightString(PAGE_W - MARGIN, y - 20, f"{L['generated']}: {fmt_date_local(generated_on, country)} 09:14")
        y -= 30
        c.setStrokeGray(0.6)
        c.line(MARGIN, y, PAGE_W - MARGIN, y)
        if page_idx == 0:
            y -= 18
            c.setFillGray(0.1)
            c.setFont(FONT, 12)
            c.drawString(MARGIN, y, L["title"])
            c.setFont(FONT, 8)
            c.setFillGray(0.4)
            c.drawString(MARGIN, y - 11, L["subtitle"])
            y -= 30
            # info grid
            info_left = [
                (L["holder"], case["account_holder"]),
                (L["acct"], case["account_masked"]),
                (L["branch"], L["branch_v"]),
                (L["currency"], cur),
            ]
            info_right = [
                (L["period"], f"{fmt_date_local(period_start, country)} - {fmt_date_local(period_end, country)}"),
                (L["opening"], f"{cur} {fmt_amount(sections[0]['opening'], cur)}"),
                (L["closing"], f"{cur} {fmt_amount(sections[-1]['closing'], cur)}"),
                ("Statement ID", f"ST-{period_end:%Y%m}-{sum(ord(ch) * (i + 1) for i, ch in enumerate(case['account_holder'])) % 100000:05d}"),
            ]
            c.setFillGray(0.95)
            c.rect(MARGIN, y - 52, PAGE_W - 2 * MARGIN, 60, stroke=0, fill=1)
            yy = y - 4
            for (k, v), (k2, v2) in zip(info_left, info_right):
                c.setFillGray(0.4)
                c.setFont(FONT, 7.5)
                c.drawString(MARGIN + 8, yy, k)
                c.drawString(MARGIN + 270, yy, k2)
                c.setFillGray(0.05)
                c.setFont("Helvetica-Bold", 8)
                c.drawString(MARGIN + 95, yy, v)
                c.drawString(MARGIN + 365, yy, v2)
                yy -= 13
            y -= 66
        else:
            y -= 14
            c.setFillGray(0.25)
            c.setFont(FONT, 9)
            c.drawString(MARGIN, y, f"{L['title']} {L['cont']}")
            c.setFont(FONT, 7.5)
            c.drawString(MARGIN + 250, y, f"{case['account_holder']}  •  {case['account_masked']}  •  {cur}")
            y -= 12
        # column header
        y -= 6
        c.setFillGray(0.20)
        c.rect(MARGIN, y - ROW_H, PAGE_W - 2 * MARGIN, ROW_H, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(FONT, 7.5)
        base = y - ROW_H + 4.5
        c.drawString(x_cols[0] + 3, base, L["cols"][0])
        c.drawString(x_cols[1] + 3, base, L["cols"][1])
        c.drawString(x_cols[2] + 3, base, L["cols"][2])
        c.drawRightString(x_cols[3] + COL_W[3] - 3, base, L["cols"][3])
        c.drawRightString(x_cols[4] + COL_W[4] - 3, base, L["cols"][4])
        c.drawRightString(x_cols[5] + COL_W[5] - 3, base, L["cols"][5])
        return y - ROW_H

    def draw_footer():
        c.setFont(FONT, 6.5)
        c.setFillGray(0.45)
        c.drawString(MARGIN, MARGIN - 8, L["footer"])
        c.drawRightString(PAGE_W - MARGIN, MARGIN - 8, WATERMARK)
        c.setStrokeGray(0.7)
        c.line(MARGIN, MARGIN + 2, PAGE_W - MARGIN, MARGIN + 2)

    def row_bbox(y_top):
        return norm_bbox(MARGIN, PAGE_H - y_top, PAGE_W - MARGIN, PAGE_H - (y_top - ROW_H), PAGE_W, PAGE_H)

    for pi, page in enumerate(pages):
        draw_watermark()
        y = draw_header(pi)
        shade = False
        for kind, payload in page:
            if kind == "title":
                y -= ROW_H * 0.6
                c.setFillGray(0.15)
                c.setFont("Helvetica-Bold", 9)
                c.drawString(MARGIN, y - ROW_H + 4, payload)
                c.setStrokeGray(0.5)
                c.line(MARGIN, y - ROW_H, PAGE_W - MARGIN, y - ROW_H)
                y -= ROW_H * 1.4
                continue
            base = y - ROW_H + 4.5
            if kind in ("open", "close"):
                s = sections[payload]
                c.setFillGray(0.90)
                c.rect(MARGIN, y - ROW_H, PAGE_W - 2 * MARGIN, ROW_H, stroke=0, fill=1)
                c.setFillGray(0.05)
                c.setFont("Helvetica-Bold", 7.5)
                label = L["opening"] if kind == "open" else L["closing"]
                d = date(s["year"], s["month"], 1) if kind == "open" else None
                if not section_titles:
                    d = period_start if kind == "open" else period_end
                else:
                    d = d if kind == "open" else list(days_in_month(s["year"], s["month"]))[-1]
                c.drawString(x_cols[0] + 3, base, fmt_date_local(d, country))
                c.drawString(x_cols[2] + 3, base, label)
                c.setFont("Courier-Bold", 7.5)
                val = s["opening"] if kind == "open" else s["closing"]
                c.drawRightString(x_cols[5] + COL_W[5] - 3, base, fmt_amount(val, cur))
                key = "opening" if kind == "open" else "closing"
                result["sections"][payload][f"{key}_bbox"] = row_bbox(y)
                result["sections"][payload][f"{key}_page"] = pi + 1
                y -= ROW_H
                continue
            t = payload
            if shade:
                c.setFillGray(0.965)
                c.rect(MARGIN, y - ROW_H, PAGE_W - 2 * MARGIN, ROW_H, stroke=0, fill=1)
            shade = not shade
            c.setFillGray(0.08)
            c.setFont(FONT, 7.2)
            c.drawString(x_cols[0] + 3, base, fmt_date_local(t["date"], country))
            c.setFillGray(0.4)
            c.setFont("Courier", 6.6)
            c.drawString(x_cols[1] + 3, base, t["ref"])
            c.setFillGray(0.08)
            c.setFont(FONT, 7.2)
            desc = t["description"]
            maxw = COL_W[2] - 6
            while pdfmetrics.stringWidth(desc, FONT, 7.2) > maxw and len(desc) > 4:
                desc = desc[:-2]
            c.drawString(x_cols[2] + 3, base, desc)
            c.setFont("Courier", 7.2)
            if t["debit"]:
                c.drawRightString(x_cols[3] + COL_W[3] - 3, base, fmt_amount(t["debit"], cur))
            if t["credit"]:
                c.drawRightString(x_cols[4] + COL_W[4] - 3, base, fmt_amount(t["credit"], cur))
            c.setFont("Courier-Bold", 7.2)
            c.drawRightString(x_cols[5] + COL_W[5] - 3, base, fmt_amount(t["balance_after"], cur))
            result["rows"].append({"page": pi + 1, "bbox": row_bbox(y), "tx": t})
            y -= ROW_H
        draw_footer()
        c.showPage()
    c.save()
    return result


def ground_truth_bank(case: dict, sections: list[dict], render: dict, period_start: date, period_end: date,
                      notes: dict | None = None) -> dict:
    rows = render["rows"]
    txs = []
    i = 0
    for r in rows:
        i += 1
        t = r["tx"]
        txs.append({
            "row_id": f"T{i:04d}",
            "date": iso(t["date"]),
            "description": t["description"],
            "counterparty": t["counterparty"],
            "debit": t["debit"],
            "credit": t["credit"],
            "balance_after": t["balance_after"],
            "page": r["page"],
            "bbox": r["bbox"],
            "ref": t["ref"],
            "trap_ids": t["trap_ids"],
        })
    gt = {
        "account_holder": case["account_holder"],
        "bank_name": case["bank_name"],
        "account_masked": case["account_masked"],
        "currency": case["currency"],
        "period_start": iso(period_start),
        "period_end": iso(period_end),
        "opening_balance": sections[0]["opening"],
        "closing_balance": sections[-1]["closing"],
        "opening_balance_bbox": render["sections"][0].get("opening_bbox"),
        "opening_balance_page": render["sections"][0].get("opening_page"),
        "closing_balance_bbox": render["sections"][-1].get("closing_bbox"),
        "closing_balance_page": render["sections"][-1].get("closing_page"),
        "pages": render["pages"],
        "months_covered": sorted({tx["date"][:7] for tx in txs}),
        "sections": [
            {
                "label": f"{s['year']}-{s['month']:02d}",
                "opening_balance": s["opening"],
                "closing_balance": s["closing"],
                "opening_bbox": render["sections"][si].get("opening_bbox"),
                "opening_page": render["sections"][si].get("opening_page"),
                "closing_bbox": render["sections"][si].get("closing_bbox"),
                "closing_page": render["sections"][si].get("closing_page"),
            }
            for si, s in enumerate(sections)
        ],
        "balance_breaks": [],
        "transactions": txs,
    }
    # describe the planted continuity breaks explicitly
    prev = sections[0]["opening"]
    for tx in txs:
        expected = round(prev + tx["credit"] - tx["debit"], 2)
        if abs(expected - tx["balance_after"]) > 0.005:
            gt["balance_breaks"].append({
                "row_id": tx["row_id"], "date": tx["date"], "expected_balance": expected,
                "shown_balance": tx["balance_after"], "difference": round(tx["balance_after"] - expected, 2),
                "trap_ids": tx["trap_ids"],
            })
        prev = tx["balance_after"]
    if notes:
        gt.update(notes)
    return gt
