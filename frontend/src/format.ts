// Formatting helpers: currency (ISO code aware), percent, ISO dates, durations.

import type { Figure, FigureUnit } from './types'

const ZERO_DECIMAL_CURRENCIES = new Set(['IDR', 'VND', 'JPY', 'KRW'])

function fractionDigits(currency: string | null | undefined): number {
  if (!currency) return 2
  return ZERO_DECIMAL_CURRENCIES.has(currency.toUpperCase()) ? 0 : 2
}

const fmtCache = new Map<string, Intl.NumberFormat>()
function cached(key: string, make: () => Intl.NumberFormat): Intl.NumberFormat {
  let f = fmtCache.get(key)
  if (!f) {
    f = make()
    fmtCache.set(key, f)
  }
  return f
}

/** Full currency amount, e.g. "IDR 12,345,000" or "$1,234.50". */
export function formatCurrency(value: number | null | undefined, currency?: string | null, compact = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const code = (currency || '').toUpperCase()
  const digits = fractionDigits(code)
  if (!code) {
    return cached(`num-${digits}-${compact}`, () =>
      new Intl.NumberFormat('en-US', {
        maximumFractionDigits: digits,
        minimumFractionDigits: 0,
        notation: compact ? 'compact' : 'standard',
      }),
    ).format(value)
  }
  try {
    return cached(`cur-${code}-${compact}`, () =>
      new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: code,
        currencyDisplay: 'code',
        maximumFractionDigits: compact ? 1 : digits,
        minimumFractionDigits: compact ? 0 : digits,
        notation: compact ? 'compact' : 'standard',
      }),
    )
      .format(value)
      .replace(/ /g, ' ')
  } catch {
    return `${code} ${value.toLocaleString('en-US', { maximumFractionDigits: digits })}`
  }
}

export const formatCompact = (value: number | null | undefined, currency?: string | null) =>
  formatCurrency(value, currency, true)

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString('en-US', { maximumFractionDigits: digits })
}

/** Percent from a ratio (0.12 → "12.0%") unless `alreadyPercent` is true. */
export function formatPercent(value: number | null | undefined, digits = 1, alreadyPercent = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const pct = alreadyPercent ? value : value * 100
  return `${pct.toFixed(digits)}%`
}

export function formatSignedPercent(value: number | null | undefined, digits = 1, alreadyPercent = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const s = formatPercent(value, digits, alreadyPercent)
  return value > 0 ? `+${s}` : s
}

export function formatUsd(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `$${value.toFixed(digits)}`
}

export function formatFigure(fig: Pick<Figure, 'value' | 'unit' | 'currency'>, compact = false): string {
  return formatUnit(fig.value, fig.unit, fig.currency, compact)
}

export function formatUnit(value: number, unit: FigureUnit, currency?: string | null, compact = false): string {
  switch (unit) {
    case 'currency':
      return formatCurrency(value, currency, compact)
    case 'percent':
      // Percent figures are assumed to be already expressed in percent points.
      return formatPercent(value, 1, true)
    case 'ratio':
      return value.toFixed(2)
    case 'count':
      return formatNumber(value, 0)
    case 'months':
      return `${formatNumber(value, value % 1 === 0 ? 0 : 1)} mo`
    case 'days':
      return `${formatNumber(value, 0)} d`
    case 'score':
      return value.toFixed(1)
    default:
      return formatNumber(value, 2)
  }
}

/** ISO timestamp → "2026-10-14 09:30" (local time). */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** ISO date/timestamp → "2026-10-14". */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return iso.slice(0, 10)
}

/** "2026-03" → "Mar 2026". */
export function formatMonth(ym: string): string {
  const m = /^(\d{4})-(\d{2})/.exec(ym)
  if (!m) return ym
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${names[Number(m[2]) - 1] ?? m[2]} ${m[1]}`
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

export function durationBetween(start: string | null, end: string | null): string {
  if (!start) return ''
  const a = new Date(start).getTime()
  const b = end ? new Date(end).getTime() : Date.now()
  if (Number.isNaN(a) || Number.isNaN(b)) return ''
  return formatDuration(b - a)
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export function countryFlag(country: string): string {
  const c = country.trim().toUpperCase()
  const map: Record<string, string> = {
    ID: '🇮🇩',
    INDONESIA: '🇮🇩',
    VN: '🇻🇳',
    VIETNAM: '🇻🇳',
    PH: '🇵🇭',
    PHILIPPINES: '🇵🇭',
    SG: '🇸🇬',
    TH: '🇹🇭',
    MY: '🇲🇾',
    US: '🇺🇸',
  }
  if (map[c]) return map[c]
  if (/^[A-Z]{2}$/.test(c)) {
    return String.fromCodePoint(...[...c].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65))
  }
  return '🌏'
}

export function humanize(s: string): string {
  return s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export const LANGUAGE_NAMES: Record<string, string> = {
  id: 'Indonesian',
  vi: 'Vietnamese',
  tl: 'Filipino',
  en: 'English',
  th: 'Thai',
  ms: 'Malay',
}

export function languageName(code: string | null | undefined): string {
  if (!code) return '—'
  return LANGUAGE_NAMES[code] ?? code.toUpperCase()
}

/** Cost for display: "< $0.01" below one cent, "$0.00" when zero, otherwise two decimals. */
export function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (value === 0) return '$0.00'
  if (value < 0.01) return '< $0.01'
  return `$${value.toFixed(2)}`
}

/** "2026-10-14T11:10:24Z" → "3 h ago" / "yesterday" / "Oct 14". */
export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return iso
  const diff = Date.now() - t
  const s = Math.round(diff / 1000)
  if (s < 45) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m} min ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} h ago`
  const d = Math.round(h / 24)
  if (d === 1) return 'yesterday'
  if (d < 7) return `${d} d ago`
  const date = new Date(t)
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${names[date.getMonth()]} ${date.getDate()}${date.getFullYear() !== new Date().getFullYear() ? ` ${date.getFullYear()}` : ''}`
}

/** Human-readable document type. */
export const DOC_TYPE_LABEL: Record<string, string> = {
  bank_statement: 'Bank statement',
  seller_dashboard: 'Seller dashboard',
  receipt: 'Receipt',
  handwritten_ledger: 'Handwritten ledger',
  premises_photo: 'Premises photo',
  logistics_receipt: 'Logistics receipt',
  other: 'Other',
}
export function docTypeLabel(t: string | null | undefined): string {
  if (!t) return 'Unclassified'
  return DOC_TYPE_LABEL[t] ?? humanize(t)
}

export const COUNTRY_NAMES: Record<string, string> = {
  ID: 'Indonesia',
  VN: 'Vietnam',
  PH: 'Philippines',
  SG: 'Singapore',
  TH: 'Thailand',
  MY: 'Malaysia',
  US: 'United States',
}
export function countryName(code: string | null | undefined): string {
  if (!code) return '—'
  return COUNTRY_NAMES[code.toUpperCase()] ?? code
}

/** "gemini-3.8-flash" → "Gemini 3.8 Flash". */
export function modelDisplayName(model: string | null | undefined): string {
  if (!model) return ''
  const base = model.split('/').pop() ?? model
  return base
    .split('-')
    .map((p) => (/^\d/.test(p) ? p : p.charAt(0).toUpperCase() + p.slice(1)))
    .join(' ')
}

/** Humanise an audit event name with its details, e.g. "memo_drafted" → "Memo drafted (v1)". */
export function auditEventTitle(event: string, details: Record<string, unknown>): string {
  const v = details['version']
  const ver = typeof v === 'number' || typeof v === 'string' ? ` (v${v})` : ''
  const stage = /^stage_(\w+)_done$/.exec(event)
  if (stage) return `${humanize(stage[1]!)} stage completed`
  const failed = /^stage_(\w+)_failed$/.exec(event)
  if (failed) return `${humanize(failed[1]!)} stage failed`
  switch (event) {
    case 'case_created':
      return 'Case created'
    case 'documents_uploaded':
      return 'Documents uploaded'
    case 'documents_classified':
      return 'Documents classified'
    case 'documents_extracted':
      return 'Documents extracted'
    case 'cashflow_computed':
      return 'Cashflow model computed'
    case 'memo_drafted':
      return `Memo drafted${ver}`
    case 'memo_challenged':
      return `Memo challenged${ver}`
    case 'objection_resolved':
      return 'Objection resolved'
    case 'decision_signed':
      return 'Decision signed'
    case 'letter_generated':
      return 'Customer letter generated'
    default:
      return humanize(event)
  }
}

export function pluralize(n: number, one: string, many?: string): string {
  return `${n} ${n === 1 ? one : (many ?? `${one}s`)}`
}
