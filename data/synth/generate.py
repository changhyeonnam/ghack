#!/usr/bin/env python
"""Generate the LedgerLens synthetic demo dataset (3 cases, 20 planted traps, ground truth).

Usage:
    python generate.py --seed 7 --out cases

Everything is fictional and deterministic for a given seed. See SPEC.md and README.md.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import imagehash  # noqa: E402
from PIL import Image  # noqa: E402

import random  # noqa: E402

from gen_bank import build_case_a, build_case_b, build_case_c, ground_truth_bank, render_statement  # noqa: E402
from gen_dashboard import ground_truth_dashboards, plan_months, render_dashboard  # noqa: E402
from gen_ledger import build_pages, income_list, plan_ledger, render_pages  # noqa: E402
from gen_premises import premises_garage, premises_stockroom, premises_warung, premises_workshop_interior  # noqa: E402
from gen_receipts import (  # noqa: E402
    ground_truth_logistics,
    ground_truth_receipts_a,
    plan_logistics_b,
    plan_receipts_a,
    render_logistics,
    render_receipt_handwritten,
    render_receipt_printed,
)
from profiles import CASES, SYNTH_DIR, sha256_file, write_json  # noqa: E402

GENERATED_ON = date(2026, 7, 6)


def load_traps() -> dict:
    with open(SYNTH_DIR / "traps.json", encoding="utf-8") as fh:
        return json.load(fh)


def trap_ids_for(traps: dict, case_id: str) -> list[str]:
    return [t["id"] for t in traps["traps"] if t["case_id"] == case_id]


def manifest_for(case: dict, docs: list[dict], traps: dict, seed: int, notes: str) -> dict:
    keys = ["case_id", "name", "business_name", "sector", "country", "city", "language", "currency",
            "requested_amount", "expected_outcome", "account_holder", "bank_name"]
    m = {k: case[k] for k in keys}
    m["notes"] = notes
    m["documents"] = docs
    m["traps"] = trap_ids_for(traps, case["case_id"])
    m["generated_with"] = {"generator": "data/synth/generate.py", "seed": seed, "synthetic": True}
    return m


def pdf_pages(path: Path) -> int:
    import pymupdf

    with pymupdf.open(path) as doc:
        return doc.page_count


# --------------------------------------------------------------------------------------
def gen_case_a(out: Path, seed: int, traps: dict):
    case = CASES["A"]
    rng = random.Random(seed * 100 + 1)
    docs_dir = out / "A" / "docs"
    gt_dir = out / "A" / "ground_truth"
    docs_dir.mkdir(parents=True, exist_ok=True)

    recs = plan_receipts_a(rng)
    matched = [r for r in recs if r["paid_by_transfer"]]
    bank = build_case_a(rng, matched)
    sections = [{"year": 2026, "month": 1, "opening": bank["opening"], "closing": bank["closing"], "txs": bank["txs"]}]
    ps, pe = date(2026, 1, 1), date(2026, 6, 30)
    pdf = docs_dir / case["statement_filename"]
    render = render_statement(pdf, case, sections, "id", GENERATED_ON, section_titles=False, period_start=ps, period_end=pe)
    gt_bank = ground_truth_bank(case, sections, render, ps, pe)
    write_json(gt_dir / "bank_statement.json", gt_bank)

    extras = {}
    for i, r in enumerate(recs):
        p = docs_dir / r["filename"]
        if r["handwritten"]:
            extras[r["filename"]] = render_receipt_handwritten(r, p, seed=seed * 1000 + 300 + i)
        else:
            extras[r["filename"]] = render_receipt_printed(r, p, seed=seed * 1000 + 300 + i)
    write_json(gt_dir / "receipts.json", ground_truth_receipts_a(recs, extras))

    premises_warung(seed * 10 + 1, 1, docs_dir / "premises_01.jpg")
    premises_warung(seed * 10 + 2, 2, docs_dir / "premises_02.jpg")

    docs = [{"filename": case["statement_filename"], "doc_type": "bank_statement", "pages": pdf_pages(pdf),
             "ground_truth": "ground_truth/bank_statement.json", "description": "6-month mobile banking statement, Jan-Jun 2026"}]
    for r in recs:
        docs.append({"filename": r["filename"], "doc_type": "receipt", "pages": 1, "ground_truth": "ground_truth/receipts.json",
                     "description": ("handwritten supplier nota" if r["handwritten"] else "printed supplier receipt") + f" - {r['merchant']}"})
    docs.append({"filename": "premises_01.jpg", "doc_type": "premises_photo", "pages": 1, "ground_truth": None, "description": "storefront"})
    docs.append({"filename": "premises_02.jpg", "doc_type": "premises_photo", "pages": 1, "ground_truth": None, "description": "shop interior"})
    write_json(out / "A" / "manifest.json", manifest_for(
        case, docs, traps, seed,
        "Clean control case: no traps. Healthy, slightly growing inflow; receipts partly paid by bank transfer (matching TRF KE rows)."))
    return {"bank": gt_bank}


# --------------------------------------------------------------------------------------
def gen_case_b(out: Path, seed: int, traps: dict):
    case = CASES["B"]
    rng = random.Random(seed * 100 + 2)
    docs_dir = out / "B" / "docs"
    gt_dir = out / "B" / "ground_truth"
    docs_dir.mkdir(parents=True, exist_ok=True)

    plan = plan_months(rng)  # Dec 2025 .. Jun 2026
    bank_months = plan[:6]  # Dec..May
    dash_months = plan[1:]  # Jan..Jun
    bank = build_case_b(rng, bank_months)
    sections = [{"year": 2025, "month": 12, "opening": bank["opening"], "closing": bank["closing"], "txs": bank["txs"]}]
    ps, pe = date(2025, 12, 1), date(2026, 5, 31)
    pdf = docs_dir / case["statement_filename"]
    render = render_statement(pdf, case, sections, "vi", GENERATED_ON, section_titles=False, period_start=ps, period_end=pe)
    gt_bank = ground_truth_bank(case, sections, render, ps, pe, notes={
        "planted": {
            "T11": "row dated 2026-02-17 with credit 18,500,000 whose balance_after equals the previous row",
            "T12": "row in April whose balance_after is 7,200,000 lower than prev + credit - debit",
            "monthly_shopee_payout_totals": {f"{m['year']}-{m['month']:02d}": m["payout"] for m in bank_months},
            "monthly_cod_deposit_totals": {f"{m['year']}-{m['month']:02d}": m["cod_value"] for m in bank_months},
        }
    })
    write_json(gt_dir / "bank_statement.json", gt_bank)

    rendered = []
    for mp in dash_months:
        fname = f"shopee_dashboard_{mp['year']}-{mp['month']:02d}.png"
        bboxes = render_dashboard(mp, docs_dir / fname, random.Random(seed * 100 + mp["month"]))
        rendered.append((mp, fname, bboxes))
    write_json(gt_dir / "dashboards.json", ground_truth_dashboards(rendered))

    lrecs = plan_logistics_b(rng)
    extras = {r["filename"]: render_logistics(r, docs_dir / r["filename"]) for r in lrecs}
    write_json(gt_dir / "receipts.json", ground_truth_logistics(lrecs, extras))

    premises_stockroom(seed * 10 + 3, docs_dir / "premises_01.jpg")

    docs = [{"filename": case["statement_filename"], "doc_type": "bank_statement", "pages": pdf_pages(pdf),
             "ground_truth": "ground_truth/bank_statement.json", "description": "6-month mobile banking statement, Dec 2025-May 2026"}]
    for mp, fname, _ in rendered:
        docs.append({"filename": fname, "doc_type": "seller_dashboard", "pages": 1, "ground_truth": "ground_truth/dashboards.json",
                     "description": f"Shopee seller centre capture for {mp['year']}-{mp['month']:02d}"})
    for r in lrecs:
        docs.append({"filename": r["filename"], "doc_type": "logistics_receipt", "pages": 1, "ground_truth": "ground_truth/receipts.json",
                     "description": f"{r['carrier']} drop-off receipt {r['receipt_number']}"})
    docs.append({"filename": "premises_01.jpg", "doc_type": "premises_photo", "pages": 1, "ground_truth": None, "description": "home stock room"})
    write_json(out / "B" / "manifest.json", manifest_for(
        case, docs, traps, seed,
        "Trap case: carries T01-T14 (double counting, round trips, document reuse, period/balance breaks, hidden debt)."))
    return {"bank": gt_bank}


# --------------------------------------------------------------------------------------
def gen_case_c(out: Path, seed: int, traps: dict, past_dir: Path):
    case = CASES["C"]
    rng = random.Random(seed * 100 + 3)
    docs_dir = out / "C" / "docs"
    gt_dir = out / "C" / "ground_truth"
    docs_dir.mkdir(parents=True, exist_ok=True)

    months = plan_ledger(rng)
    bank = build_case_c(rng, income_list(months))
    ps, pe = date(2026, 1, 1), date(2026, 6, 30)
    pdf = docs_dir / case["statement_filename"]
    render = render_statement(pdf, case, bank["sections"], "en", GENERATED_ON, section_titles=True, period_start=ps, period_end=pe)
    gt_bank = ground_truth_bank(case, bank["sections"], render, ps, pe, notes={
        "months_missing": ["2026-03", "2026-04"],
        "planted": {"T16": "header period Jan-Jun 2026, but March and April pages are absent; May BALANCE FORWARD 61,400.00 != Feb ENDING BALANCE 48,950.00"},
    })
    write_json(gt_dir / "bank_statement.json", gt_bank)

    pages = build_pages(months)
    gt_ledger = render_pages(pages, docs_dir)
    write_json(gt_dir / "ledger.json", gt_ledger)

    premises_garage(seed * 10 + 4, docs_dir / "premises_01.jpg")
    # T20: reuse of a prior applicant's photo (byte-identical copy)
    past_case = past_dir / "PAST-2025-0471"
    past_case.mkdir(parents=True, exist_ok=True)
    premises_workshop_interior(seed * 10 + 5, past_case / "premises.jpg")
    shutil.copyfile(past_case / "premises.jpg", docs_dir / "premises_02.jpg")
    ph = imagehash.phash(Image.open(past_case / "premises.jpg"))
    write_json(past_dir / "index.json", [{
        "case_id": "PAST-2025-0471", "filename": "premises.jpg", "sha256": sha256_file(past_case / "premises.jpg"),
        "phash": str(ph), "applicant": "Motortek Auto Service (synthetic prior applicant)", "filed": "2025-09-18",
        "note": "Synthetic. Used by trap T20: case C premises_02.jpg is a byte-identical copy of this file.",
    }])

    docs = [{"filename": case["statement_filename"], "doc_type": "bank_statement", "pages": pdf_pages(pdf),
             "ground_truth": "ground_truth/bank_statement.json",
             "description": "Statement with header period Jan-Jun 2026; only Jan, Feb, May, Jun pages present"}]
    for g in gt_ledger:
        docs.append({"filename": g["filename"], "doc_type": "handwritten_ledger", "pages": 1, "ground_truth": "ground_truth/ledger.json",
                     "description": f"handwritten ledger page - {g['period_label']}"})
    docs.append({"filename": "premises_01.jpg", "doc_type": "premises_photo", "pages": 1, "ground_truth": None, "description": "shop front with signage"})
    docs.append({"filename": "premises_02.jpg", "doc_type": "premises_photo", "pages": 1, "ground_truth": None, "description": "workshop interior"})
    write_json(out / "C" / "manifest.json", manifest_for(
        case, docs, traps, seed,
        "Incomplete-documents case: carries T15-T20 (ledger page reuse, missing statement months, hidden debt, ledger/deposit double count, reused premises photo)."))
    return {"bank": gt_bank}


# --------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="cases", help="output directory (relative to data/synth)")
    ap.add_argument("--imagen", action="store_true", help="(reserved) use Gemini image generation for premises photos; default off")
    args = ap.parse_args(argv)
    if args.imagen:
        print("note: --imagen is reserved and currently a no-op; using PIL illustrations")

    out = (SYNTH_DIR / args.out).resolve()
    past_dir = SYNTH_DIR / "past_cases"
    for sub in ("A", "B", "C"):
        shutil.rmtree(out / sub, ignore_errors=True)
    shutil.rmtree(past_dir, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    traps = load_traps()

    print("generating case A ...")
    gen_case_a(out, args.seed, traps)
    print("generating case B ...")
    gen_case_b(out, args.seed, traps)
    print("generating case C ...")
    gen_case_c(out, args.seed, traps, past_dir)

    index = []
    for cid in ("A", "B", "C"):
        with open(out / cid / "manifest.json", encoding="utf-8") as fh:
            m = json.load(fh)
        index.append({"case_id": cid, "name": m["name"], "expected_outcome": m["expected_outcome"],
                      "documents": len(m["documents"]), "traps": m["traps"], "manifest": f"{cid}/manifest.json"})
    write_json(out / "index.json", {"seed": args.seed, "cases": index, "traps_file": "../traps.json", "synthetic": True})
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) + sum(p.stat().st_size for p in past_dir.rglob("*") if p.is_file())
    print(f"done. total size {total / 1e6:.1f} MB -> {out}")


if __name__ == "__main__":
    main()
