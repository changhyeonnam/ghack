# Synthetic case data — specification

No real customer data. Three fictional micro-businesses, 20 planted traps, and a ground-truth answer key.
Every generated file carries a visible "SYNTHETIC · FOR DEMO" watermark. All generation is seeded and
deterministic (`python generate.py --out cases`).

## Output layout
```
data/synth/cases/<case_id>/
  manifest.json
  docs/<files...>                 # exactly what gets uploaded to LedgerLens
  ground_truth/*.json             # answer key used by the benchmark + mock mode
data/synth/traps.json             # 20 traps (already written — do not change ids/types; refine details freely)
data/synth/past_cases/            # one premises photo + hash index used for cross-case reuse trap T20
```

### manifest.json
```json
{
  "case_id": "A", "name": "Warung Ibu Sari", "business_name": "Warung Ibu Sari",
  "sector": "grocery retail", "country": "ID", "city": "Jakarta", "language": "id", "currency": "IDR",
  "requested_amount": 25000000, "expected_outcome": "approve",
  "account_holder": "SARI DEWI", "bank_name": "Bank Nusantara Digital (synthetic)",
  "documents": [
    {"filename": "bank_statement_2026H1.pdf", "doc_type": "bank_statement", "pages": 7,
     "ground_truth": "ground_truth/bank_statement.json", "description": "6-month mobile banking statement"},
    {"filename": "receipt_01.jpg", "doc_type": "receipt", "pages": 1, "ground_truth": "ground_truth/receipts.json"},
    {"filename": "premises_01.jpg", "doc_type": "premises_photo", "pages": 1, "ground_truth": null}
  ],
  "traps": []
}
```
`doc_type` ∈ bank_statement | seller_dashboard | receipt | handwritten_ledger | premises_photo | logistics_receipt.

### ground_truth/bank_statement.json
```json
{"account_holder": "...", "bank_name": "...", "currency": "IDR", "period_start": "2026-01-01", "period_end": "2026-06-30",
 "opening_balance": 4350000, "closing_balance": 9120000,
 "transactions": [
   {"row_id": "T0001", "date": "2026-01-02", "description": "QRIS SALES SETTLEMENT", "counterparty": null,
    "debit": 0, "credit": 1250000, "balance_after": 5600000, "page": 1, "bbox": [182, 40, 196, 960],
    "trap_ids": []}
 ]}
```
`bbox` = `[ymin, xmin, ymax, xmax]` normalized to 0–1000 of the rendered page (ReportLab knows where it drew
each row: convert points → normalized). `trap_ids` lists traps this row participates in (e.g. a self-transfer).
Balances must be continuous (prev + credit − debit = balance_after) **except** where a balance-break trap is planted.

### ground_truth/dashboards.json
```json
[{"filename": "shopee_dashboard_2026-01.png", "platform": "Shopee", "shop_name": "Linh Fashion Official",
  "period_start": "2026-01-01", "period_end": "2026-01-31", "data_as_of": "2026-02-01",
  "metrics": {"gross_sales": 48200000, "orders": 312, "payout": 43100000, "followers": 12400, "rating": 4.9, "visitors": 9800},
  "bboxes": {"gross_sales": [210, 60, 260, 330]}, "trap_ids": []}]
```
### ground_truth/receipts.json
```json
[{"filename": "receipt_01.jpg", "merchant": "Toko Grosir Makmur", "date": "2026-02-03", "receipt_number": "TGM-0931",
  "currency": "IDR", "total": 1875000, "direction": "purchase", "handwritten": false,
  "items": [{"description": "Beras 25kg x4", "amount": 1300000}], "trap_ids": []}]
```
### ground_truth/ledger.json (case C only)
```json
[{"filename": "ledger_p1.jpg", "period_label": "Enero 2026", "business_name_header": "Reyes Auto Repair",
  "entries": [{"row_id": "L0001", "date": "2026-01-03", "description": "Change oil - Toyota Vios", "amount": 1800,
               "kind": "income", "bbox": [120, 40, 150, 960]}], "trap_ids": []}]
```

## The three cases
| Case | Business | Country/currency/lang | Documents | Expected |
|---|---|---|---|---|
| A | Warung Ibu Sari — neighbourhood grocery kiosk, Jakarta | ID / IDR / id | 6-month bank statement PDF (Jan–Jun 2026, ~25–35 tx/month: QRIS settlements, cash deposits, supplier transfers, small utilities), 15 supplier receipt photos (purchases; mix of printed thermal receipts and 3 handwritten), 2 premises photos | approve. Clean: no traps. Healthy, slightly growing inflow (~IDR 28–35M/month), low volatility. |
| B | Linh Fashion Online — Shopee clothing seller, Ho Chi Minh City | VN / VND / vi | bank statement Dec 2025–May 2026 (6 months), 6 Shopee dashboard captures Jan–Jun 2026, 6 logistics receipts (GHN/J&T), 1 premises photo (home stock room) | approve_with_conditions. Carries traps T01–T14. |
| C | Reyes Auto Repair — motor repair shop, Manila | PH / PHP / tl+en | bank statement Jan–Feb + May–Jun 2026 (Mar–Apr missing), 8 handwritten ledger page photos, 2 premises photos | request_more_documents (or reject). Carries traps T15–T20. |

Realism notes: statements should look like a real mobile-banking export (bank logo text, account holder,
masked account number, period, opening/closing balance, running balance column, page x of y). Vietnamese
statements use descriptions like "CHUYEN TIEN TU SHOPEE PAYOUT", Indonesian like "TRF DARI ... / QRIS / SETOR TUNAI",
Filipino/English like "GCASH TRANSFER / CASH DEPOSIT / BDO AUTO LOAN". Amounts in local magnitude (IDR millions,
VND millions, PHP thousands). Use descriptions a real underwriter would see; keep the fictional bank names.

## Trap mechanics (see traps.json for ids; implement exactly these effects)
- **T01** Shopee GMV on dashboards vs `SHOPEE PAYOUT` credits in the bank: payouts ≈ 88–92 % of GMV, same months. Memo must not sum them.
- **T02** Each dashboard shows both "Gross sales" and "Total payout" cards — payout is a subset of gross sales.
- **T03** Dashboards show "COD orders" revenue; bank shows lumpy `NOP TIEN MAT` (cash deposit) credits of similar monthly totals — same money.
- **T04–T06** Three credits `CHUYEN TIEN TU NGUYEN THI LINH - VCB` (own account at another bank) 20–35M VND each, on different months.
- **T07** `NHAN TU NGUYEN VAN LONG` +50,000,000 on 2026-03-14 and `CHUYEN DEN NGUYEN VAN LONG` −50,000,000 on 2026-03-20.
- **T08** Logistics receipt reused: `ghn_receipt_02.jpg` and `ghn_receipt_05.jpg` are the same rendered receipt (same receipt number GHN-2231, same items) except the printed date (2026-02-11 vs 2026-03-11). Pixel-identical apart from the date glyphs so a perceptual hash is near-identical.
- **T09** Followers on dashboards: Jan 12,400 · Feb 12,900 · Mar 9,800 · Apr 13,600 · May 13,900 · Jun 14,200 — the March capture is inconsistent (and its shop name reads "Linh Fashion VN" instead of "Linh Fashion Official").
- **T10** Dashboards cover Jan–Jun 2026 but the statement covers Dec 2025–May 2026: June dashboard has no bank counterpart; December bank has no dashboard.
- **T11** Balance break #1: on the statement, one credit row (`THANH TOAN DON HANG` +18,500,000, 2026-02-17) is present but the running balance does not move (balance_after equals the previous row).
- **T12** Balance break #2: between two April rows the balance jumps down by 7,200,000 with no debit row (a deleted row).
- **T13** `CHUYEN DEN FE CREDIT - TRA GOP` −3,250,000 on the 5th of every month, all 6 months.
- **T14** `SPAYLATER THANH TOAN` −1,480,000 around the 20th of every month.
- **T15** Ledger photo reused: `ledger_p3.jpg` (Marso) and `ledger_p6.jpg` (Abril) are the same page render with the month header swapped — entries identical.
- **T16** Statement missing Mar–Apr 2026: the May page's opening balance (PHP 61,400) ≠ February's closing balance (PHP 48,950); the "period" header says Jan–Jun.
- **T17** `BDO AUTO LOAN PAYMENT` −14,800 monthly on the 10th (in the 4 months present).
- **T18** `GCASH TRANSFER TO JUAN DELA CRUZ` −3,000 every Friday (informal lender pattern).
- **T19** Ledger shows daily cash income (≈ PHP 2–6k/day); bank shows `CASH DEPOSIT` credits each Monday equal to the previous week's ledger cash income — counting both doubles revenue.
- **T20** `premises_02.jpg` in case C is byte-identical to `data/synth/past_cases/past_case_X/premises.jpg` (a prior applicant). Write `past_cases/index.json` = `[{"case_id":"PAST-2025-0471","filename":"premises.jpg","sha256":"...","phash":"..."}]`.

## Rendering guidance
- Bank statements: ReportLab, A4, 25–40 rows per page, monospace amounts right-aligned, header block, footer with
  page x/y and watermark "SYNTHETIC · FOR DEMO" diagonal light grey. Record each row's bbox.
- Dashboards: PIL. 1600×1000 PNG. Platform header bar, shop name + period selector text, 4–6 KPI cards with label
  + value, a simple bar chart (days), a small table. Watermark bottom-right. Record KPI bboxes (normalized).
- Receipts: PIL. ~600×1100 thermal-receipt look (monospace font e.g. Courier New / Andale Mono), slight rotation
  (±3°), subtle noise, off-white paper on dark background to look like a phone photo. Handwritten ones: use
  "Bradley Hand Bold.ttf" / "Noteworthy.ttc" / "Chalkboard.ttc" from /System/Library/Fonts/Supplemental.
- Handwritten ledger: PIL. Lined notebook page 1200×1600, handwriting font, header with business name + month,
  columns Petsa / Deskripsyon / Halaga, ~18–25 rows per page, running weekly totals.
- Premises photos: PIL stylised storefront illustration 1400×1000 (building, awning, sign with business name,
  shelves/goods or a car on a lift). It does not need to be photorealistic; it needs readable signage and an
  apparent size. Optional `--imagen` flag may call Gemini image generation; default OFF (cost).
- Fonts: check `/System/Library/Fonts` and `/System/Library/Fonts/Supplemental`; fall back to PIL default.

## Deliverables
1. `data/synth/generate.py` (+ helper modules) producing everything above deterministically with `--seed 7`.
2. `data/synth/cases/{A,B,C}/...` generated and committed (PDF+PNG+JPG+JSON).
3. `data/synth/past_cases/...` and `index.json`.
4. `data/synth/README.md` (English): what is synthetic, how to regenerate, trap table.
5. A quick `python verify.py` that re-reads ground truth and asserts: balance continuity holds except at T11/T12/T16,
   all trap effects are present, duplicate images hash-match (imagehash phash distance ≤ 4), file counts match manifests.
