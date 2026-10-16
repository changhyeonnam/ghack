import type { ReactNode } from 'react'
import type { CaseStatus, QualityFlag, Recommendation, Severity, StageStatus } from '../types'
import { STAGE_ORDER } from '../types'
import { durationBetween, humanize } from '../format'
import { Icon, type IconName } from './Icons'

export const STATUS_LABEL: Record<CaseStatus, string> = {
  draft: 'Draft',
  documents_uploaded: 'Documents added',
  processing: 'Processing',
  memo_ready: 'Memo ready',
  challenged: 'In review',
  decided: 'Decided',
  failed: 'Failed',
}

export function StatusBadge({ status, size }: { status: CaseStatus; size?: 'sm' }) {
  return (
    <span className={`badge status-${status}${size ? ` badge-${size}` : ''}`}>
      <span className="badge-dot" aria-hidden="true" />
      {STATUS_LABEL[status] ?? humanize(status)}
    </span>
  )
}

const REC_LABEL: Record<Recommendation, string> = {
  approve: 'Approve',
  approve_with_conditions: 'Approve with conditions',
  hold: 'Hold',
  reject: 'Reject',
  request_more_documents: 'Request more documents',
}

export const REC_DESCRIPTION: Record<Recommendation, string> = {
  approve: 'Evidence supports the requested amount without extra safeguards.',
  approve_with_conditions: 'Approve, but disbursement depends on the listed conditions being met.',
  hold: 'Pause the application until open questions are resolved.',
  reject: 'The evidence does not support lending at this time.',
  request_more_documents: 'Ask the applicant for specific additional documents before deciding.',
}

export function recommendationLabel(r: Recommendation | string): string {
  return REC_LABEL[r as Recommendation] ?? humanize(r)
}

export function RecommendationBadge({
  value,
  large,
  prefix,
}: {
  value: Recommendation | string
  large?: boolean
  prefix?: string
}) {
  return (
    <span className={`badge rec-${value}${large ? ' badge-lg' : ''}`}>
      {prefix ? <span className="badge-prefix">{prefix}</span> : null}
      {recommendationLabel(value)}
    </span>
  )
}

export function SeverityPill({ severity, count }: { severity: Severity; count?: number }) {
  return (
    <span className={`pill sev-${severity}`}>
      {count !== undefined ? <span className="pill-count">{count}</span> : null}
      {severity}
    </span>
  )
}

export function Chip({ children, tone, mono, title }: { children: ReactNode; tone?: string; mono?: boolean; title?: string }) {
  return (
    <span className={`chip${tone ? ` chip-${tone}` : ''}${mono ? ' mono' : ''}`} title={title}>
      {children}
    </span>
  )
}

const STAGE_LABEL: Record<string, string> = {
  intake: 'Intake',
  extract: 'Extract',
  cashflow: 'Cashflow',
  analyze: 'Analyze',
  challenge: 'Challenge',
}

/** Five compact dots, one per pipeline stage, each with a tooltip. */
export function StageDots({ stages }: { stages: StageStatus[] }) {
  return (
    <span className="stage-dots" aria-label="Pipeline progress">
      {STAGE_ORDER.map((name) => {
        const st = stages.find((s) => s.name === name)
        const status = st?.status ?? 'pending'
        const dur = st?.started_at ? durationBetween(st.started_at, st.finished_at) : ''
        const tip = `${STAGE_LABEL[name]} · ${status}${dur ? ` · ${dur}` : ''}`
        return <span key={name} className={`dot dot-${status} tip`} data-tip={tip} />
      })}
    </span>
  )
}

export function Spinner({ small }: { small?: boolean }) {
  return <span className={`spinner${small ? ' spinner-sm' : ''}`} aria-hidden="true" />
}

export function EmptyState({
  title,
  hint,
  icon,
  action,
  tone,
}: {
  title: string
  hint?: ReactNode
  icon?: IconName
  action?: ReactNode
  tone?: 'good' | 'bad'
}) {
  return (
    <div className={`empty${tone ? ` empty-${tone}` : ''}`}>
      <div className="empty-icon" aria-hidden="true">
        <Icon name={icon ?? 'layers'} size={20} />
      </div>
      <div className="empty-title">{title}</div>
      {hint ? <div className="empty-hint">{hint}</div> : null}
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  )
}

export function Loading({ label }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <Spinner /> <span>{label ?? 'Loading…'}</span>
    </div>
  )
}

/** Grey shimmer block. Width/height accept any CSS length. */
export function Skeleton({ w, h, className, radius }: { w?: string | number; h?: string | number; className?: string; radius?: number }) {
  return <span className={`skeleton${className ? ` ${className}` : ''}`} style={{ width: w, height: h, borderRadius: radius }} aria-hidden="true" />
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  const widths = ['100%', '92%', '97%', '70%', '88%', '60%']
  return (
    <div className={`skeleton-text${className ? ` ${className}` : ''}`} aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} h={12} w={widths[i % widths.length]} />
      ))}
    </div>
  )
}

/** File-type glyph from a MIME type. */
export function DocIcon({ mime, size = 16 }: { mime: string | null | undefined; size?: number }) {
  const pdf = (mime ?? '').includes('pdf')
  return (
    <span className={`doc-icon ${pdf ? 'doc-icon-pdf' : 'doc-icon-img'}`}>
      <Icon name={pdf ? 'file-pdf' : 'image'} size={size} />
    </span>
  )
}

const FLAG_ICON: Record<QualityFlag, IconName> = {
  blurry: 'eye-off',
  cropped: 'minus',
  low_resolution: 'eye-off',
  glare: 'sun',
  partial_page: 'minus',
  handwritten: 'pen',
  duplicate_suspected: 'copy',
  synthetic_watermark: 'spark',
  unreadable: 'alert',
  other: 'info',
}

// Dataset watermarks are a property of the demo documents, not a finding about the applicant: not shown.
const HIDDEN_FLAGS = new Set<QualityFlag>(['synthetic_watermark'])

export function visibleFlags(flags: QualityFlag[]): QualityFlag[] {
  return flags.filter((f) => !HIDDEN_FLAGS.has(f))
}

export function QualityFlagIcons({ flags: all }: { flags: QualityFlag[] }) {
  const flags = visibleFlags(all)
  if (flags.length === 0) return null
  return (
    <span className="flag-icons">
      {flags.map((f) => (
        <span key={f} className={`flag-icon tip flag-${f}`} data-tip={humanize(f)}>
          <Icon name={FLAG_ICON[f] ?? 'info'} size={12} />
        </span>
      ))}
    </span>
  )
}

export interface SegmentOption<T extends string> {
  value: T
  label: ReactNode
  count?: number
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  size,
  ariaLabel,
}: {
  value: T
  options: SegmentOption<T>[]
  onChange: (v: T) => void
  size?: 'sm'
  ariaLabel?: string
}) {
  return (
    <div className={`segmented${size ? ` segmented-${size}` : ''}`} role="tablist" aria-label={ariaLabel}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          className={`segment${o.value === value ? ' active' : ''}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
          {o.count !== undefined ? <span className="segment-count">{o.count}</span> : null}
        </button>
      ))}
    </div>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>
}

/** Verified seal / warning for sourced numbers. */
export function SourcedSeal({ unsourced }: { unsourced: number }) {
  if (unsourced === 0) {
    return (
      <span className="seal seal-good tip" data-tip="Every number in this memo links to a document location or a computation">
        <Icon name="shield-check" size={14} />
        All numbers sourced
      </span>
    )
  }
  return (
    <span className="seal seal-bad">
      <Icon name="alert" size={14} />
      {unsourced} unsourced number{unsourced === 1 ? '' : 's'}
    </span>
  )
}
