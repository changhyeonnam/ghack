"""Offline stand-in for Gemini, plugged into ADK as a model named "mock/<agent>".

It answers from the synthetic dataset's ground truth, so the whole pipeline (ADK runner, schema validation,
cashflow, challenger tools, UI) can be exercised without an API key. Non-synthetic uploads get minimal answers.
"""
from __future__ import annotations

import contextvars
import json
import re
from typing import Any, AsyncGenerator, Optional

from google.adk.models import BaseLlm, LLMRegistry
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from ..schemas import DocType

# Set by the runner before each call: {"agent": str, "case": Case-like dict, "docs": [...], "gt": GroundTruth, "extra": {...}}
MOCK_CONTEXT: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("ledgerlens_mock_context", default={})


def _bbox(b: Any) -> Optional[dict[str, int]]:
    if not b or len(b) != 4:
        return None
    return {"ymin": int(b[0]), "xmin": int(b[1]), "ymax": int(b[2]), "xmax": int(b[3])}


def _ref(doc_id: str, page: int = 1, bbox: Any = None, snippet: Optional[str] = None) -> dict[str, Any]:
    return {"doc_id": doc_id, "page": page, "bbox": _bbox(bbox), "snippet": snippet}


class MockLlm(BaseLlm):
    model: str = "mock/generic"

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"mock/.*"]

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        ctx = MOCK_CONTEXT.get()
        agent = self.model.split("/", 1)[1]
        payload = build_mock_output(agent, ctx)
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part.from_text(text=text)]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=0, candidates_token_count=0, total_token_count=0),
        )


LLMRegistry.register(MockLlm)


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------
def build_mock_output(agent: str, ctx: dict[str, Any]) -> Any:
    if agent == "intake":
        return _mock_intake(ctx)
    if agent.startswith("extractor"):
        return _mock_extractor(ctx)
    if agent == "analyst":
        return _mock_analyst(ctx)
    if agent == "challenger_investigator":
        return _mock_investigation(ctx)
    if agent == "challenger_writer":
        rb = dict(ctx.get("extra", {}).get("rule_based_challenge", {"objections": [], "questions_checked": [f"Q{i}" for i in range(1, 13)]}))
        n = len(rb.get("objections", []))
        crit = sum(1 for o in rb.get("objections", []) if o.get("severity") == "critical")
        rb["overall_assessment"] = ("The deterministic checks found no inconsistencies; the memo's figures reconcile with the documents." if n == 0 else
                                    f"{n} objections stand, {crit} of them critical. The memo's revenue base and document integrity need the underwriter's attention before approval; "
                                    "the figures themselves are all sourced.")
        return rb
    if agent == "explainer":
        return _mock_explainer(ctx)
    if agent == "baseline":
        return _mock_baseline(ctx)
    return {}


def _mock_intake(ctx: dict[str, Any]) -> dict[str, Any]:
    case = ctx["case"]
    gt = ctx.get("gt")
    docs = []
    names: set[str] = {case["business_name"]}
    for d in ctx["docs"]:
        dtype, lang = DocType.other.value, re.split(r"[+/,; ]+", case.get("language") or "en")[0]
        manifest = gt.find_case_for_filename(d["filename"], ctx.get("synthetic_case_id")) if gt else None
        if manifest:
            entry = gt.doc_entry(manifest, d["filename"])
            dtype = entry["doc_type"] if entry else dtype
            names.add(manifest.get("business_name", ""))
        else:
            fn = d["filename"].lower()
            dtype = ("bank_statement" if fn.endswith(".pdf") else "seller_dashboard" if "dashboard" in fn else "handwritten_ledger" if "ledger" in fn
                     else "premises_photo" if "premises" in fn else "logistics_receipt" if "ghn" in fn or "jnt" in fn else "receipt")
        flags = ["synthetic_watermark"] + (["handwritten"] if dtype == "handwritten_ledger" else [])
        docs.append({"doc_id": d["doc_id"], "doc_type": dtype, "language": lang, "currency": case.get("currency"), "quality_flags": flags,
                     "confidence": 0.9, "summary": f"Mock classification of {d['filename']} as {dtype}."})
    return {"documents": docs, "business_name_candidates": sorted(n for n in names if n), "location_candidates": [case.get("country", "")], "notes": "mock"}


def _mock_extractor(ctx: dict[str, Any]) -> dict[str, Any]:
    d = ctx["doc"]
    doc_id = d["doc_id"]
    gt = ctx.get("gt")
    dtype = ctx.get("doc_type", "other")
    manifest = gt.find_case_for_filename(d["filename"], ctx.get("synthetic_case_id")) if gt else None
    rec = None
    if manifest:
        _, rec = gt.ground_truth_for(manifest, d["filename"])
    if dtype == "bank_statement":
        if not rec:
            return {"currency": ctx["case"].get("currency", "USD"), "period_start": "2026-01-01", "period_end": "2026-06-30", "transactions": []}
        txs = []
        for t in rec["transactions"]:
            txs.append({"row_id": t["row_id"], "date": t["date"], "description": t["description"], "counterparty": t.get("counterparty"),
                        "debit": float(t.get("debit") or 0), "credit": float(t.get("credit") or 0), "balance_after": t.get("balance_after"),
                        "source": _ref(doc_id, t.get("page", 1), t.get("bbox"), t["description"])})
        ob = rec.get("opening_balance")
        cb = rec.get("closing_balance")
        return {"bank_name": rec.get("bank_name"), "account_holder": rec.get("account_holder"), "account_number_masked": rec.get("account_number_masked"),
                "address": rec.get("address"), "currency": rec["currency"], "period_start": rec["period_start"], "period_end": rec["period_end"],
                "opening_balance": {"value": ob, "source": _ref(doc_id, 1, rec.get("opening_balance_bbox"), "Opening balance")} if ob is not None else None,
                "closing_balance": {"value": cb, "source": _ref(doc_id, rec.get("pages", 1), rec.get("closing_balance_bbox"), "Closing balance")} if cb is not None else None,
                "transactions": txs}
    if dtype == "seller_dashboard":
        if not rec:
            return {"metrics": []}
        labels = {"gross_sales": "Gross sales", "orders": "Orders", "payout": "Total payout", "followers": "Followers", "rating": "Shop rating",
                  "visitors": "Visitors", "cod_value": "COD orders value", "cancelled_orders": "Cancelled orders", "returns": "Returns", "ad_spend": "Ad spend"}
        metrics = []
        for k, v in rec.get("metrics", {}).items():
            key = k if k in ("gross_sales", "net_sales", "orders", "payout", "followers", "rating", "reviews", "visitors", "conversion_rate", "cancelled_orders", "returns", "ad_spend") else "other"
            metrics.append({"key": key, "label": labels.get(k, k), "value": float(v), "period_label": f"{rec.get('period_start')} - {rec.get('period_end')}",
                            "source": _ref(doc_id, 1, (rec.get("bboxes") or {}).get(k), f"{labels.get(k, k)} {v}")})
        return {"platform": rec.get("platform"), "shop_name": rec.get("shop_name"), "period_start": rec.get("period_start"), "period_end": rec.get("period_end"),
                "data_as_of": rec.get("data_as_of"), "currency": ctx["case"].get("currency"), "metrics": metrics}
    if dtype in ("receipt", "logistics_receipt"):
        if not rec:
            return {"direction": "unknown", "items": [], "handwritten": False}
        items = [{"description": it["description"], "amount": float(it["amount"]), "source": _ref(doc_id, 1, it.get("bbox"), it["description"])} for it in rec.get("items", [])]
        return {"merchant": rec.get("merchant"), "date": rec.get("date"), "receipt_number": rec.get("receipt_number"), "currency": rec.get("currency"),
                "total": {"value": float(rec["total"]), "source": _ref(doc_id, 1, rec.get("total_bbox"), f"TOTAL {rec['total']}")} if rec.get("total") is not None else None,
                "items": items, "payment_method": rec.get("payment_method"), "direction": _direction(rec.get("direction")), "handwritten": bool(rec.get("handwritten"))}
    if dtype == "handwritten_ledger":
        if not rec:
            return {"entries": []}
        entries = [{"row_id": e["row_id"], "date": e["date"], "description": e["description"], "amount": float(e["amount"]), "kind": e["kind"],
                    "source": _ref(doc_id, 1, e.get("bbox"), e["description"])} for e in rec.get("entries", []) if e.get("kind") in ("income", "expense")]
        return {"business_name_header": rec.get("business_name_header"), "address_header": rec.get("address_header"), "currency": rec.get("currency") or ctx["case"].get("currency"),
                "period_label": rec.get("period_label"), "entries": entries}
    if dtype == "premises_photo":
        name = (manifest or {}).get("business_name", ctx["case"].get("business_name"))
        return {"signage_text": name, "business_type_guess": ctx["case"].get("sector"), "apparent_size": "small", "inventory_level": "moderate",
                "observations": [{"text": f"Sign reads '{name}'.", "source": _ref(doc_id, 1, [40, 100, 160, 900], name)},
                                 {"text": "Stylised illustration with a SYNTHETIC watermark; not a photograph.", "source": _ref(doc_id, 1, [900, 600, 990, 990], "SYNTHETIC")}]}
    return {}


def _direction(v: Any) -> str:
    v = (v or "").lower()
    if v in ("purchase", "expense", "cost", "paid"):
        return "purchase"
    if v in ("sale", "income", "revenue", "received"):
        return "sale"
    return "unknown"


def _mock_analyst(ctx: dict[str, Any]) -> dict[str, Any]:
    """Offline memo in the register of a real credit memo. Figures are referenced by catalog id only."""
    case = ctx["case"]
    ex = ctx.get("extra", {})
    ids = set(ex.get("catalog_ids", {}))
    sg = ex.get("signals", {})
    has = lambda i: i in ids  # noqa: E731
    fig = lambda i: "{fig:%s}" % i  # noqa: E731
    name, sector, country = case["business_name"], case.get("sector") or "small business", case.get("country") or ""
    cty = {"ID": "Indonesia", "VN": "Vietnam", "PH": "the Philippines"}.get(country, country)
    expected = ex.get("expected_outcome") or "hold"
    months = sorted(i for i in ids if i.startswith("CF.m.") and i.endswith(".business_inflow"))
    debt = [d for d in sg.get("debt", []) if d[2]]
    recurring_ids = sorted(i for i in ids if i.startswith("CF.recurring.") and i.endswith(".amount"))
    sections = []

    # Business overview
    art = "an" if sector[:1].lower() in "aeiou" else "a"
    p = [f"{name} is {art} {sector} operator in {cty}" + (f", banking with {sg['bank']}" if sg.get("bank") else "") +
         (f" under the account name {sg['holder']}" if sg.get("holder") else "") + "."]
    if has("APP.requested_amount"):
        p.append(f"The applicant requests {fig('APP.requested_amount')} of working capital. The file consists of a bank statement covering {sg.get('period', 'the review period')}"
                 + (", monthly marketplace dashboard captures" if sg.get("has_dashboards") else "") + (", handwritten daily ledger pages" if sg.get("has_ledger") else "")
                 + (f", supplier receipts" if sg.get("n_receipts") else "") + (" and photographs of the premises." if sg.get("has_premises") else "."))
    sections.append({"heading": "Business overview", "paragraphs": p, "figure_ids": [i for i in ["APP.requested_amount"] if has(i)]})

    # Cash flow
    p = []
    if has("CF.avg_monthly_business_inflow"):
        p.append(f"Across {fig('CF.months_covered')} months of statement activity, business inflow averaged {fig('CF.avg_monthly_business_inflow')} per month against "
                 f"outflow of {fig('CF.avg_monthly_outflow')}, leaving net cash of {fig('CF.avg_monthly_net')} per month. "
                 + ("Net cash is negative on average, so the account is being supported by sources other than trading." if sg.get("avg_net", 0) < 0 else
                    "The account retains a positive cash surplus in a typical month."))
        trend = sg.get("trend", 0)
        p.append(f"Business inflow is trending at {fig('CF.revenue_trend_pct')} per month"
                 + (", a steady upward path." if trend > 1 else ", broadly flat." if trend > -1 else ", a declining path that needs explanation.")
                 + f" Month-to-month volatility is {fig('CF.inflow_volatility_cv')} (coefficient of variation), which is "
                 + ("low for a cash business." if sg.get("cv", 0) < 0.2 else "moderate." if sg.get("cv", 0) < 0.4 else "high and argues for a shorter tenor."))
        if sg.get("months_missing"):
            p.append(f"{fig('CF.months_missing_count')} months inside the stated statement period contain no transactions ({', '.join(sg['months_missing'])}); the averages above are computed on the remaining months only and overstate coverage.")
    else:
        p.append("No bank statement could be extracted, so no cash-flow model was built.")
    sections.append({"heading": "Cash flow", "paragraphs": p,
                     "figure_ids": [i for i in ["CF.months_covered", "CF.avg_monthly_business_inflow", "CF.avg_monthly_outflow", "CF.avg_monthly_net", "CF.revenue_trend_pct", "CF.inflow_volatility_cv", "CF.months_missing_count"] if has(i)] + months[:6]})

    # Revenue quality
    p = []
    if sg.get("n_self"):
        p.append(f"{fig('CF.self_transfer_count')} credits totalling {fig('CF.self_transfer_total')} were sent from an account in the applicant's own name at another bank. "
                 "They are excluded from business inflow above; the applicant should be asked what the other account is used for.")
    if sg.get("n_round"):
        p.append(f"Credits of {fig('CF.round_trip_total')} were returned to the same counterparty within two weeks and are treated as round-trips, not revenue.")
    if sg.get("has_dashboards"):
        p.append(f"Marketplace dashboards report gross sales of {fig('CF.dashboard_gross_sales_total')} and payouts of {fig('CF.dashboard_payout_total')}; the statement shows {fig('CF.platform_payout_total')} of platform payouts. "
                 "The dashboards corroborate the bank figures and are not added on top of them.")
    if sg.get("has_ledger"):
        p.append(f"The handwritten ledger records cash income of {fig('CF.ledger_income_total')}, while cash deposits into the account total {fig('CF.cash_deposit_total')}. "
                 "The deposits appear to be the ledger's cash banked weekly, so income is counted once, from the bank side; the ledger is used as corroboration.")
    if sg.get("n_receipts"):
        p.append(f"{fig('CF.receipts_count')} supplier receipts evidence purchases of {fig('CF.receipts_purchases_total')}, consistent with a trading business of this size.")
    p.append(f"{fig('CF.end_of_month_concentration')} of inflow lands in the last five days of the month"
             + (", which is unusual for daily retail and should be explained." if sg.get("eom", 0) >= 0.5 else ", in line with daily retail." if sg.get("eom", 0) < 0.3 else ", somewhat concentrated."))
    sections.append({"heading": "Revenue quality and concentration", "paragraphs": p,
                     "figure_ids": [i for i in ["CF.self_transfer_count", "CF.self_transfer_total", "CF.round_trip_total", "CF.dashboard_gross_sales_total", "CF.dashboard_payout_total", "CF.platform_payout_total",
                                                 "CF.ledger_income_total", "CF.cash_deposit_total", "CF.receipts_count", "CF.receipts_purchases_total", "CF.end_of_month_concentration"] if has(i)]})

    # Obligations
    p = []
    if debt:
        names = ", ".join(d[0] for d in debt[:3])
        p.append(f"The statement shows recurring debits that look like loan servicing: {names}. Together they absorb {fig('CF.recurring_debt_service_monthly')} per month. "
                 "None of these facilities was disclosed in the application; the balances and remaining tenors must be confirmed before any new exposure is taken.")
    else:
        p.append("No recurring transfers consistent with existing loan repayments were identified in the statement. Rent and utilities are paid regularly and are not treated as debt.")
    sections.append({"heading": "Obligations and leverage", "paragraphs": p, "figure_ids": [i for i in ["CF.recurring_debt_service_monthly"] if has(i)] + recurring_ids[:4]})

    # Document quality
    p = []
    if sg.get("n_breaks"):
        p.append("The running balance on the statement does not reconcile at every row; the Challenger's balance test identifies the exact rows. Until the bank confirms the statement, figures derived from it carry extra uncertainty.")
    else:
        p.append("The running balance reconciles row by row across the statement, which supports the integrity of the document.")
    if sg.get("months_missing"):
        p.append("Statement coverage is incomplete (see Cash flow). Full months should be requested directly from the bank.")
    p.append("All documents carry a visible synthetic-data watermark; this file is a demonstration case.")
    sections.append({"heading": "Document quality and coverage", "paragraphs": p, "figure_ids": [i for i in ["CF.months_missing_count"] if has(i)]})

    # Recommendation
    cap_ok = has("CF.suggested_capacity") and sg.get("capacity", 0) > 0
    p = []
    if cap_ok:
        p.append(f"Illustrative repayment capacity, taken as three months of net business cash, is {fig('CF.suggested_capacity')}"
                 + (f", against a request of {fig('APP.requested_amount')} ({fig('CF.request_to_capacity')} of capacity)." if has("CF.request_to_capacity") else "."))
    else:
        p.append("Net business cash is not positive on the evidence provided, so no illustrative repayment capacity can be stated.")
    rec_text = {"approve": "The evidence supports approval at the requested amount.",
                "approve_with_conditions": "Approval is supported subject to the conditions below, which address the unexplained transfers and undisclosed obligations.",
                "hold": "The file should be held pending the applicant's explanations.",
                "reject": "The evidence does not support the request.",
                "request_more_documents": "The file is incomplete; the missing months and originals should be obtained before a decision."}[expected]
    p.append(rec_text + " The decision rests with the underwriter; this memo organises the evidence and does not produce a credit score.")
    sections.append({"heading": "Recommendation", "paragraphs": p, "figure_ids": [i for i in ["CF.suggested_capacity", "APP.requested_amount", "CF.request_to_capacity"] if has(i)]})

    strengths, concerns, conditions = [], [], []
    if sg.get("trend", 0) > 0 and has("CF.revenue_trend_pct"):
        strengths.append(f"Business inflow is growing ({fig('CF.revenue_trend_pct')} per month).")
    if sg.get("cv", 1) < 0.25 and has("CF.inflow_volatility_cv"):
        strengths.append(f"Low inflow volatility ({fig('CF.inflow_volatility_cv')}).")
    if not sg.get("n_breaks"):
        strengths.append("Running balance reconciles on every statement row.")
    if sg.get("n_receipts"):
        strengths.append("Supplier receipts corroborate the purchasing pattern seen in the statement.")
    if sg.get("has_dashboards"):
        strengths.append("Marketplace payouts in the statement match the seller dashboards.")
    if sg.get("n_self"):
        concerns.append(f"Own-account transfers of {fig('CF.self_transfer_total')} were presented inside the inflow.")
        conditions.append("Provide statements for the other account in the applicant's name and explain the transfers.")
    if sg.get("n_round"):
        concerns.append(f"Round-trip credits of {fig('CF.round_trip_total')} inflate gross inflow.")
        conditions.append("Written explanation of the returned transfer and its counterparty.")
    if debt:
        concerns.append(f"Undisclosed recurring repayments of about {fig('CF.recurring_debt_service_monthly')} per month.")
        conditions.append("Disclose all existing credit facilities (lender, balance, instalment, remaining tenor).")
    if sg.get("n_breaks"):
        concerns.append("Running balance does not reconcile at every row; statement integrity is in question.")
        conditions.append("Obtain the statement directly from the bank or via API for the full period.")
    if sg.get("months_missing"):
        concerns.append(f"Months without statement activity: {', '.join(sg['months_missing'])}.")
        conditions.append("Provide the missing statement months.")
    if sg.get("has_dashboards"):
        concerns.append("Dashboard sales and bank payouts describe the same revenue; they must not be summed.")
    if not concerns:
        concerns.append("No material concerns identified from the documents provided; the Challenger review should confirm.")
    if expected not in ("approve_with_conditions", "hold"):
        conditions = conditions if expected == "request_more_documents" else []
    return {
        "headline": {"approve": f"{name}: approval supported by a consistent, fully sourced cash-flow record",
                     "approve_with_conditions": f"{name}: approval supported once own-account transfers and undisclosed repayments are resolved",
                     "hold": f"{name}: hold pending the applicant's explanations",
                     "reject": f"{name}: the verified evidence does not support the request",
                     "request_more_documents": f"{name}: file incomplete; missing statement months and duplicated pages must be resolved first"}[expected],
        "sections": sections,
        "key_figure_ids": [i for i in ("APP.requested_amount", "CF.avg_monthly_business_inflow", "CF.avg_monthly_net", "CF.revenue_trend_pct", "CF.recurring_debt_service_monthly", "CF.suggested_capacity") if has(i)],
        "strengths": strengths[:5], "concerns": concerns[:6], "recommendation": expected, "conditions": conditions[:5],
        "rationale": ("Figures are drawn exclusively from the deterministic cash-flow model built on the extracted statement rows; each one links to its source. "
                      + ("The adjustments for own-account and round-trip transfers materially reduce the revenue base, and the undisclosed repayments reduce capacity, hence conditions." if (sg.get("n_self") or debt) else
                         "The statement is internally consistent and the trading pattern matches the documents supplied.")),
    }


def _mock_explainer(ctx: dict[str, Any]) -> dict[str, Any]:
    ex = ctx.get("extra", {})
    lang = ex.get("language", "en")
    outcome = ex.get("outcome", "hold")
    name = ctx["case"]["business_name"]
    T = {
        "en": {
            "subject": {"approve": "Your loan application has been approved", "approve_with_conditions": "Your loan application: approved with a few conditions",
                        "hold": "Your loan application is on hold", "reject": "Your loan application: our decision", "request_more_documents": "We need a few more documents"},
            "open": f"Dear {name},\n\nThank you for applying with us and for sharing your bank statement and business records. We have reviewed them carefully.",
            "body": {"approve": "We are pleased to tell you that your application has been approved. Your records show steady sales and regular, healthy cash flow, and the documents you sent were complete and consistent.",
                     "approve_with_conditions": "Your application can be approved once a few points are cleared up. Some of the money coming into your account came from your own other account or was sent back to the same person soon after, so we could not count it as sales. We also noticed regular monthly payments that look like an existing loan, which we need you to confirm.",
                     "hold": "We have paused your application for now. Some items in your statement need an explanation before we can continue, and we would like to go through them with you.",
                     "reject": "After reviewing your records we are not able to approve the application at this time. The sales we could verify do not yet support the amount requested, and some documents did not match each other.",
                     "request_more_documents": "We cannot complete the review yet because some months of your bank statement are missing and some pages appear more than once. Once we receive the missing documents we will continue immediately."},
            "close": "If anything here is unclear, please reply to this message or visit a branch; we are happy to walk you through it.\n\nWith kind regards,\nThe credit team",
            "steps": {"approve": ["Sign the offer letter we will send separately.", "Keep using the same bank account for your sales so future reviews are quick."],
                      "approve_with_conditions": ["Send the statement of your other account for the same months.", "Tell us about any existing loan or pay-later plan (lender, monthly amount, remaining months).", "Explain the transfer that was sent back to the same person."],
                      "hold": ["Reply with explanations for the transfers we listed.", "Send any document that supports your answer."],
                      "reject": ["You may apply again after three months of statements showing regular sales.", "Ask us for the list of documents that would strengthen a new application."],
                      "request_more_documents": ["Send the missing statement months, downloaded directly from your banking app.", "Send original photos of each ledger page, one photo per page."]},
        },
        "id": {
            "subject": {"approve": "Pengajuan pinjaman Anda disetujui", "approve_with_conditions": "Pengajuan pinjaman Anda: disetujui dengan beberapa syarat",
                        "hold": "Pengajuan pinjaman Anda ditunda sementara", "reject": "Pengajuan pinjaman Anda: keputusan kami", "request_more_documents": "Kami memerlukan beberapa dokumen tambahan"},
            "open": f"Yth. {name},\n\nTerima kasih telah mengajukan pinjaman dan mengirimkan rekening koran serta catatan usaha Anda. Kami telah memeriksanya dengan saksama.",
            "body": {"approve": "Dengan senang hati kami sampaikan bahwa pengajuan Anda disetujui. Catatan Anda menunjukkan penjualan yang stabil dan arus kas yang sehat, dan dokumen yang Anda kirim lengkap serta konsisten.",
                     "approve_with_conditions": "Pengajuan Anda dapat disetujui setelah beberapa hal diperjelas. Sebagian dana masuk berasal dari rekening Anda sendiri di bank lain atau dikirim kembali ke orang yang sama tidak lama kemudian, sehingga tidak dapat kami hitung sebagai penjualan. Kami juga melihat pembayaran bulanan rutin yang tampak seperti cicilan pinjaman yang perlu Anda konfirmasi.",
                     "hold": "Kami menunda pengajuan Anda untuk sementara. Beberapa transaksi di rekening koran perlu penjelasan sebelum kami dapat melanjutkan.",
                     "reject": "Setelah memeriksa catatan Anda, kami belum dapat menyetujui pengajuan ini. Penjualan yang dapat kami verifikasi belum mendukung jumlah yang diminta, dan beberapa dokumen tidak saling cocok.",
                     "request_more_documents": "Kami belum dapat menyelesaikan penilaian karena beberapa bulan rekening koran belum ada dan beberapa halaman muncul lebih dari sekali. Begitu dokumen diterima, kami akan segera melanjutkan."},
            "close": "Jika ada yang kurang jelas, silakan balas pesan ini atau kunjungi kantor cabang kami.\n\nHormat kami,\nTim Kredit",
            "steps": {"approve": ["Tandatangani surat penawaran yang akan kami kirim terpisah.", "Tetap gunakan rekening yang sama untuk penjualan agar penilaian berikutnya cepat."],
                      "approve_with_conditions": ["Kirim rekening koran rekening Anda yang lain untuk bulan yang sama.", "Beri tahu kami pinjaman atau paylater yang masih berjalan (pemberi pinjaman, cicilan per bulan, sisa tenor).", "Jelaskan transfer yang dikirim kembali ke orang yang sama."],
                      "hold": ["Balas dengan penjelasan atas transfer yang kami sebutkan.", "Kirim dokumen pendukung bila ada."],
                      "reject": ["Anda dapat mengajukan kembali setelah tiga bulan rekening koran dengan penjualan rutin.", "Minta daftar dokumen yang akan memperkuat pengajuan baru."],
                      "request_more_documents": ["Kirim bulan rekening koran yang kurang, diunduh langsung dari aplikasi bank.", "Kirim foto asli setiap halaman buku catatan, satu foto per halaman."]},
        },
        "vi": {
            "subject": {"approve": "Hồ sơ vay của bạn đã được duyệt", "approve_with_conditions": "Hồ sơ vay của bạn: được duyệt kèm một số điều kiện",
                        "hold": "Hồ sơ vay của bạn đang tạm dừng", "reject": "Hồ sơ vay của bạn: quyết định của chúng tôi", "request_more_documents": "Chúng tôi cần thêm một vài giấy tờ"},
            "open": f"Kính gửi {name},\n\nCảm ơn bạn đã nộp hồ sơ và chia sẻ sao kê ngân hàng cùng số liệu kinh doanh. Chúng tôi đã xem xét kỹ lưỡng.",
            "body": {"approve": "Chúng tôi vui mừng thông báo hồ sơ của bạn đã được duyệt. Số liệu cho thấy doanh thu ổn định và dòng tiền đều đặn; giấy tờ đầy đủ và nhất quán.",
                     "approve_with_conditions": "Hồ sơ của bạn có thể được duyệt sau khi làm rõ vài điểm. Một phần tiền vào tài khoản đến từ tài khoản khác đứng tên bạn, hoặc được chuyển trả lại cho cùng một người ngay sau đó, nên chúng tôi không thể tính là doanh thu. Chúng tôi cũng thấy các khoản thanh toán hằng tháng giống như một khoản vay đang có, cần bạn xác nhận.",
                     "hold": "Chúng tôi tạm dừng hồ sơ của bạn. Một số giao dịch trong sao kê cần được giải thích trước khi tiếp tục.",
                     "reject": "Sau khi xem xét, chúng tôi chưa thể duyệt hồ sơ lần này. Doanh thu có thể xác minh chưa đủ cho số tiền đề nghị, và một số giấy tờ không khớp nhau.",
                     "request_more_documents": "Chúng tôi chưa thể hoàn tất thẩm định vì thiếu một số tháng sao kê và có trang xuất hiện nhiều lần. Ngay khi nhận đủ giấy tờ, chúng tôi sẽ tiếp tục."},
            "close": "Nếu có điểm nào chưa rõ, bạn vui lòng phản hồi tin nhắn này hoặc đến chi nhánh gần nhất.\n\nTrân trọng,\nBộ phận Tín dụng",
            "steps": {"approve": ["Ký thư chào vay chúng tôi gửi riêng.", "Tiếp tục dùng cùng tài khoản để nhận doanh thu, giúp các lần thẩm định sau nhanh hơn."],
                      "approve_with_conditions": ["Gửi sao kê của tài khoản còn lại đứng tên bạn cho cùng các tháng.", "Cho chúng tôi biết các khoản vay hoặc trả sau đang có (bên cho vay, số tiền hằng tháng, số kỳ còn lại).", "Giải thích khoản chuyển tiền đã được trả lại cho cùng một người."],
                      "hold": ["Phản hồi kèm giải thích cho các giao dịch đã nêu.", "Gửi giấy tờ hỗ trợ nếu có."],
                      "reject": ["Bạn có thể nộp lại sau ba tháng sao kê có doanh thu đều đặn.", "Liên hệ để nhận danh sách giấy tờ giúp hồ sơ mới mạnh hơn."],
                      "request_more_documents": ["Gửi các tháng sao kê còn thiếu, tải trực tiếp từ ứng dụng ngân hàng.", "Gửi ảnh gốc từng trang sổ ghi chép, mỗi trang một ảnh."]},
        },
        "tl": {
            "subject": {"approve": "Aprubado na ang inyong aplikasyon sa pautang", "approve_with_conditions": "Ang inyong aplikasyon: aprubado na may ilang kondisyon",
                        "hold": "Pansamantalang nakabinbin ang inyong aplikasyon", "reject": "Ang inyong aplikasyon: ang aming desisyon", "request_more_documents": "Kailangan namin ng ilang karagdagang dokumento"},
            "open": f"Mahal na {name},\n\nSalamat sa pag-apply at sa pagbabahagi ng inyong bank statement at mga tala ng negosyo. Maingat namin itong sinuri.",
            "body": {"approve": "Ikinagagalak naming ipaalam na aprubado ang inyong aplikasyon. Ipinapakita ng inyong mga tala ang matatag na benta at regular na daloy ng pera, at kumpleto at magkakatugma ang mga dokumento.",
                     "approve_with_conditions": "Maaaring aprubahan ang aplikasyon kapag nalinaw ang ilang bagay. May perang pumasok na galing sa sarili ninyong ibang account o ibinalik sa parehong tao pagkaraan ng ilang araw, kaya hindi namin ito mabilang bilang benta. Napansin din namin ang regular na buwanang bayad na mukhang kasalukuyang utang na kailangan ninyong kumpirmahin.",
                     "hold": "Pansamantala naming itinigil ang aplikasyon. May mga transaksyon sa statement na kailangang ipaliwanag bago kami magpatuloy.",
                     "reject": "Matapos suriin ang inyong mga tala, hindi pa namin maaprubahan ang aplikasyon sa ngayon. Hindi pa sapat ang benta na na-verify namin para sa hinihinging halaga, at may mga dokumentong hindi magkatugma.",
                     "request_more_documents": "Hindi pa namin matapos ang pagsusuri dahil kulang ang ilang buwan ng bank statement at may mga pahinang lumitaw nang higit sa isang beses. Sa sandaling matanggap ang mga dokumento, agad kaming magpapatuloy."},
            "close": "Kung may hindi malinaw, mangyaring tumugon sa mensaheng ito o bumisita sa aming sangay.\n\nLubos na gumagalang,\nAng Credit Team",
            "steps": {"approve": ["Pirmahan ang offer letter na ipapadala namin nang hiwalay.", "Patuloy na gamitin ang parehong account para sa benta upang mabilis ang susunod na pagsusuri."],
                      "approve_with_conditions": ["Ipadala ang statement ng inyong ibang account para sa parehong mga buwan.", "Sabihin sa amin ang anumang kasalukuyang utang o pay-later (nagpautang, buwanang bayad, natitirang buwan).", "Ipaliwanag ang transfer na ibinalik sa parehong tao."],
                      "hold": ["Tumugon kasama ang paliwanag sa mga transfer na aming binanggit.", "Ipadala ang anumang dokumentong sumusuporta sa inyong sagot."],
                      "reject": ["Maaari kayong mag-apply muli pagkatapos ng tatlong buwan ng statement na may regular na benta.", "Hingin sa amin ang listahan ng mga dokumentong magpapalakas sa bagong aplikasyon."],
                      "request_more_documents": ["Ipadala ang kulang na mga buwan ng statement, direktang na-download mula sa banking app.", "Ipadala ang orihinal na larawan ng bawat pahina ng ledger, isang larawan bawat pahina."]},
        },
    }
    t = T.get(lang, T["en"])
    body = f"{t['open']}\n\n{t['body'][outcome]}\n\n{t['close']}"
    return {"language": lang, "subject": t["subject"][outcome], "body": body, "next_steps": t["steps"][outcome]}


def _mock_investigation(ctx: dict[str, Any]) -> str:
    """Checklist-style notes built from the deterministic digest, in the Challenger's voice."""
    rb = ctx.get("extra", {}).get("rule_based_challenge", {})
    by_q: dict[str, list[dict]] = {}
    for o in rb.get("objections", []):
        by_q.setdefault(o["question_id"], []).append(o)
    titles = {"Q1": "Double counting across sources", "Q2": "Seasonality vs one-off inflows", "Q3": "Self-transfers and round-trips", "Q4": "Duplicate or reused images",
              "Q5": "Period coverage", "Q6": "Balance continuity", "Q7": "Undisclosed debt service", "Q8": "Premises vs claimed scale", "Q9": "Every number sourced",
              "Q10": "Month-end concentration", "Q11": "Entity consistency", "Q12": "Language and currency vs location"}
    lines = ["CHALLENGER INVESTIGATION (offline mode: deterministic checks only, no model judgement)"]
    for q in [f"Q{i}" for i in range(1, 13)]:
        objs = by_q.get(q, [])
        if objs:
            lines.append(f"\n{q} {titles[q]}: OBJECTION ({len(objs)})")
            for o in objs:
                lines.append(f"  - [{o['severity']}] {o['title']}. Evidence: {o.get('tool_evidence') or 'see claim'}.")
        else:
            lines.append(f"\n{q} {titles[q]}: PASS (no deterministic finding; model review pending in live mode)")
    lines.append("\nOverall: " + rb.get("overall_assessment", ""))
    return "\n".join(lines)


def _mock_baseline(ctx: dict[str, Any]) -> dict[str, Any]:
    return {"headline": "Baseline mock memo", "sections": [{"heading": "Cash flow", "paragraphs": ["Revenue looks healthy at about 60,000,000 per month."]}],
            "figures": [{"label": "Monthly revenue", "value": 60000000, "source_refs": []}], "recommendation": "approve",
            "concerns": [{"title": "None", "claim": "No concerns found by the single prompt.", "severity": "low"}]}


_ = re  # keep import for future pattern use
