"""Shared data contract for LedgerLens.

Every model here is either (a) a structured-output schema handed to a Gemini
agent, or (b) a persisted record. The single most important rule of the
system is encoded in ``Figure``: a number may only appear in a credit memo if
it carries at least one ``SourceRef`` pointing back to a document location.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Evidence primitives
# ---------------------------------------------------------------------------
class DocType(str, Enum):
    bank_statement = "bank_statement"
    seller_dashboard = "seller_dashboard"
    receipt = "receipt"
    handwritten_ledger = "handwritten_ledger"
    premises_photo = "premises_photo"
    logistics_receipt = "logistics_receipt"
    other = "other"


class BBox(BaseModel):
    """Bounding box in Gemini's normalized convention: 0-1000, [ymin, xmin, ymax, xmax]."""

    ymin: int = Field(ge=0, le=1000)
    xmin: int = Field(ge=0, le=1000)
    ymax: int = Field(ge=0, le=1000)
    xmax: int = Field(ge=0, le=1000)


class SourceRef(BaseModel):
    """Where a value was read from. Page is 1-based."""

    doc_id: str
    page: int = 1
    bbox: Optional[BBox] = None
    snippet: Optional[str] = Field(
        default=None, description="Verbatim text visible at this location, for human verification."
    )


FigureUnit = Literal["currency", "count", "ratio", "percent", "months", "days", "score"]


class Figure(BaseModel):
    """A number that is allowed to appear in a memo. No refs, no figure."""

    id: str
    label: str
    value: float
    unit: FigureUnit = "currency"
    currency: Optional[str] = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    computation: Optional[str] = Field(default=None, description="Formula or method, when derived.")
    derived_from: list[str] = Field(default_factory=list, description="Ids of figures this one is computed from.")
    origin: Literal["document", "computed", "application"] = "document"

    def is_sourced(self) -> bool:
        if self.origin == "application":
            return True
        return bool(self.source_refs) or (self.origin == "computed" and bool(self.derived_from))


# ---------------------------------------------------------------------------
# Intake agent output
# ---------------------------------------------------------------------------
class QualityFlag(str, Enum):
    blurry = "blurry"
    cropped = "cropped"
    low_resolution = "low_resolution"
    glare = "glare"
    partial_page = "partial_page"
    handwritten = "handwritten"
    duplicate_suspected = "duplicate_suspected"
    synthetic_watermark = "synthetic_watermark"
    unreadable = "unreadable"
    other = "other"


class DocumentIntake(BaseModel):
    doc_id: str
    doc_type: DocType
    language: str = Field(description="ISO 639-1 code of the dominant language, e.g. 'id', 'vi', 'tl', 'en'.")
    currency: Optional[str] = Field(default=None, description="ISO 4217 code if visible, e.g. IDR, VND, PHP.")
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(description="One sentence describing what the document is.")


class IntakeResult(BaseModel):
    documents: list[DocumentIntake]
    business_name_candidates: list[str] = Field(default_factory=list)
    location_candidates: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Extractor agent outputs (one schema per document type)
# ---------------------------------------------------------------------------
class MoneyField(BaseModel):
    value: float
    source: SourceRef


class Transaction(BaseModel):
    row_id: str = Field(description="Sequential id in reading order, e.g. T0001.")
    date: str = Field(description="ISO date YYYY-MM-DD.")
    description: str
    counterparty: Optional[str] = Field(default=None, description="Named person/company in the description, if any.")
    debit: float = Field(default=0, description="Money out, positive number or 0.")
    credit: float = Field(default=0, description="Money in, positive number or 0.")
    balance_after: Optional[float] = None
    source: SourceRef


class BankStatementExtraction(BaseModel):
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    account_number_masked: Optional[str] = None
    address: Optional[str] = None
    currency: str
    period_start: str
    period_end: str
    opening_balance: Optional[MoneyField] = None
    closing_balance: Optional[MoneyField] = None
    transactions: list[Transaction]


DashboardMetricKey = Literal[
    "gross_sales", "net_sales", "orders", "payout", "followers", "rating", "reviews",
    "visitors", "conversion_rate", "cancelled_orders", "returns", "ad_spend", "other",
]


class DashboardMetric(BaseModel):
    key: DashboardMetricKey
    label: str = Field(description="Label exactly as shown on screen.")
    value: float
    period_label: Optional[str] = Field(default=None, description="Period text shown next to the metric, if any.")
    source: SourceRef


class SellerDashboardExtraction(BaseModel):
    platform: Optional[str] = None
    shop_name: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    data_as_of: Optional[str] = Field(default=None, description="'Data as of' / 'last updated' timestamp if shown.")
    currency: Optional[str] = None
    metrics: list[DashboardMetric]


class ReceiptLineItem(BaseModel):
    description: str
    amount: float
    source: SourceRef


class ReceiptExtraction(BaseModel):
    merchant: Optional[str] = None
    date: Optional[str] = None
    receipt_number: Optional[str] = None
    currency: Optional[str] = None
    total: Optional[MoneyField] = None
    items: list[ReceiptLineItem] = Field(default_factory=list)
    payment_method: Optional[str] = None
    direction: Literal["purchase", "sale", "unknown"] = Field(
        description="From the applicant business's point of view: did it pay (purchase) or get paid (sale)?"
    )
    handwritten: bool = False


class LedgerEntry(BaseModel):
    row_id: str
    date: str
    description: str
    amount: float
    kind: Literal["income", "expense"]
    source: SourceRef


class LedgerExtraction(BaseModel):
    business_name_header: Optional[str] = None
    address_header: Optional[str] = None
    currency: Optional[str] = None
    period_label: Optional[str] = None
    entries: list[LedgerEntry]


class PremisesObservation(BaseModel):
    text: str
    source: SourceRef


class PremisesExtraction(BaseModel):
    signage_text: Optional[str] = None
    business_type_guess: Optional[str] = None
    apparent_size: Literal["kiosk", "small", "medium", "large", "unknown"] = "unknown"
    inventory_level: Literal["sparse", "moderate", "dense", "unknown"] = "unknown"
    observations: list[PremisesObservation] = Field(default_factory=list)


class TextLayerCheck(BaseModel):
    """Cross-check of model-extracted amounts against the PDF's own text layer (free, exact)."""

    doc_id: str
    text_layer: bool
    rows: int = 0
    amounts_found: int = 0
    amount_match_rate: Optional[float] = None
    amounts_missing: list[dict[str, Any]] = Field(default_factory=list)
    bbox_hits: int = 0
    bbox_match_rate: Optional[float] = None
    bbox_misses: list[str] = Field(default_factory=list)
    dates_found: int = 0


class DocumentExtraction(BaseModel):
    """Persisted per document. Exactly one of the typed sections is filled."""

    doc_id: str
    doc_type: DocType
    verification: Optional[TextLayerCheck] = None
    bank_statement: Optional[BankStatementExtraction] = None
    seller_dashboard: Optional[SellerDashboardExtraction] = None
    receipt: Optional[ReceiptExtraction] = None
    handwritten_ledger: Optional[LedgerExtraction] = None
    premises: Optional[PremisesExtraction] = None
    extraction_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Deterministic cashflow model (Python, never the LLM)
# ---------------------------------------------------------------------------
class MonthlyRow(BaseModel):
    month: str = Field(description="YYYY-MM")
    inflow: float
    outflow: float
    net: float
    business_inflow: float = Field(description="Inflow excluding self-transfers and round-trips.")
    n_credits: int
    n_debits: int
    end_of_month_share: float = Field(description="Share of month inflow landing in the last 5 days.")
    closing_balance: Optional[float] = None


class RecurringTransfer(BaseModel):
    counterparty: str
    amount: float
    day_of_month_mode: int
    months: list[str]
    occurrences: int
    row_ids: list[str]
    likely_debt_service: bool
    source_refs: list[SourceRef]


FlagReason = Literal["self_transfer", "round_trip", "large_one_off", "platform_payout", "cash_deposit"]


class FlaggedTransaction(BaseModel):
    row_id: str
    reason: FlagReason
    date: str
    description: str
    amount: float
    matched_row_id: Optional[str] = None
    source: SourceRef


class BalanceCheck(BaseModel):
    row_id: str
    date: str
    expected_balance: float
    reported_balance: float
    difference: float
    source: SourceRef


class CashflowSummary(BaseModel):
    currency: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    months_covered: int = 0
    months_missing: list[str] = Field(default_factory=list)
    monthly: list[MonthlyRow] = Field(default_factory=list)
    avg_monthly_inflow: float = 0
    avg_monthly_outflow: float = 0
    avg_monthly_net: float = 0
    avg_monthly_business_inflow: float = 0
    revenue_trend_pct_per_month: float = 0
    inflow_volatility_cv: float = 0
    end_of_month_concentration: float = 0
    recurring_transfers: list[RecurringTransfer] = Field(default_factory=list)
    flagged: list[FlaggedTransaction] = Field(default_factory=list)
    balance_checks: list[BalanceCheck] = Field(default_factory=list)
    platform_payout_total: float = 0
    cash_deposit_total: float = 0
    dashboard_gross_sales_total: float = 0
    dashboard_payout_total: float = 0
    receipts_purchases_total: float = 0
    receipts_sales_total: float = 0
    ledger_income_total: float = 0
    ledger_expense_total: float = 0
    off_ledger_income_estimate: float = 0
    suggested_capacity: float = Field(default=0, description="Illustrative: 3 x avg monthly net business cash. Not a credit score.")
    figures: list[Figure] = Field(default_factory=list, description="Figure catalog with ids CF.*; every value has refs.")


# ---------------------------------------------------------------------------
# Analyst memo
# ---------------------------------------------------------------------------
Recommendation = Literal["approve", "approve_with_conditions", "hold", "reject", "request_more_documents"]


class MemoSection(BaseModel):
    heading: str
    paragraphs: list[str] = Field(
        description="Prose. Never write a numeral directly; reference catalog figures as {fig:ID}."
    )
    figure_ids: list[str] = Field(default_factory=list)


class MemoDraft(BaseModel):
    """Analyst agent output. It may only *select* figure ids from the catalog, never invent values."""

    headline: str
    sections: list[MemoSection]
    key_figure_ids: list[str]
    strengths: list[str]
    concerns: list[str]
    recommendation: Recommendation
    conditions: list[str] = Field(default_factory=list)
    rationale: str


class UnsourcedNumeral(BaseModel):
    section: str
    text: str
    context: str


class Memo(BaseModel):
    case_id: str
    version: int = 1
    created_at: str = Field(default_factory=utcnow_iso)
    model: str
    prompt_version: str
    draft: MemoDraft
    figures: list[Figure] = Field(description="Catalog figures resolved by id. The only numbers in the memo.")
    unresolved_figure_ids: list[str] = Field(default_factory=list)
    unsourced_numerals: list[UnsourcedNumeral] = Field(default_factory=list)
    baseline: bool = Field(default=False, description="True when produced by the single-prompt baseline.")


# ---------------------------------------------------------------------------
# Challenger
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class ImageDuplicate(BaseModel):
    doc_a: str
    page_a: int
    doc_b: str
    page_b: int
    hamming_distance: int
    kind: Literal["exact", "near"]
    cross_case: bool = False
    other_case_id: Optional[str] = None


class PeriodCheck(BaseModel):
    doc_a: str
    period_a: str
    doc_b: str
    period_b: str
    overlap_months: list[str]
    only_in_a: list[str]
    only_in_b: list[str]
    consistent: bool


class EntityCheck(BaseModel):
    field: Literal["business_name", "account_holder", "address", "currency", "language"]
    values: dict[str, str]
    consistent: bool
    note: Optional[str] = None


class PayoutReconciliation(BaseModel):
    dashboard_gross_sales: float
    dashboard_payout: float
    bank_platform_payouts: float
    ratio_payout_to_bank: Optional[float] = None
    double_count_risk: bool


class CashReconciliation(BaseModel):
    ledger_income: float
    receipts_sales: float
    bank_cash_deposits: float
    double_count_risk: bool


class ToolFindings(BaseModel):
    """Output of the deterministic battery run before the Challenger LLM sees anything."""

    balance_checks: list[BalanceCheck] = Field(default_factory=list)
    image_duplicates: list[ImageDuplicate] = Field(default_factory=list)
    period_checks: list[PeriodCheck] = Field(default_factory=list)
    entity_checks: list[EntityCheck] = Field(default_factory=list)
    recurring_transfers: list[RecurringTransfer] = Field(default_factory=list)
    self_transfers: list[FlaggedTransaction] = Field(default_factory=list)
    round_trips: list[FlaggedTransaction] = Field(default_factory=list)
    payout_reconciliation: Optional[PayoutReconciliation] = None
    cash_reconciliation: Optional[CashReconciliation] = None
    months_missing: list[str] = Field(default_factory=list)
    unsourced_figure_ids: list[str] = Field(default_factory=list)
    unsourced_numerals: list[UnsourcedNumeral] = Field(default_factory=list)
    text_layer_checks: list[TextLayerCheck] = Field(default_factory=list)


class Objection(BaseModel):
    id: str
    question_id: str = Field(description="Q1..Q12 from the fixed checklist, or CUSTOM.")
    severity: Severity
    title: str
    claim: str
    evidence_refs: list[SourceRef] = Field(default_factory=list)
    figure_ids: list[str] = Field(default_factory=list)
    tool_evidence: Optional[str] = Field(default=None, description="Which deterministic tool result supports this.")
    suggested_action: str
    financial_impact: Optional[float] = Field(default=None, description="Amount at stake in case currency.")


class ChallengeDraft(BaseModel):
    """Challenger writer agent output."""

    objections: list[Objection]
    questions_checked: list[str]
    overall_assessment: str


class ChallengeResult(BaseModel):
    case_id: str
    version: int = 1
    created_at: str = Field(default_factory=utcnow_iso)
    model: str
    prompt_version: str
    objections: list[Objection]
    questions_checked: list[str] = Field(default_factory=list)
    investigation_notes: str = ""
    overall_assessment: str = ""
    tool_findings: ToolFindings = Field(default_factory=ToolFindings)
    baseline: bool = False


# ---------------------------------------------------------------------------
# Human decisions, letters, audit
# ---------------------------------------------------------------------------
ResolutionStatus = Literal["open", "accepted", "dismissed"]


class ObjectionResolution(BaseModel):
    objection_id: str
    status: ResolutionStatus = "open"
    note: Optional[str] = None
    by: Optional[str] = None
    at: Optional[str] = None


class Decision(BaseModel):
    case_id: str
    outcome: Recommendation
    conditions: list[str] = Field(default_factory=list)
    rationale: str
    underwriter: str = "demo-underwriter"
    decided_at: str = Field(default_factory=utcnow_iso)
    objection_resolutions: list[ObjectionResolution] = Field(default_factory=list)


class CustomerLetterDraft(BaseModel):
    language: str
    subject: str
    body: str
    next_steps: list[str] = Field(default_factory=list)


class CustomerLetter(CustomerLetterDraft):
    case_id: str
    generated_at: str = Field(default_factory=utcnow_iso)
    model: str
    prompt_version: str


class AuditEntry(BaseModel):
    id: str
    case_id: str
    at: str = Field(default_factory=utcnow_iso)
    actor: str = Field(description="'system', 'agent:<name>' or 'underwriter:<id>'.")
    event: str
    details: dict[str, Any] = Field(default_factory=dict)


class AgentTrace(BaseModel):
    id: str
    case_id: str
    agent: str
    model: str
    prompt_version: str
    started_at: str
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cost_usd: float = 0
    cached: bool = False
    status: Literal["ok", "error"] = "ok"
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Case
# ---------------------------------------------------------------------------
class StageName(str, Enum):
    intake = "intake"
    extract = "extract"
    cashflow = "cashflow"
    analyze = "analyze"
    challenge = "challenge"


StageState = Literal["pending", "running", "done", "failed"]


class StageStatus(BaseModel):
    name: StageName
    status: StageState = "pending"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False


class DocumentMeta(BaseModel):
    doc_id: str
    filename: str
    mime_type: str
    size_bytes: int
    pages: int = 1
    sha256: str
    storage_path: str
    uploaded_at: str = Field(default_factory=utcnow_iso)
    page_hashes: list[str] = Field(default_factory=list, description="Perceptual hash per page, hex.")
    doc_type: Optional[DocType] = None
    language: Optional[str] = None
    quality_flags: list[QualityFlag] = Field(default_factory=list)


class CaseStats(BaseModel):
    total_cost_usd: float = 0
    total_tokens: int = 0
    processing_seconds: float = 0
    n_llm_calls: int = 0
    n_cached_calls: int = 0
    n_figures: int = 0
    n_unsourced: int = 0
    n_objections: int = 0


CaseStatus = Literal["draft", "documents_uploaded", "processing", "memo_ready", "challenged", "decided", "failed"]


class CaseCreate(BaseModel):
    name: str
    business_name: str
    sector: str = ""
    country: str = ""
    language: str = "en"
    currency: str = "USD"
    requested_amount: Optional[float] = None


class Case(BaseModel):
    id: str
    name: str
    business_name: str
    sector: str = ""
    country: str = ""
    language: str = "en"
    currency: str = "USD"
    requested_amount: Optional[float] = None
    status: CaseStatus = "draft"
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    documents: list[DocumentMeta] = Field(default_factory=list)
    stages: list[StageStatus] = Field(default_factory=lambda: [StageStatus(name=s) for s in StageName])
    stats: CaseStats = Field(default_factory=CaseStats)
    decision: Optional[Decision] = None
    objection_resolutions: list[ObjectionResolution] = Field(default_factory=list)
    is_demo: bool = False
    demo_expected_outcome: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    def stage(self, name: StageName) -> StageStatus:
        for s in self.stages:
            if s.name == name:
                return s
        s = StageStatus(name=name)
        self.stages.append(s)
        return s


class ChallengerPriority(BaseModel):
    question_id: str
    raised: int = 0
    accepted: int = 0
    dismissed: int = 0
    acceptance_rate: Optional[float] = None
    weight: float = 1.0


class FeedbackPriorities(BaseModel):
    computed_at: str = Field(default_factory=utcnow_iso)
    n_decisions: int = 0
    priorities: list[ChallengerPriority] = Field(default_factory=list)
