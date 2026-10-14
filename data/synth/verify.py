#!/usr/bin/env python
"""Verify the generated synthetic dataset against SPEC.md / traps.json.

    python verify.py [--cases cases]

Prints a table of checks and exits non-zero if any check fails.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import imagehash
import pymupdf
from PIL import Image

from profiles import SYNTH_DIR, WATERMARK, fmt_amount, sha256_file

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    RESULTS.append((bool(ok), name, detail))
    return bool(ok)


def load(p: Path):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def bbox_ok(b) -> bool:
    return (isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)
            and 0 <= b[0] < b[2] <= 1000 and 0 <= b[1] < b[3] <= 1000)


def month_of(s: str) -> str:
    return s[:7]


# --------------------------------------------------------------------------------------
def verify_structure(cases_dir: Path, traps: dict):
    trap_ids = {t["id"] for t in traps["traps"]}
    check(len(trap_ids) == 20, "traps.json has 20 trap ids", ", ".join(sorted(trap_ids)))
    expected_counts = {"A": 18, "B": 14, "C": 11}
    for cid in "ABC":
        mdir = cases_dir / cid
        m = load(mdir / "manifest.json")
        files = {d["filename"] for d in m["documents"]}
        on_disk = {p.name for p in (mdir / "docs").iterdir() if p.is_file()}
        check(files == on_disk, f"{cid}: manifest files == files on disk ({len(files)})",
              f"missing={sorted(files - on_disk)} extra={sorted(on_disk - files)}")
        check(len(files) == expected_counts[cid], f"{cid}: document count {len(files)} == {expected_counts[cid]}")
        for d in m["documents"]:
            if d["filename"].endswith(".pdf"):
                with pymupdf.open(mdir / "docs" / d["filename"]) as doc:
                    check(doc.page_count == d["pages"], f"{cid}: {d['filename']} pages == manifest ({d['pages']})")
            if d["ground_truth"]:
                check((mdir / d["ground_truth"]).exists(), f"{cid}: ground truth exists {d['ground_truth']}")
        case_traps = sorted(t["id"] for t in traps["traps"] if t["case_id"] == cid)
        check(sorted(m["traps"]) == case_traps, f"{cid}: manifest.traps == traps.json case assignment", ",".join(m["traps"]))
        # every trap id referenced anywhere in ground truth exists
        referenced = set()
        for gtf in (mdir / "ground_truth").glob("*.json"):
            def walk(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k == "trap_ids":
                            referenced.update(v)
                        else:
                            walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
            walk(load(gtf))
        check(referenced <= trap_ids, f"{cid}: all referenced trap_ids exist in traps.json", ",".join(sorted(referenced)))
        check(referenced <= set(case_traps), f"{cid}: referenced trap_ids belong to this case", ",".join(sorted(referenced - set(case_traps))))
        for t in traps["traps"]:
            if t["case_id"] != cid:
                continue
            for fn in t["planted_in"]:
                check(fn in files, f"{cid}: {t['id']} planted_in file exists: {fn}")


# --------------------------------------------------------------------------------------
def verify_bank_common(cid: str, gt: dict, pdf: Path, allowed_break_traps: set[str], expected_breaks: int):
    txs = gt["transactions"]
    prev = gt["opening_balance"]
    breaks = []
    for tx in txs:
        expected = round(prev + tx["credit"] - tx["debit"], 2)
        if abs(expected - tx["balance_after"]) > 0.005:
            breaks.append(tx)
            check(bool(set(tx["trap_ids"]) & allowed_break_traps),
                  f"{cid}: continuity break at {tx['row_id']} {tx['date']} is a planted trap", ",".join(tx["trap_ids"]))
        prev = tx["balance_after"]
    check(len(breaks) == expected_breaks, f"{cid}: exactly {expected_breaks} balance break(s) (found {len(breaks)})")
    check(abs(prev - gt["closing_balance"]) < 0.005, f"{cid}: last balance == closing_balance")
    check(len(gt["balance_breaks"]) == expected_breaks, f"{cid}: ground truth balance_breaks list has {expected_breaks}")
    # bboxes + text extraction
    check(all(bbox_ok(tx["bbox"]) for tx in txs), f"{cid}: all {len(txs)} row bboxes within 0-1000")
    check(bbox_ok(gt["opening_balance_bbox"]) and bbox_ok(gt["closing_balance_bbox"]), f"{cid}: opening/closing bboxes present")
    with pymupdf.open(pdf) as doc:
        for pno in range(doc.page_count):
            text = doc[pno].get_text()
            check(len(text) > 200, f"{cid}: page {pno + 1} text extractable ({len(text)} chars)")
            check(WATERMARK in text, f"{cid}: page {pno + 1} carries watermark")
            pix = doc[pno].get_pixmap(dpi=36)
            check(pix.width > 0 and pix.height > 0, f"{cid}: page {pno + 1} renders")
        hits = 0
        for tx in txs:
            page = doc[tx["page"] - 1]
            h = page.rect.height
            target = fmt_amount(tx["balance_after"], gt["currency"])
            rects = page.search_for(target)
            y0, _, y1, _ = tx["bbox"]
            if any(y0 - 3 <= 1000 * (r.y0 + r.y1) / 2 / h <= y1 + 3 for r in rects):
                hits += 1
        check(hits == len(txs), f"{cid}: balance text found inside bbox for every row ({hits}/{len(txs)})")
        # row count per page within 25-42 for full pages
        per_page = defaultdict(int)
        for tx in txs:
            per_page[tx["page"]] += 1
        full = [n for p, n in sorted(per_page.items())[:-1]]
        check(all(25 <= n <= 42 for n in full), f"{cid}: rows per full page in 25-42", str(dict(per_page)))


def verify_case_a(cases_dir: Path):
    cid = "A"
    gt = load(cases_dir / cid / "ground_truth/bank_statement.json")
    verify_bank_common(cid, gt, cases_dir / cid / "docs/bank_statement_2026H1.pdf", set(), 0)
    txs = gt["transactions"]
    check(all(not tx["trap_ids"] for tx in txs), f"{cid}: no trap_ids on any row")
    holder = gt["account_holder"]
    check(not any(holder in tx["description"] for tx in txs), f"{cid}: no self-transfers (holder name absent from descriptions)")
    inflow = defaultdict(int)
    for tx in txs:
        inflow[month_of(tx["date"])] += tx["credit"]
    months = sorted(inflow)
    check(months == [f"2026-{m:02d}" for m in range(1, 7)], f"{cid}: statement covers Jan-Jun 2026")
    check(all(26_000_000 <= inflow[m] <= 40_000_000 for m in months), f"{cid}: monthly inflow 26-40M IDR",
          " ".join(f"{m}:{inflow[m] / 1e6:.1f}M" for m in months))
    check(inflow[months[-1]] > inflow[months[0]], f"{cid}: inflow growing (Jun > Jan)")
    # recurring same-amount debits other than rent / bank fee
    rec = defaultdict(set)
    for tx in txs:
        if tx["debit"]:
            rec[(tx["description"].split(" - ")[0].rsplit(" BULAN", 1)[0], tx["debit"])].add(month_of(tx["date"]))
    suspicious = [k for k, v in rec.items() if len(v) >= 4 and not (k[0].startswith("SEWA KIOS") or k[0].startswith("BIAYA ADMIN"))]
    check(not suspicious, f"{cid}: no loan-like recurring equal debits (rent/admin fee only)", str(suspicious))
    recs = load(cases_dir / cid / "ground_truth/receipts.json")
    check(len(recs) == 15 and sum(r["handwritten"] for r in recs) == 3, f"{cid}: 15 receipts, 3 handwritten")
    check(all(300_000 <= r["total"] <= 3_000_000 for r in recs), f"{cid}: receipt totals 300k-3M IDR")
    check(all(abs(sum(i["amount"] for i in r["items"]) - r["total"]) < 1 for r in recs), f"{cid}: receipt items sum to total")
    check(all(not r["trap_ids"] for r in recs), f"{cid}: receipts carry no traps")
    matched = 0
    for r in recs:
        if r.get("paid_by_bank_transfer"):
            matched += any(tx["date"] == r["date"] and tx["debit"] == r["total"] and r["merchant"].upper() in tx["description"] for tx in txs)
    check(matched == sum(1 for r in recs if r.get("paid_by_bank_transfer")) and matched >= 3,
          f"{cid}: transfer-paid receipts have matching TRF KE rows ({matched})")


def verify_case_b(cases_dir: Path):
    cid = "B"
    gt = load(cases_dir / cid / "ground_truth/bank_statement.json")
    verify_bank_common(cid, gt, cases_dir / cid / "docs/bank_statement_2025-12_2026-05.pdf", {"T11", "T12"}, 2)
    txs = gt["transactions"]
    dash = load(cases_dir / cid / "ground_truth/dashboards.json")
    by_month = {d["period_start"][:7]: d for d in dash}
    # T10
    check(sorted(by_month) == [f"2026-{m:02d}" for m in range(1, 7)], "T10: dashboards cover Jan-Jun 2026")
    check(gt["months_covered"] == ["2025-12"] + [f"2026-{m:02d}" for m in range(1, 6)], "T10: statement covers Dec 2025-May 2026")
    check(gt["period_start"] == "2025-12-01" and gt["period_end"] == "2026-05-31", "T10: statement period header Dec-May")
    # T01 / T03
    payouts = defaultdict(int)
    cod = defaultdict(int)
    for tx in txs:
        if "SHOPEE PAYOUT" in tx["description"]:
            payouts[month_of(tx["date"])] += tx["credit"]
        if tx["description"].startswith("NOP TIEN MAT"):
            cod[month_of(tx["date"])] += tx["credit"]
    for m in [f"2026-{k:02d}" for k in range(1, 6)]:
        d = by_month[m]["metrics"]
        check(payouts[m] == d["payout"], f"T01: {m} SHOPEE PAYOUT credits == dashboard payout ({payouts[m]:,})")
        check(0.88 <= d["payout"] / d["gross_sales"] <= 0.92, f"T01: {m} payout/gross in 0.88-0.92 ({d['payout'] / d['gross_sales']:.3f})")
        check(cod[m] == d["cod_value"], f"T03: {m} NOP TIEN MAT deposits == dashboard COD value ({cod[m]:,})")
        n_payouts = sum(1 for tx in txs if "SHOPEE PAYOUT" in tx["description"] and month_of(tx["date"]) == m)
        check(2 <= n_payouts <= 4, f"T01: {m} payout split into 2-4 credits ({n_payouts})")
        check(n_payouts == len(by_month[m]["payout_batches"]), f"T01: {m} dashboard payout table matches bank batches")
    check("2025-12" in payouts and payouts["2025-12"] > 0, "T10: December payouts exist in bank without a dashboard")
    check(all(d["metrics"]["payout"] < d["metrics"]["gross_sales"] for d in dash), "T02: payout < gross sales on every dashboard")
    # T04-T06
    own = sorted((tx["credit"], month_of(tx["date"])) for tx in txs if "NGUYEN THI LINH - VCB" in tx["description"])
    check([a for a, _ in own] == [24_000_000, 27_500_000, 31_000_000], "T04-T06: own-account VCB credits 24M/27.5M/31M", str(own))
    check(len({m for _, m in own}) == 3, "T04-T06: own-account credits in three different months")
    # T07
    t07 = [tx for tx in txs if "NGUYEN VAN LONG" in tx["description"]]
    check(any(tx["date"] == "2026-03-14" and tx["credit"] == 50_000_000 for tx in t07) and
          any(tx["date"] == "2026-03-20" and tx["debit"] == 50_000_000 for tx in t07), "T07: +50M on 03-14 and -50M on 03-20 (NGUYEN VAN LONG)")
    # T11
    idx = {tx["row_id"]: i for i, tx in enumerate(txs)}
    t11 = [tx for tx in txs if "T11" in tx["trap_ids"]]
    ok = len(t11) == 1 and t11[0]["date"] == "2026-02-17" and t11[0]["credit"] == 18_500_000 and \
        t11[0]["description"].startswith("THANH TOAN DON HANG") and t11[0]["balance_after"] == txs[idx[t11[0]["row_id"]] - 1]["balance_after"]
    check(ok, "T11: 2026-02-17 THANH TOAN DON HANG +18,500,000 with unchanged running balance")
    # T12
    t12 = [b for b in gt["balance_breaks"] if "T12" in b["trap_ids"]]
    check(len(t12) == 1 and t12[0]["date"].startswith("2026-04") and t12[0]["difference"] == -7_200_000,
          "T12: April balance drops by 7,200,000 with no debit row")
    # T13 / T14
    fe = {month_of(tx["date"]): tx for tx in txs if "FE CREDIT" in tx["description"]}
    check(len(fe) == 6 and all(tx["debit"] == 3_250_000 and tx["date"].endswith("-05") for tx in fe.values()),
          "T13: FE CREDIT -3,250,000 on the 5th in all 6 months")
    sp = {month_of(tx["date"]): tx for tx in txs if "SPAYLATER" in tx["description"]}
    check(len(sp) == 6 and all(tx["debit"] == 1_480_000 and 19 <= int(tx["date"][-2:]) <= 21 for tx in sp.values()),
          "T14: SPAYLATER -1,480,000 on the 19th-21st in all 6 months")
    # T08
    p2 = cases_dir / cid / "docs/ghn_receipt_02.jpg"
    p5 = cases_dir / cid / "docs/ghn_receipt_05.jpg"
    dist = imagehash.phash(Image.open(p2)) - imagehash.phash(Image.open(p5))
    check(dist <= 4, f"T08: phash distance ghn_receipt_02 vs 05 <= 4 (={dist})")
    check(sha256_file(p2) != sha256_file(p5), "T08: the two receipt files are not byte-identical (date differs)")
    recs = {r["filename"]: r for r in load(cases_dir / cid / "ground_truth/receipts.json")}
    r2, r5 = recs["ghn_receipt_02.jpg"], recs["ghn_receipt_05.jpg"]
    check(r2["receipt_number"] == r5["receipt_number"] == "GHN-2231" and r2["items"] == r5["items"] and
          r2["date"] == "2026-02-11" and r5["date"] == "2026-03-11", "T08: same receipt number/items, dates 02-11 vs 03-11")
    check(len(recs) == 6, "B: 6 logistics receipts")
    # T09
    followers = [by_month[f"2026-{m:02d}"]["metrics"]["followers"] for m in range(1, 7)]
    check(followers == [12_400, 12_900, 9_800, 13_600, 13_900, 14_200], "T09: followers sequence with March dip", str(followers))
    check(by_month["2026-03"]["shop_name"] == "Linh Fashion VN" and
          all(by_month[m]["shop_name"] == "Linh Fashion Official" for m in by_month if m != "2026-03"), "T09: March shop name 'Linh Fashion VN'")
    # dashboard bboxes / sizes
    for d in dash:
        img = Image.open(cases_dir / cid / "docs" / d["filename"])
        check(img.size == (1600, 1000), f"B: {d['filename']} is 1600x1000")
        check(all(bbox_ok(b) for b in d["bboxes"].values()) and
              {"gross_sales", "orders", "payout", "cod_value", "followers", "rating"} <= set(d["bboxes"]),
              f"B: {d['filename']} KPI bboxes present and valid")


def verify_case_c(cases_dir: Path, past_dir: Path):
    cid = "C"
    gt = load(cases_dir / cid / "ground_truth/bank_statement.json")
    verify_bank_common(cid, gt, cases_dir / cid / "docs/bank_statement_2026_partial.pdf", {"T16"}, 1)
    txs = gt["transactions"]
    secs = {s["label"]: s for s in gt["sections"]}
    # T16
    check(gt["months_covered"] == ["2026-01", "2026-02", "2026-05", "2026-06"], "T16: only Jan, Feb, May, Jun present")
    check(gt["period_start"] == "2026-01-01" and gt["period_end"] == "2026-06-30", "T16: header period says Jan-Jun 2026")
    check(secs["2026-02"]["closing_balance"] == 48_950.00 and secs["2026-05"]["opening_balance"] == 61_400.00,
          "T16: Feb closing 48,950.00 vs May opening 61,400.00")
    check(secs["2026-01"]["closing_balance"] == secs["2026-02"]["opening_balance"] and
          secs["2026-05"]["closing_balance"] == secs["2026-06"]["opening_balance"], "T16: other month boundaries chain")
    # T17
    bdo = {month_of(tx["date"]): tx for tx in txs if "BDO AUTO LOAN" in tx["description"]}
    check(sorted(bdo) == gt["months_covered"] and all(tx["debit"] == 14_800 and tx["date"].endswith("-10") for tx in bdo.values()),
          "T17: BDO AUTO LOAN PAYMENT -14,800 on the 10th in all 4 months")
    # T18
    fridays = [date(2026, m, d) for m in (1, 2, 5, 6) for d in range(1, 32)
               if d <= (date(2026, m % 12 + 1, 1) - timedelta(days=1)).day and date(2026, m, d).weekday() == 4]
    gc = {tx["date"] for tx in txs if "GCASH TRANSFER TO JUAN DELA CRUZ" in tx["description"] and tx["debit"] == 3000}
    check(gc == {f.isoformat() for f in fridays}, f"T18: GCASH 3,000 to JUAN DELA CRUZ on every Friday ({len(gc)}/{len(fridays)})")
    # T19
    ledger = load(cases_dir / cid / "ground_truth/ledger.json")
    genuine = [p for p in ledger if not p.get("duplicate_of") and p["month"]]
    income = [(date.fromisoformat(e["date"]), e["amount"]) for p in genuine for e in p["entries"] if e["kind"] == "income"]
    deposits = [tx for tx in txs if tx["description"].startswith("CASH DEPOSIT")]
    ok, n = True, 0
    for tx in deposits:
        d = date.fromisoformat(tx["date"])
        if d.weekday() != 0:
            ok = False
        s = sum(a for dd, a in income if d - timedelta(days=7) <= dd <= d - timedelta(days=1))
        if abs(s - tx["credit"]) > 0.005:
            ok = False
        n += 1
    check(ok and n >= 15, f"T19: every Monday CASH DEPOSIT equals previous week's ledger cash income ({n} deposits)")
    check(all("T19" in tx["trap_ids"] for tx in deposits), "T19: deposits tagged T19")
    # ledger structure
    check([p["filename"] for p in ledger] == [f"ledger_p{i}.jpg" for i in range(1, 9)], "C: 8 ledger pages p1..p8")
    labels = {p["filename"]: p["period_label"] for p in ledger}
    check(labels["ledger_p3.jpg"] == "Marso 2026" and labels["ledger_p6.jpg"] == "Abril 2026", "T15: p3 header Marso, p6 header Abril")
    check({"Enero 2026", "Pebrero 2026", "Marso 2026", "Abril 2026", "Mayo 2026", "Hunyo 2026"} <= set(labels.values()),
          "C: ledger pages for all six Filipino month names (incl. missing bank months Marso/Abril)")
    p3 = next(p for p in ledger if p["filename"] == "ledger_p3.jpg")
    p6 = next(p for p in ledger if p["filename"] == "ledger_p6.jpg")
    same = len(p3["entries"]) == len(p6["entries"]) and all(
        a["description"] == b["description"] and a["amount"] == b["amount"] and a["date"][8:] == b["date"][8:]
        for a, b in zip(p3["entries"], p6["entries"]))
    check(same and p6.get("duplicate_of") == "ledger_p3.jpg" and "T15" in p6["trap_ids"], "T15: p6 entries identical to p3 (dates re-labelled to April)")
    dist = imagehash.phash(Image.open(cases_dir / cid / "docs/ledger_p3.jpg")) - imagehash.phash(Image.open(cases_dir / cid / "docs/ledger_p6.jpg"))
    check(dist <= 4, f"T15: phash distance ledger_p3 vs ledger_p6 <= 4 (={dist})")
    check(sha256_file(cases_dir / cid / "docs/ledger_p3.jpg") != sha256_file(cases_dir / cid / "docs/ledger_p6.jpg"),
          "T15: p3 and p6 files differ (header glyphs)")
    for p in ledger:
        amounts = [e["amount"] for e in p["entries"] if e["kind"] == "income"]
        check(all(1500 <= a <= 6000 for a in amounts), f"C: {p['filename']} daily cash income within 1,500-6,000")
        check(all(bbox_ok(e["bbox"]) for e in p["entries"]), f"C: {p['filename']} entry bboxes valid ({len(p['entries'])})")
        if p["month"]:
            check(18 <= len(p["entries"]) <= 32, f"C: {p['filename']} has 18-32 rows ({len(p['entries'])})")
    # T20
    idx = load(past_dir / "index.json")
    past = past_dir / idx[0]["filename"] if (past_dir / idx[0]["filename"]).exists() else past_dir / idx[0]["case_id"] / idx[0]["filename"]
    p2 = cases_dir / cid / "docs/premises_02.jpg"
    check(idx[0]["case_id"] == "PAST-2025-0471", "T20: past_cases/index.json lists PAST-2025-0471")
    check(sha256_file(p2) == sha256_file(past) == idx[0]["sha256"], "T20: premises_02.jpg byte-identical to past case photo (sha256 matches index)")
    check(str(imagehash.phash(Image.open(past))) == idx[0]["phash"], "T20: index phash matches computed phash")


# --------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="cases")
    args = ap.parse_args(argv)
    cases_dir = (SYNTH_DIR / args.cases).resolve()
    past_dir = SYNTH_DIR / "past_cases"
    traps = load(SYNTH_DIR / "traps.json")

    verify_structure(cases_dir, traps)
    verify_case_a(cases_dir)
    verify_case_b(cases_dir)
    verify_case_c(cases_dir, past_dir)
    total = sum(p.stat().st_size for p in cases_dir.rglob("*") if p.is_file()) + sum(p.stat().st_size for p in past_dir.rglob("*") if p.is_file())
    check(total < 25e6, f"total generated size {total / 1e6:.1f} MB < 25 MB")

    # ---- report ----
    fails = [r for r in RESULTS if not r[0]]
    width = max(len(r[1]) for r in RESULTS)
    print(f"{'STATUS':6}  {'CHECK':{width}}  DETAIL")
    print("-" * (width + 30))
    # collapse the very repetitive per-page / per-file passes to keep the table readable
    shown = 0
    collapsed = defaultdict(int)
    for ok, name, detail in RESULTS:
        key = None
        for pat in ("text extractable", "carries watermark", "renders", "planted_in file exists", "ground truth exists",
                    "KPI bboxes present", "is 1600x1000", "entry bboxes valid", "daily cash income within", "has 18-32 rows"):
            if pat in name and ok:
                key = f"{name.split(':')[0]}: ... {pat} (all)"
        if key:
            collapsed[key] += 1
            continue
        print(f"{'PASS' if ok else 'FAIL':6}  {name:{width}}  {detail}")
        shown += 1
    for key, n in collapsed.items():
        print(f"{'PASS':6}  {key:{width}}  x{n}")
    print("-" * (width + 30))
    print(f"{len(RESULTS) - len(fails)} passed, {len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
