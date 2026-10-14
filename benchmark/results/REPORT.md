# LedgerLens benchmark (mock, gemini-3.8-flash)

Generated 2026-10-14T11:11:36+00:00

> **Mock mode**: no Gemini calls were made. Extraction comes from the synthetic answer key and the Challenger is the deterministic battery only, so this measures the pipeline and the tools, not the model. The baseline row is a stub in this mode. Re-run with GOOGLE_API_KEY set for the real numbers.

| Metric | LedgerLens | Single-prompt baseline | Target |
|---|---|---|---|
| Trap recall | 19/20 (0.95) | 0/20 (0.0) | >= 16/20 |
| Unsourced numbers | 0 | 6 | 0 |
| Objections on clean case A | 0 (share 0.0) | - | <= 20% |
| Extraction row accuracy | 1.0 | - | >= 97% |
| Evidence-link accuracy | 1.0 | - | >= 95% |
| Avg time per case | 4.5 s | - | <= 180 s |
| Avg cost per case | $0.0 | - | <= $0.50 |

## Per case

### Case A - Warung Ibu Sari: expected approve, got approve
traps 0/0, objections 0, unsourced 0, 5.0 s, $0.0, tokens 0

### Case B - Linh Fashion Online: expected approve_with_conditions, got approve_with_conditions
traps 13/14, objections 12, unsourced 0, 2.9 s, $0.0, tokens 0
- T01 Shopee GMV and bank payouts are the same money: caught by O01 | baseline: missed
- T02 Dashboard gross sales vs dashboard payout: caught by O01 | baseline: missed
- T03 COD dashboard revenue vs cash deposits: MISSED | baseline: missed
- T04 Own-account transfer #1 counted as income: caught by O05,O06,O07 | baseline: missed
- T05 Own-account transfer #2 counted as income: caught by O05,O06,O07 | baseline: missed
- T06 Own-account transfer #3 counted as income: caught by O05,O06,O07 | baseline: missed
- T07 Family round-trip 50,000,000 in and out: caught by O08 | baseline: missed
- T08 Logistics receipt reused with a changed date: caught by O02 | baseline: missed
- T09 March dashboard inconsistent (followers, shop name): caught by O09 | baseline: missed
- T10 Dashboard period vs statement period: caught by O10 | baseline: missed
- T11 Balance continuity break: credit without balance change: caught by O03,O04 | baseline: missed
- T12 Balance continuity break: missing debit row: caught by O03,O04 | baseline: missed
- T13 FE Credit instalment every month: caught by O11,O12 | baseline: missed
- T14 SPayLater repayment every month: caught by O11,O12 | baseline: missed

### Case C - Reyes Auto Repair: expected request_more_documents, got request_more_documents
traps 6/6, objections 7, unsourced 0, 5.7 s, $0.0, tokens 0
- T15 Ledger page photographed twice with month changed: caught by O01,O04 | baseline: missed
- T16 Two statement months missing; balances do not chain: caught by O02,O05 | baseline: missed
- T17 BDO auto loan payment monthly: caught by O06 | baseline: missed
- T18 Weekly GCash transfer to an individual (informal lender): caught by O06 | baseline: missed
- T19 Ledger cash income vs Monday cash deposits: caught by O03 | baseline: missed
- T20 Premises photo reused from a previous applicant: caught by O01 | baseline: missed
