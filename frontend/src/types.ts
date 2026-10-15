// Hand-written TypeScript mirror of backend/app/schemas.py.
// Field names must match the backend exactly.

export type DocType =
  | 'bank_statement'
  | 'seller_dashboard'
  | 'receipt'
  | 'handwritten_ledger'
  | 'premises_photo'
  | 'logistics_receipt'
  | 'other'

export interface BBox {
  ymin: number
  xmin: number
  ymax: number
  xmax: number
}

export interface SourceRef {
  doc_id: string
  page: number
  bbox: BBox | null
  snippet: string | null
}

export type FigureUnit = 'currency' | 'count' | 'ratio' | 'percent' | 'months' | 'days' | 'score'

export interface Figure {
  id: string
  label: string
  value: number
  unit: FigureUnit
  currency: string | null
  source_refs: SourceRef[]
  computation: string | null
  derived_from: string[]
  origin: 'document' | 'computed' | 'application'
}

export type QualityFlag =
  | 'blurry'
  | 'cropped'
  | 'low_resolution'
  | 'glare'
  | 'partial_page'
  | 'handwritten'
  | 'duplicate_suspected'
  | 'synthetic_watermark'
  | 'unreadable'
  | 'other'

export interface DocumentIntake {
  doc_id: string
  doc_type: DocType
  language: string
  currency: string | null
  quality_flags: QualityFlag[]
  confidence: number
  summary: string
}

export interface IntakeResult {
  documents: DocumentIntake[]
  business_name_candidates: string[]
  location_candidates: string[]
  notes: string | null
}

export interface MoneyField {
  value: number
  source: SourceRef
}

export interface Transaction {
  row_id: string
  date: string
  description: string
  counterparty: string | null
  debit: number
  credit: number
  balance_after: number | null
  source: SourceRef
}

export interface BankStatementExtraction {
  bank_name: string | null
  account_holder: string | null
  account_number_masked: string | null
  address: string | null
  currency: string
  period_start: string
  period_end: string
  opening_balance: MoneyField | null
  closing_balance: MoneyField | null
  transactions: Transaction[]
}

export interface DashboardMetric {
  key: string
  label: string
  value: number
  period_label: string | null
  source: SourceRef
}

export interface SellerDashboardExtraction {
  platform: string | null
  shop_name: string | null
  period_start: string | null
  period_end: string | null
  data_as_of: string | null
  currency: string | null
  metrics: DashboardMetric[]
}

export interface ReceiptLineItem {
  description: string
  amount: number
  source: SourceRef
}

export interface ReceiptExtraction {
  merchant: string | null
  date: string | null
  receipt_number: string | null
  currency: string | null
  total: MoneyField | null
  items: ReceiptLineItem[]
  payment_method: string | null
  direction: 'purchase' | 'sale' | 'unknown'
  handwritten: boolean
}

export interface LedgerEntry {
  row_id: string
  date: string
  description: string
  amount: number
  kind: 'income' | 'expense'
  source: SourceRef
}

export interface LedgerExtraction {
  business_name_header: string | null
  address_header: string | null
  currency: string | null
  period_label: string | null
  entries: LedgerEntry[]
}

export interface PremisesObservation {
  text: string
  source: SourceRef
}

export interface PremisesExtraction {
  signage_text: string | null
  business_type_guess: string | null
  apparent_size: 'kiosk' | 'small' | 'medium' | 'large' | 'unknown'
  inventory_level: 'sparse' | 'moderate' | 'dense' | 'unknown'
  observations: PremisesObservation[]
}

export interface DocumentExtraction {
  doc_id: string
  doc_type: DocType
  bank_statement: BankStatementExtraction | null
  seller_dashboard: SellerDashboardExtraction | null
  receipt: ReceiptExtraction | null
  handwritten_ledger: LedgerExtraction | null
  premises: PremisesExtraction | null
  extraction_notes: string | null
}

export interface MonthlyRow {
  month: string
  inflow: number
  outflow: number
  net: number
  business_inflow: number
  n_credits: number
  n_debits: number
  end_of_month_share: number
  closing_balance: number | null
}

export interface RecurringTransfer {
  counterparty: string
  amount: number
  day_of_month_mode: number
  months: string[]
  occurrences: number
  row_ids: string[]
  likely_debt_service: boolean
  source_refs: SourceRef[]
}

export type FlagReason = 'self_transfer' | 'round_trip' | 'large_one_off' | 'platform_payout' | 'cash_deposit'

export interface FlaggedTransaction {
  row_id: string
  reason: FlagReason
  date: string
  description: string
  amount: number
  matched_row_id: string | null
  source: SourceRef
}

export interface BalanceCheck {
  row_id: string
  date: string
  expected_balance: number
  reported_balance: number
  difference: number
  source: SourceRef
}

export interface CashflowSummary {
  currency: string
  period_start: string | null
  period_end: string | null
  months_covered: number
  months_missing: string[]
  monthly: MonthlyRow[]
  avg_monthly_inflow: number
  avg_monthly_outflow: number
  avg_monthly_net: number
  avg_monthly_business_inflow: number
  revenue_trend_pct_per_month: number
  inflow_volatility_cv: number
  end_of_month_concentration: number
  recurring_transfers: RecurringTransfer[]
  flagged: FlaggedTransaction[]
  balance_checks: BalanceCheck[]
  platform_payout_total: number
  cash_deposit_total: number
  dashboard_gross_sales_total: number
  dashboard_payout_total: number
  receipts_purchases_total: number
  receipts_sales_total: number
  ledger_income_total: number
  ledger_expense_total: number
  off_ledger_income_estimate: number
  suggested_capacity: number
  figures: Figure[]
}

export type Recommendation =
  | 'approve'
  | 'approve_with_conditions'
  | 'hold'
  | 'reject'
  | 'request_more_documents'

export const RECOMMENDATIONS: Recommendation[] = [
  'approve',
  'approve_with_conditions',
  'hold',
  'reject',
  'request_more_documents',
]

export interface MemoSection {
  heading: string
  paragraphs: string[]
  figure_ids: string[]
}

export interface MemoDraft {
  headline: string
  sections: MemoSection[]
  key_figure_ids: string[]
  strengths: string[]
  concerns: string[]
  recommendation: Recommendation
  conditions: string[]
  rationale: string
}

export interface UnsourcedNumeral {
  section: string
  text: string
  context: string
}

export interface Memo {
  case_id: string
  version: number
  created_at: string
  model: string
  prompt_version: string
  draft: MemoDraft
  figures: Figure[]
  unresolved_figure_ids: string[]
  unsourced_numerals: UnsourcedNumeral[]
  baseline: boolean
}

export type Severity = 'critical' | 'high' | 'medium' | 'low'

export interface ImageDuplicate {
  doc_a: string
  page_a: number
  doc_b: string
  page_b: number
  hamming_distance: number
  kind: 'exact' | 'near'
  cross_case: boolean
  other_case_id: string | null
}

export interface PeriodCheck {
  doc_a: string
  period_a: string
  doc_b: string
  period_b: string
  overlap_months: string[]
  only_in_a: string[]
  only_in_b: string[]
  consistent: boolean
}

export interface EntityCheck {
  field: 'business_name' | 'account_holder' | 'address' | 'currency' | 'language'
  values: Record<string, string>
  consistent: boolean
  note: string | null
}

export interface PayoutReconciliation {
  dashboard_gross_sales: number
  dashboard_payout: number
  bank_platform_payouts: number
  ratio_payout_to_bank: number | null
  double_count_risk: boolean
}

export interface CashReconciliation {
  ledger_income: number
  receipts_sales: number
  bank_cash_deposits: number
  double_count_risk: boolean
}

export interface ToolFindings {
  balance_checks: BalanceCheck[]
  image_duplicates: ImageDuplicate[]
  period_checks: PeriodCheck[]
  entity_checks: EntityCheck[]
  recurring_transfers: RecurringTransfer[]
  self_transfers: FlaggedTransaction[]
  round_trips: FlaggedTransaction[]
  payout_reconciliation: PayoutReconciliation | null
  cash_reconciliation: CashReconciliation | null
  months_missing: string[]
  unsourced_figure_ids: string[]
  unsourced_numerals: UnsourcedNumeral[]
}

export interface Objection {
  id: string
  question_id: string
  severity: Severity
  title: string
  claim: string
  evidence_refs: SourceRef[]
  figure_ids: string[]
  tool_evidence: string | null
  suggested_action: string
  financial_impact: number | null
}

export interface ChallengeResult {
  case_id: string
  version: number
  created_at: string
  model: string
  prompt_version: string
  objections: Objection[]
  questions_checked: string[]
  investigation_notes: string
  overall_assessment: string
  tool_findings: ToolFindings
  baseline: boolean
}

export type ResolutionStatus = 'open' | 'accepted' | 'dismissed'

export interface ObjectionResolution {
  objection_id: string
  status: ResolutionStatus
  note: string | null
  by: string | null
  at: string | null
}

export interface Decision {
  case_id: string
  outcome: Recommendation
  conditions: string[]
  rationale: string
  underwriter: string
  decided_at: string
  objection_resolutions: ObjectionResolution[]
}

export interface CustomerLetter {
  language: string
  subject: string
  body: string
  next_steps: string[]
  case_id: string
  generated_at: string
  model: string
  prompt_version: string
}

export interface AuditEntry {
  id: string
  case_id: string
  at: string
  actor: string
  event: string
  details: Record<string, unknown>
}

export interface AgentTrace {
  id: string
  case_id: string
  agent: string
  model: string
  prompt_version: string
  started_at: string
  duration_ms: number
  input_tokens: number
  output_tokens: number
  thinking_tokens: number
  cost_usd: number
  cached: boolean
  status: 'ok' | 'error'
  error: string | null
}

export type StageName = 'intake' | 'extract' | 'cashflow' | 'analyze' | 'challenge'
export const STAGE_ORDER: StageName[] = ['intake', 'extract', 'cashflow', 'analyze', 'challenge']

export type StageState = 'pending' | 'running' | 'done' | 'failed'

export interface StageStatus {
  name: StageName
  status: StageState
  started_at: string | null
  finished_at: string | null
  error: string | null
  cached: boolean
}

export interface DocumentMeta {
  doc_id: string
  filename: string
  mime_type: string
  size_bytes: number
  pages: number
  sha256: string
  storage_path: string
  uploaded_at: string
  page_hashes: string[]
  doc_type: DocType | null
  language: string | null
  quality_flags: QualityFlag[]
}

export interface CaseStats {
  total_cost_usd: number
  total_tokens: number
  processing_seconds: number
  n_llm_calls: number
  n_cached_calls: number
  n_figures: number
  n_unsourced: number
  n_objections: number
}

export type CaseStatus =
  | 'draft'
  | 'documents_uploaded'
  | 'processing'
  | 'memo_ready'
  | 'challenged'
  | 'decided'
  | 'failed'

export interface CaseCreate {
  name: string
  business_name: string
  sector: string
  country: string
  language: string
  currency: string
  requested_amount: number | null
}

export interface Case {
  id: string
  name: string
  business_name: string
  sector: string
  country: string
  language: string
  currency: string
  requested_amount: number | null
  status: CaseStatus
  created_at: string
  updated_at: string
  documents: DocumentMeta[]
  stages: StageStatus[]
  stats: CaseStats
  decision: Decision | null
  objection_resolutions: ObjectionResolution[]
  is_demo: boolean
  workspace?: string | null
  demo_expected_outcome: string | null
  tags: string[]
}

export interface ChallengerPriority {
  question_id: string
  raised: number
  accepted: number
  dismissed: number
  acceptance_rate: number | null
  weight: number
}

export interface FeedbackPriorities {
  computed_at: string
  n_decisions: number
  priorities: ChallengerPriority[]
}

export interface Health {
  status: string
  llm_mode: 'live' | 'cache_only' | 'mock'
  storage: 'local' | 'gcp'
  models: { flash: string; pro: string }
}

export interface BenchmarkSummary {
  trap_recall: number
  baseline_trap_recall: number
  false_positive_rate: number
  unsourced_numbers: number
  avg_seconds: number
  avg_cost_usd: number
}

export interface Benchmark {
  generated_at: string
  cases: unknown[]
  summary: BenchmarkSummary
}

export interface ResolutionRequest {
  status: ResolutionStatus
  note?: string
  by?: string
}

export interface DecisionRequest {
  outcome: Recommendation
  conditions: string[]
  rationale: string
  underwriter: string
}

export interface LetterRequest {
  language: string
}

/** Fixed challenger checklist titles (API.md). */
export const QUESTION_TITLES: Record<string, string> = {
  Q1: 'Double counting across sources',
  Q2: 'Seasonality vs one-off inflows',
  Q3: 'Self-transfers',
  Q4: 'Duplicate receipt/image reuse',
  Q5: 'Dashboard period vs statement period',
  Q6: 'Balance continuity',
  Q7: 'Undisclosed debt service',
  Q8: 'Premises vs claimed scale',
  Q9: 'Every number sourced',
  Q10: 'End-of-month concentration',
  Q11: 'Entity name/address consistency',
  Q12: 'Language/currency vs location',
  CUSTOM: 'Case-specific question',
}

export const SEVERITY_ORDER: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 }
