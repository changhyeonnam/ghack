"""Stage 5: the Challenger. Deterministic battery first, then an ADK two-step agent (investigator with tools ->
writer with schema). Tool-proven findings are guaranteed to surface: anything the LLM fails to report is appended
as a rule-based objection with `tool_evidence`, so the deterministic floor is never lost."""
from __future__ import annotations

import re
from typing import Any, Optional

from google.genai import types

from ..config import Settings
from ..schemas import (
    Case, CashflowSummary, ChallengeDraft, ChallengeResult, DocumentExtraction, DocumentMeta, FeedbackPriorities, IntakeResult,
    Memo, Objection, Severity, SourceRef, ToolFindings,
)
from ..storage import Repository
from ..tools import checks
from ..tools.cashflow import recompute_balances
from ..tools.documents import phash_distance
from . import prompts
from .common import DEMO_DATASET_NOTE, case_facts, catalog_text, extraction_digest, inventory_text, ref_dict, render_memo_text
from .runner import AgentSpec, CacheMiss, run_sequence

SEV_ORDER = {Severity.critical: 0, Severity.high: 1, Severity.medium: 2, Severity.low: 3}


# ---------------------------------------------------------------------------
# Deterministic floor
# ---------------------------------------------------------------------------
def rule_based_objections(tf: ToolFindings, cf: CashflowSummary, docs: dict[str, DocumentMeta], currency: str) -> list[Objection]:
    out: list[Objection] = []
    n = 0

    def nxt() -> str:
        nonlocal n
        n += 1
        return f"R{n:02d}"

    name = lambda d: docs[d].filename if d in docs else d  # noqa: E731
    for b in tf.balance_checks:
        out.append(Objection(id=nxt(), question_id="Q6", severity=Severity.critical, title=f"Running balance breaks at row {b.row_id}",
                             claim=f"On {b.date} (row {b.row_id}) the printed balance is {b.reported_balance:,.0f} but previous balance + credit - debit gives {b.expected_balance:,.0f} (difference {b.difference:+,.0f} {currency}). Either a row is missing or the statement was edited.",
                             evidence_refs=[b.source], tool_evidence=f"recompute_balance_chain: expected {b.expected_balance:,.0f}, reported {b.reported_balance:,.0f}",
                             suggested_action="Request the original statement directly from the bank (or an API pull) and reconcile this row.", financial_impact=abs(b.difference)))
    for d in tf.image_duplicates:
        if d.cross_case:
            out.append(Objection(id=nxt(), question_id="Q4", severity=Severity.critical, title=f"{name(d.doc_a)} was already filed in past case {d.other_case_id}",
                                 claim=f"Document {d.doc_a} ({name(d.doc_a)}) is {'byte-identical' if d.kind == 'exact' else 'near-identical'} (hamming {d.hamming_distance}) to {d.doc_b} from a previous applicant's case {d.other_case_id}. Premises or receipt evidence may not belong to this applicant.",
                                 evidence_refs=[SourceRef(doc_id=d.doc_a, page=d.page_a)], tool_evidence=f"image_similarity vs past-case index: {d.kind}, hamming {d.hamming_distance}",
                                 suggested_action="Disregard this document and request a fresh, geo-tagged photo taken during a site visit."))
        else:
            out.append(Objection(id=nxt(), question_id="Q4", severity=Severity.high if d.kind == "near" else Severity.critical, title=f"{name(d.doc_a)} and {name(d.doc_b)} are the same image",
                                 claim=f"{d.doc_a} page {d.page_a} and {d.doc_b} page {d.page_b} are {'identical' if d.kind == 'exact' else f'near-identical (perceptual hash distance {d.hamming_distance})'}; one of them is a reuse, possibly with an edited date or header.",
                                 evidence_refs=[SourceRef(doc_id=d.doc_a, page=d.page_a), SourceRef(doc_id=d.doc_b, page=d.page_b)],
                                 tool_evidence=f"image_similarity: {d.kind}, hamming {d.hamming_distance}", suggested_action="Count the document once and ask the applicant for the missing original."))
    for r in tf.recurring_transfers:
        if r.likely_debt_service:
            monthly = r.amount * (4.33 if len(r.months) < r.occurrences else 1)
            out.append(Objection(id=nxt(), question_id="Q7", severity=Severity.high if monthly >= 0.5 * (cf.avg_monthly_outflow or 1) * 0.1 else Severity.medium,
                                 title=f"Recurring transfer to {r.counterparty} looks like loan repayment",
                                 claim=f"{r.occurrences} debits of {r.amount:,.0f} {currency} to {r.counterparty} ({', '.join(r.months)}, around day {r.day_of_month_mode}). The pattern matches an undisclosed instalment or informal lender; it should be treated as existing debt service of about {monthly:,.0f} per month.",
                                 evidence_refs=r.source_refs[:6], tool_evidence=f"recurring detector: rows {','.join(r.row_ids[:8])}",
                                 suggested_action="Ask the applicant to disclose the facility (lender, balance, tenor) and deduct the instalment from repayment capacity.", financial_impact=monthly))
    for f in tf.self_transfers:
        out.append(Objection(id=nxt(), question_id="Q3", severity=Severity.high, title=f"Credit of {f.amount:,.0f} on {f.date} comes from the applicant's own account",
                             claim=f"Row {f.row_id} '{f.description}' ({f.amount:,.0f} {currency}) names the account holder as the sender. It is a transfer between the applicant's own accounts, not revenue.",
                             evidence_refs=[f.source], tool_evidence="self-transfer detector: sender tokens match account holder", suggested_action="Exclude from business inflow; ask for the other account's statement.", financial_impact=f.amount))
    for f in tf.round_trips:
        out.append(Objection(id=nxt(), question_id="Q3", severity=Severity.high, title=f"{f.amount:,.0f} received on {f.date} was sent back within two weeks",
                             claim=f"Row {f.row_id} '{f.description}' credits {f.amount:,.0f} {currency}; the same amount leaves again in row {f.matched_row_id} to the same counterparty. This is a round-trip, not revenue, and may be balance window-dressing.",
                             evidence_refs=[f.source], tool_evidence=f"round-trip detector: matched row {f.matched_row_id}", suggested_action="Exclude both legs from the cash-flow analysis and ask the applicant to explain.", financial_impact=f.amount))
    if tf.payout_reconciliation and tf.payout_reconciliation.double_count_risk:
        p = tf.payout_reconciliation
        out.append(Objection(id=nxt(), question_id="Q1", severity=Severity.critical, title="Marketplace sales and bank payouts are the same money",
                             claim=f"Dashboards show gross sales {p.dashboard_gross_sales:,.0f} and payouts {p.dashboard_payout:,.0f}; the bank statement already contains {p.bank_platform_payouts:,.0f} of platform payouts. Adding dashboard revenue on top of bank inflow double counts it.",
                             evidence_refs=[], tool_evidence=f"payout reconciliation: bank/dashboard payout ratio {p.ratio_payout_to_bank}", suggested_action="Use bank payouts as the revenue base; treat dashboard figures as corroboration only.",
                             financial_impact=min(p.dashboard_payout or p.dashboard_gross_sales, p.bank_platform_payouts)))
    if tf.cash_reconciliation and tf.cash_reconciliation.double_count_risk:
        c = tf.cash_reconciliation
        out.append(Objection(id=nxt(), question_id="Q1", severity=Severity.high, title="Ledger cash income is the same cash later deposited",
                             claim=f"Ledger/receipt sales total {c.ledger_income + c.receipts_sales:,.0f} while bank cash deposits total {c.bank_cash_deposits:,.0f}; the deposits are the ledger's cash banked, so summing both overstates revenue.",
                             evidence_refs=[], tool_evidence="cash reconciliation: deposits/ledger ratio inside 0.4-1.6", suggested_action="Count cash income once (prefer the ledger, cross-check with deposits).", financial_impact=min(c.ledger_income + c.receipts_sales, c.bank_cash_deposits)))
    for pc in tf.period_checks:
        if not pc.consistent and not (pc.doc_a == pc.doc_b and tf.months_missing):  # self-check duplicates months_missing
            out.append(Objection(id=nxt(), question_id="Q5", severity=Severity.medium, title="Document periods do not line up",
                                 claim=f"{pc.period_a} versus {pc.period_b}: months only in the first: {', '.join(pc.only_in_a) or 'none'}; only in the second: {', '.join(pc.only_in_b) or 'none'}. Sales claimed for months without bank evidence cannot be verified.",
                                 evidence_refs=[SourceRef(doc_id=pc.doc_a, page=1)], tool_evidence="date_crosscheck", suggested_action="Request the statement months that are missing or drop the uncovered dashboard/ledger months."))
    if tf.months_missing:
        out.append(Objection(id=nxt(), question_id="Q5", severity=Severity.high, title=f"No statement rows for {', '.join(tf.months_missing)}",
                             claim=f"The statement header covers the period but there are no transactions in {', '.join(tf.months_missing)}. Pages may have been removed; averages computed on the remaining months overstate coverage.",
                             evidence_refs=[], tool_evidence="months_missing from cashflow model", suggested_action="Request the missing months before relying on averages."))
    for e in tf.entity_checks:
        if not e.consistent:
            q = "Q12" if e.field in ("currency", "language") else "Q11"
            out.append(Objection(id=nxt(), question_id=q, severity=Severity.medium, title=f"Inconsistent {e.field.replace('_', ' ')} across documents",
                                 claim=f"{e.note or 'Values differ'}: " + "; ".join(f"{k}={v}" for k, v in list(e.values.items())[:6]),
                                 evidence_refs=[SourceRef(doc_id=k, page=1) for k in e.values if k in docs][:4], tool_evidence="entity consistency check",
                                 suggested_action="Confirm the legal/trading name and account ownership with the applicant."))
    if cf.end_of_month_concentration >= 0.5 and cf.months_covered >= 3:
        out.append(Objection(id=nxt(), question_id="Q10", severity=Severity.medium, title="Inflow concentrated in the last days of each month",
                             claim=f"{cf.end_of_month_concentration:.0%} of inflow lands in the last five days of the month, which is unusual for daily retail and consistent with window-dressing before statement cut-off.",
                             evidence_refs=[], tool_evidence="end_of_month_concentration", suggested_action="Ask for daily sales records to explain the timing."))
    for v in tf.text_layer_checks:
        if v.text_layer and v.amounts_missing:
            refs = []
            for m in v.amounts_missing[:6]:
                refs.append(SourceRef(doc_id=v.doc_id, page=int(m.get("page") or 1)))
            out.append(Objection(id=nxt(), question_id="Q9", severity=Severity.high if len(v.amounts_missing) > 2 else Severity.medium,
                                 title=f"{len(v.amounts_missing)} extracted amounts are not in the PDF text of {name(v.doc_id)}",
                                 claim=f"The statement has a text layer, but {len(v.amounts_missing)} of {v.rows} extracted amounts do not occur verbatim on their page "
                                       f"(e.g. rows {', '.join(m['row_id'] for m in v.amounts_missing[:5])}). These values may be misreads and must not be relied on until re-checked.",
                                 evidence_refs=refs, tool_evidence=f"text-layer cross-check: amount match {v.amount_match_rate}, bbox match {v.bbox_match_rate}",
                                 suggested_action="Re-extract these rows or confirm them against the original PDF before using the affected figures."))
    if tf.unsourced_figure_ids or tf.unsourced_numerals:
        out.append(Objection(id=nxt(), question_id="Q9", severity=Severity.critical, title="Memo contains numbers without a source reference",
                             claim=f"Unsourced figure ids: {', '.join(tf.unsourced_figure_ids) or 'none'}. Unsourced numerals in prose: {', '.join(u.text for u in tf.unsourced_numerals[:8]) or 'none'}.",
                             evidence_refs=[], tool_evidence="schema validation of memo figures and numeral scan", suggested_action="Regenerate the affected memo sections or strike the numbers."))
    return out


_MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def _covers(llm: Objection, rule: Objection) -> bool:
    if llm.question_id != rule.question_id:
        return False
    if llm.title.strip().lower() == rule.title.strip().lower():
        return True
    if rule.question_id in ("Q1", "Q9", "Q10"):
        return True
    # rules without document refs (e.g. missing statement months) match on the months they name
    months = set(re.findall(r"\b20\d\d-\d\d\b", rule.title + " " + rule.claim))
    if months and not rule.evidence_refs:
        txt_months = llm.claim + " " + llm.title
        names = {m: _MONTH_NAMES[int(m[5:7]) - 1] for m in months}
        if all(m in txt_months or names[m] in txt_months for m in months):
            return True
    rule_docs = {r.doc_id for r in rule.evidence_refs}
    llm_docs = {r.doc_id for r in llm.evidence_refs}
    rows = set(re.findall(r"\b[TL]\d{4}\b", rule.claim + " " + (rule.tool_evidence or "")))
    txt = llm.claim + " " + llm.title + " " + (llm.tool_evidence or "")
    if rows and any(r in txt for r in rows):
        return True
    if rule_docs and rule_docs & llm_docs:
        return True
    amt = re.findall(r"\d[\d,]{4,}", rule.claim)
    return bool(amt and any(a in txt for a in amt[:2]))


def merge_objections(llm: list[Objection], rules: list[Objection]) -> list[Objection]:
    """Tool-proven findings must surface: an LLM objection may absorb at most one rule objection, and when it does it
    takes the higher severity and the tool's evidence. Otherwise the rule objection is added as is."""
    merged = list(llm)
    absorbed: set[int] = set()
    for r in rules:
        cover = next((o for o in llm if id(o) not in absorbed and _covers(o, r)), None)
        if cover is None:
            merged.append(r)
            continue
        absorbed.add(id(cover))
        if SEV_ORDER.get(r.severity, 9) < SEV_ORDER.get(cover.severity, 9):
            cover.severity = r.severity
        have = {(e.doc_id, e.page) for e in cover.evidence_refs}
        cover.evidence_refs += [e for e in r.evidence_refs if (e.doc_id, e.page) not in have]
        # keep the specific tool finding (amount, date, row) visible inside the broader LLM objection
        finding = f"{r.title} [{r.tool_evidence}]" if r.tool_evidence else r.title
        if finding not in (cover.tool_evidence or ""):
            cover.tool_evidence = ((cover.tool_evidence + " | ") if cover.tool_evidence else "") + finding
    merged.sort(key=lambda o: (SEV_ORDER.get(o.severity, 9), o.question_id))
    for i, o in enumerate(merged, 1):
        o.id = f"O{i:02d}"
    return merged


def priorities_text(fp: Optional[FeedbackPriorities]) -> str:
    if not fp or not fp.priorities or fp.n_decisions == 0:
        return "UNDERWRITER FEEDBACK PRIORITIES: none yet (no decisions recorded)."
    rows = [f"UNDERWRITER FEEDBACK PRIORITIES (from {fp.n_decisions} signed decisions)"]
    for p in sorted(fp.priorities, key=lambda p: -p.weight):
        rows.append(f"- {p.question_id}: raised {p.raised}, accepted {p.accepted}, dismissed {p.dismissed}, weight {p.weight:.2f}")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def run_challenger(case: Case, *, memo: Memo, cashflow: CashflowSummary, extractions: list[DocumentExtraction], intake: Optional[IntakeResult],
                         repo: Repository, settings: Settings, mock_context: dict[str, Any], past_index: Optional[list[dict]] = None,
                         priorities: Optional[FeedbackPriorities] = None) -> ChallengeResult:
    docs = {d.doc_id: d for d in case.documents}
    tf = checks.run_battery(documents=case.documents, extractions=extractions, intake=intake, cashflow=cashflow, memo=memo,
                            business_name=case.business_name, country=case.country, currency=case.currency, past_index=past_index)
    digest = checks.findings_digest(tf, {d.doc_id: d.filename for d in case.documents})
    rules = rule_based_objections(tf, cashflow, docs, case.currency)

    # ---- tools (closures over this case) ----
    rows_by_id: dict[str, Any] = {}
    for ex in extractions:
        if ex.bank_statement:
            for t in ex.bank_statement.transactions:
                rows_by_id[t.row_id] = (ex.doc_id, t)

    def lookup_transactions(query: str, min_amount: float = 0.0, max_results: int = 20) -> dict:
        """Search bank-statement rows whose description or counterparty contains `query` (case-insensitive) and amount >= min_amount.

        Returns up to max_results rows with row_id, date, description, debit, credit, balance and the source ref.
        """
        q = query.upper()
        hits = []
        for rid, (doc_id, t) in rows_by_id.items():
            text = f"{t.description} {t.counterparty or ''}".upper()
            amt = t.credit or t.debit
            if (q in text or q in rid) and amt >= min_amount:
                hits.append({"row_id": rid, "date": t.date, "description": t.description, "counterparty": t.counterparty, "debit": t.debit, "credit": t.credit,
                             "balance_after": t.balance_after, "ref": ref_dict(t.source)})
        return {"query": query, "count": len(hits), "rows": hits[:max_results]}

    def recompute_balance_chain(doc_id: str) -> dict:
        """Re-run the running-balance continuity test (previous balance + credit - debit = balance) for one bank statement document."""
        exs = [e for e in extractions if e.doc_id == doc_id and e.bank_statement]
        if not exs:
            return {"error": f"{doc_id} is not an extracted bank statement"}
        res = recompute_balances(exs)
        return {"doc_id": doc_id, "rows_checked": len(exs[0].bank_statement.transactions), "breaks": [
            {"row_id": b.row_id, "date": b.date, "expected": b.expected_balance, "reported": b.reported_balance, "difference": b.difference, "ref": ref_dict(b.source)} for b in res]}

    def image_similarity(doc_id_a: str, doc_id_b: str) -> dict:
        """Compare two documents' page images with a perceptual hash. Distance 0 = identical, <= 6 = near-identical, > 15 = different."""
        a, b = docs.get(doc_id_a), docs.get(doc_id_b)
        if not a or not b:
            return {"error": "unknown doc id"}
        pairs = []
        for pa, ha in enumerate(a.page_hashes, 1):
            for pb, hb in enumerate(b.page_hashes, 1):
                pairs.append({"page_a": pa, "page_b": pb, "hamming_distance": phash_distance(ha, hb)})
        best = min(pairs, key=lambda p: p["hamming_distance"]) if pairs else None
        return {"doc_a": doc_id_a, "doc_b": doc_id_b, "sha256_equal": a.sha256 == b.sha256, "best_match": best,
                "verdict": "identical" if a.sha256 == b.sha256 or (best and best["hamming_distance"] == 0) else "near-identical" if best and best["hamming_distance"] <= 6 else "different"}

    def date_crosscheck(doc_id_a: str, doc_id_b: str) -> dict:
        """Compare the month coverage of two documents (bank statement, dashboard or ledger) and list months present in only one of them."""
        ea = next((e for e in extractions if e.doc_id == doc_id_a), None)
        eb = next((e for e in extractions if e.doc_id == doc_id_b), None)
        if not ea or not eb:
            return {"error": "unknown doc id"}
        la, ma = checks._months_of(ea)
        lb, mb = checks._months_of(eb)
        return {"doc_a": doc_id_a, "period_a": la, "doc_b": doc_id_b, "period_b": lb, "overlap": sorted(ma & mb), "only_in_a": sorted(ma - mb), "only_in_b": sorted(mb - ma)}

    cat = {f.id: f for f in cashflow.figures}

    def recompute_figure(figure_id: str) -> dict:
        """Return how a memo figure was computed: value, unit, computation, the figures it derives from and its evidence refs."""
        f = cat.get(figure_id)
        if not f:
            return {"error": f"unknown figure {figure_id}", "known_prefixes": ["CF.", "DOC.", "TX.", "APP."]}
        return {"id": f.id, "label": f.label, "value": f.value, "unit": f.unit, "origin": f.origin, "computation": f.computation, "derived_from": f.derived_from,
                "n_refs": len(f.source_refs), "refs": [ref_dict(r) for r in f.source_refs[:5]]}

    # ---- context ----
    ref_block: dict[str, Any] = {}
    for b in tf.balance_checks:
        ref_block[b.row_id] = ref_dict(b.source)
    for f in tf.self_transfers + tf.round_trips:
        ref_block[f.row_id] = ref_dict(f.source)
    for r in tf.recurring_transfers:
        for rid, ref in zip(r.row_ids, r.source_refs):
            ref_block[rid] = ref_dict(ref)
    for d in case.documents:
        ref_block[d.doc_id] = {"doc_id": d.doc_id, "page": 1, "bbox": None, "snippet": d.filename}
    used_fig = [f for f in memo.figures]
    parts: list[types.Part] = [
        types.Part.from_text(text=case_facts(case)),
        types.Part.from_text(text=inventory_text(case)),
        types.Part.from_text(text="CREDIT MEMO UNDER REVIEW (figure values rendered; ids in brackets)\n" + render_memo_text(memo)),
        types.Part.from_text(text=catalog_text(used_fig + [f for f in cashflow.figures if f.id.startswith(("CF.", "APP.")) and f not in used_fig], max_rows=120)),
        types.Part.from_text(text=extraction_digest(extractions, docs, demo=case.is_demo)),
        types.Part.from_text(text="AUTOMATED CHECKS (deterministic, already run)\n" + digest),
        types.Part.from_text(text="EVIDENCE REFS you may copy (row_id or doc_id -> ref)\n" + "\n".join(f"{k}: {v}" for k, v in list(ref_block.items())[:80])),
        types.Part.from_text(text=priorities_text(priorities)),
        types.Part.from_text(text="Investigate now. Use the tools to verify. Then the reporting step will format objections."),
    ]
    if case.is_demo:
        parts.insert(0, types.Part.from_text(text=DEMO_DATASET_NOTE))
    inv = AgentSpec(name="challenger_investigator", instruction=prompts.CHALLENGER_INVESTIGATOR, prompt_version=prompts.PROMPT_VERSIONS["challenger_investigator"],
                    model=settings.model_pro, tools=[lookup_transactions, recompute_balance_chain, image_similarity, date_crosscheck, recompute_figure],
                    description="Adversarially investigates the memo with tools")
    wri = AgentSpec(name="challenger_writer", instruction=prompts.CHALLENGER_WRITER, prompt_version=prompts.PROMPT_VERSIONS["challenger_writer"],
                    model=settings.model_pro, output_schema=ChallengeDraft, description="Formats objections")
    rb_draft = ChallengeDraft(objections=rules, questions_checked=[f"Q{i}" for i in range(1, 13)], overall_assessment="Rule-based objections from the deterministic battery.")
    ctx = {**mock_context, "extra": {"digest": digest, "rule_based_challenge": rb_draft.model_dump(mode="json")}}
    extra = {"memo_version": memo.version, "prompt_versions": [inv.prompt_version, wri.prompt_version]}
    try:
        results = await run_sequence([inv, wri], parts, settings=settings, repo=repo, case_id=case.id, mock_context=ctx, cache_extra=extra)
    except CacheMiss:
        # cache_only replay: signed decisions change the feedback priorities (shared across workspaces), so the recorded
        # run no longer matches. Replay it with the priorities it was recorded with rather than failing the stage.
        if settings.resolved_llm_mode != "cache_only" or not priorities or priorities.n_decisions == 0:
            raise
        prio_idx = next(i for i, p in enumerate(parts) if (p.text or "").startswith("UNDERWRITER FEEDBACK PRIORITIES"))
        parts[prio_idx] = types.Part.from_text(text=priorities_text(None))
        results = await run_sequence([inv, wri], parts, settings=settings, repo=repo, case_id=case.id, mock_context=ctx, cache_extra=extra)
    notes = results[0].text
    draft = ChallengeDraft.model_validate(results[1].parsed)
    valid_docs = set(docs)
    for o in draft.objections:
        o.evidence_refs = [r for r in o.evidence_refs if r.doc_id in valid_docs]
        for r in o.evidence_refs:
            r.page = min(max(r.page, 1), max(1, docs[r.doc_id].pages))
    objections = merge_objections(draft.objections, rules)
    return ChallengeResult(case_id=case.id, model=wri.model, prompt_version=f"{inv.prompt_version}+{wri.prompt_version}", objections=objections,
                           questions_checked=draft.questions_checked, investigation_notes=notes, overall_assessment=draft.overall_assessment, tool_findings=tf)
