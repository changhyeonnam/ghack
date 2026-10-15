# LedgerLens benchmark (cache_only, gemini-3.8-flash)

Generated 2026-10-15T07:15:03+00:00



Scoring is strict: an objection counts for a trap only if it carries the trap's identifying evidence (amount or document; keywords only for traps defined by neither) under an expected checklist question, and each objection counts for at most one trap. The earlier any-keyword rule would give 18/20. 95% Wilson interval for recall: [0.58, 0.92]. Synthetic data, n = 3 businesses.

| Metric | LedgerLens | Single-prompt baseline | Target |
|---|---|---|---|
| Trap recall | 16/20 (0.8) | 1/20 (0.05) | >= 16/20 |
| Unsourced numbers | 0 | 45 | 0 |
| Objections on clean case A | 1 (share 0.045) | - | <= 20% |
| Extraction row accuracy | 1.0 | - | >= 97% |
| Evidence-link accuracy | 1.0 | - | >= 95% |
| Avg time per case | 6.8 s | - | <= 180 s |
| Avg cost per case | $0.0 | - | <= $0.50 |

## Per case

### Case A - Warung Ibu Sari: expected approve, got approve_with_conditions
traps 0/0, objections 1, unsourced 0, 7.2 s, $0.0, tokens 103102

### Case B - Linh Fashion Online: expected approve_with_conditions, got approve_with_conditions
traps 12/14, objections 13, unsourced 0, 4.8 s, $0.0, tokens 98889
- T01 Shopee GMV and bank payouts are the same money: caught by O01 | baseline: missed
- T02 Dashboard gross sales vs dashboard payout: MISSED | baseline: missed
- T03 COD dashboard revenue vs cash deposits: MISSED | baseline: missed
- T04 Own-account transfer #1 counted as income: caught by O05 | baseline: missed
- T05 Own-account transfer #2 counted as income: caught by O06 | baseline: missed
- T06 Own-account transfer #3 counted as income: caught by O07 | baseline: missed
- T07 Family round-trip 50,000,000 in and out: caught by O08 | baseline: missed
- T08 Logistics receipt reused with a changed date: caught by O02 | baseline: missed
- T09 March dashboard inconsistent (followers, shop name): caught by O09 | baseline: missed
- T10 Dashboard period vs statement period: caught by O10 | baseline: missed
- T11 Balance continuity break: credit without balance change: caught by O03 | baseline: missed
- T12 Balance continuity break: missing debit row: caught by O04 | baseline: missed
- T13 FE Credit instalment every month: caught by O11 | baseline: missed
- T14 SPayLater repayment every month: caught by O12 | baseline: missed

### Case C - Reyes Auto Repair: expected request_more_documents, got reject
traps 4/6, objections 8, unsourced 0, 8.3 s, $0.0, tokens 76887
- T15 Ledger page photographed twice with month changed: caught by O01 | baseline: missed
- T16 Two statement months missing; balances do not chain: caught by O03 | baseline: missed
- T17 BDO auto loan payment monthly: caught by O05 | baseline: caught
- T18 Weekly GCash transfer to an individual (informal lender): MISSED | baseline: missed
- T19 Ledger cash income vs Monday cash deposits: MISSED | baseline: missed
- T20 Premises photo reused from a previous applicant: caught by O02 | baseline: missed
