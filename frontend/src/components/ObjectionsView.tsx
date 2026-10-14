import { useMemo, useState, type ReactNode } from 'react'
import { formatCurrency, formatMonth, humanize } from '../format'
import type { Case, ChallengeResult, Figure, Memo, ResolutionStatus, Severity, ToolFindings } from '../types'
import { SEVERITY_ORDER } from '../types'
import { EmptyState, Segmented, Skeleton, SkeletonText } from './Badges'
import { Icon } from './Icons'
import { ObjectionCard } from './ObjectionCard'
import { RefChip, RefList } from './RefChip'
import { useViewer } from './viewerContext'

interface Props {
  kase: Case
  challenge: ChallengeResult | null
  memo: Memo | null
  challengeDone: boolean
  loading: boolean
  busyId: string | null
  onResolve: (objectionId: string, status: ResolutionStatus) => void
}

type SevFilter = 'all' | Severity
type StatusFilter = 'all' | ResolutionStatus
const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']

export function ObjectionsView({ kase, challenge, memo, challengeDone, loading, busyId, onResolve }: Props) {
  const [sevFilter, setSevFilter] = useState<SevFilter>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')

  const figuresById = useMemo(() => {
    const m = new Map<string, Figure>()
    for (const f of memo?.figures ?? []) m.set(f.id, f)
    return m
  }, [memo])

  const sorted = useMemo(
    () => [...(challenge?.objections ?? [])].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]),
    [challenge],
  )
  const resolutions = useMemo(() => {
    const m = new Map<string, Case['objection_resolutions'][number]>()
    for (const r of kase.objection_resolutions) m.set(r.objection_id, r)
    return m
  }, [kase.objection_resolutions])

  if (loading) return <ObjectionsSkeleton />
  if (!challenge) {
    return (
      <EmptyState
        icon="shield-check"
        title={challengeDone ? 'Challenge result not available' : 'No objections yet'}
        hint={
          challengeDone
            ? 'The Challenge stage finished but its result could not be loaded.'
            : 'Run the Challenge stage. A second agent runs the 12-question checklist and deterministic tools against the memo.'
        }
      />
    )
  }

  const bySeverity: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0 }
  const counts = { accepted: 0, dismissed: 0, open: 0 }
  for (const o of sorted) {
    bySeverity[o.severity]++
    counts[resolutions.get(o.id)?.status ?? 'open']++
  }
  const total = sorted.length

  const visible = sorted.filter((o) => {
    if (sevFilter !== 'all' && o.severity !== sevFilter) return false
    const st = resolutions.get(o.id)?.status ?? 'open'
    if (statusFilter !== 'all' && st !== statusFilter) return false
    return true
  })

  return (
    <div className="objections">
      <section className="panel objections-summary" aria-label="Objection summary">
        <div className="objections-summary-top">
          <div>
            <div className="summary-headline">
              <strong className="mono">{total}</strong> objection{total === 1 ? '' : 's'}
              <span className="muted"> from {challenge.questions_checked.length} checklist questions</span>
            </div>
            {challenge.overall_assessment ? <p className="assessment">{challenge.overall_assessment}</p> : null}
          </div>
          <div className="resolution-counts">
            <span className="res-count res-count-open">
              <span className="mono">{counts.open}</span> open
            </span>
            <span className="res-count res-count-accepted">
              <Icon name="check" size={11} />
              <span className="mono">{counts.accepted}</span> accepted
            </span>
            <span className="res-count res-count-dismissed">
              <Icon name="x" size={11} />
              <span className="mono">{counts.dismissed}</span> dismissed
            </span>
          </div>
        </div>
        {total > 0 ? (
          <div className="sev-bar" role="img" aria-label={SEVERITIES.map((s) => `${bySeverity[s]} ${s}`).join(', ')}>
            {SEVERITIES.filter((s) => bySeverity[s] > 0).map((s) => (
              <span key={s} className={`sev-seg sev-seg-${s} tip`} style={{ flexGrow: bySeverity[s] }} data-tip={`${bySeverity[s]} ${s}`}>
                {bySeverity[s]}
              </span>
            ))}
          </div>
        ) : null}
      </section>

      {total === 0 ? (
        <EmptyState icon="check-circle" tone="good" title="No objections raised" hint="The challenger found nothing to contest in this memo." />
      ) : (
        <>
          <div className="toolbar toolbar-plain">
            <Segmented<SevFilter>
              size="sm"
              ariaLabel="Filter by severity"
              value={sevFilter}
              onChange={setSevFilter}
              options={[
                { value: 'all', label: 'All', count: total },
                ...SEVERITIES.filter((s) => bySeverity[s] > 0).map((s) => ({
                  value: s,
                  label: <span className={`sev-text sev-text-${s}`}>{humanize(s)}</span>,
                  count: bySeverity[s],
                })),
              ]}
            />
            <Segmented<StatusFilter>
              size="sm"
              ariaLabel="Filter by status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'Any status' },
                { value: 'open', label: 'Open', count: counts.open },
                { value: 'accepted', label: 'Accepted', count: counts.accepted },
                { value: 'dismissed', label: 'Dismissed', count: counts.dismissed },
              ]}
            />
          </div>

          {visible.length === 0 ? (
            <EmptyState icon="search" title="No objections match these filters" />
          ) : (
            <div className="objection-list">
              {visible.map((o) => (
                <ObjectionCard
                  key={o.id}
                  objection={o}
                  resolution={resolutions.get(o.id)}
                  currency={kase.currency}
                  figuresById={figuresById}
                  busy={busyId === o.id}
                  onResolve={(status) => onResolve(o.id, status)}
                />
              ))}
            </div>
          )}
        </>
      )}

      <ToolFindingsPanel findings={challenge.tool_findings} currency={kase.currency} />

      {challenge.investigation_notes ? (
        <details className="panel details-panel">
          <summary>
            <Icon name="chevron-right" size={12} className="summary-chev" />
            Investigation notes
          </summary>
          <pre className="mono-block">{challenge.investigation_notes}</pre>
        </details>
      ) : null}
    </div>
  )
}

function Block({ title, count, children, tone }: { title: string; count: number; children: ReactNode; tone?: 'bad' | 'warn' | 'good' }) {
  return (
    <details className="tf-block" open={tone === 'bad'}>
      <summary>
        <Icon name="chevron-right" size={12} className="summary-chev" />
        <span className="tf-title">{title}</span>
        <span className={`chip${tone ? ` chip-${tone}` : ''} mono`}>{count}</span>
      </summary>
      <div className="tf-body">{children}</div>
    </details>
  )
}

function ToolFindingsPanel({ findings: f, currency }: { findings: ToolFindings; currency: string }) {
  const viewer = useViewer()
  const total =
    f.balance_checks.length +
    f.image_duplicates.length +
    f.period_checks.length +
    f.entity_checks.length +
    f.recurring_transfers.length +
    f.self_transfers.length +
    f.round_trips.length +
    (f.payout_reconciliation ? 1 : 0) +
    (f.cash_reconciliation ? 1 : 0) +
    f.months_missing.length +
    f.unsourced_figure_ids.length +
    f.unsourced_numerals.length

  const inconsistentPeriods = f.period_checks.filter((p) => !p.consistent).length
  const inconsistentEntities = f.entity_checks.filter((e) => !e.consistent).length

  return (
    <section className="panel tool-findings">
      <div className="panel-head">
        <h3 className="panel-title">
          <Icon name="tool" size={14} /> Automated checks
        </h3>
        <span className="muted small">
          {total} finding{total === 1 ? '' : 's'} from deterministic tools
        </span>
      </div>
      {total === 0 ? (
        <p className="muted small inline-icon">
          <Icon name="check-circle" size={14} /> All deterministic checks passed.
        </p>
      ) : (
        <div className="tf-list">
          {f.balance_checks.length > 0 ? (
            <Block title="Balance continuity breaks" count={f.balance_checks.length} tone="bad">
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Date</th>
                    <th className="num">Expected</th>
                    <th className="num">Reported</th>
                    <th className="num">Difference</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {f.balance_checks.map((b) => (
                    <tr key={b.row_id}>
                      <td className="mono">{b.row_id}</td>
                      <td className="mono">{b.date}</td>
                      <td className="num mono">{formatCurrency(b.expected_balance, currency)}</td>
                      <td className="num mono">{formatCurrency(b.reported_balance, currency)}</td>
                      <td className="num mono bad">{formatCurrency(b.difference, currency)}</td>
                      <td>
                        <RefChip r={b.source} label={`Balance break ${b.row_id}`} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Block>
          ) : null}

          {f.image_duplicates.length > 0 ? (
            <Block title="Image duplicates" count={f.image_duplicates.length} tone="bad">
              <ul className="plain-list">
                {f.image_duplicates.map((d, i) => (
                  <li key={i} className="dup-row">
                    <button className="link-btn" onClick={() => viewer.openDocument(d.doc_a, d.page_a)}>
                      {viewer.docName(d.doc_a)} p.{d.page_a}
                    </button>
                    <span className="muted">≈</span>
                    <button className="link-btn" onClick={() => viewer.openDocument(d.doc_b, d.page_b)}>
                      {viewer.docName(d.doc_b)} p.{d.page_b}
                    </button>
                    <span className={`chip ${d.kind === 'exact' ? 'chip-bad' : 'chip-warn'}`}>{d.kind}</span>
                    <span className="muted small mono">hamming {d.hamming_distance}</span>
                    {d.cross_case ? <span className="chip chip-bad">cross-case{d.other_case_id ? ` · ${d.other_case_id}` : ''}</span> : null}
                  </li>
                ))}
              </ul>
            </Block>
          ) : null}

          {f.period_checks.length > 0 ? (
            <Block title="Period consistency" count={f.period_checks.length} tone={inconsistentPeriods > 0 ? 'warn' : 'good'}>
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Document A</th>
                    <th>Document B</th>
                    <th>Overlap</th>
                    <th>Only in A</th>
                    <th>Only in B</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {f.period_checks.map((p, i) => (
                    <tr key={i}>
                      <td>
                        {viewer.docName(p.doc_a)} <span className="muted small mono">{p.period_a}</span>
                      </td>
                      <td>
                        {viewer.docName(p.doc_b)} <span className="muted small mono">{p.period_b}</span>
                      </td>
                      <td className="mono small">{p.overlap_months.map(formatMonth).join(', ') || '—'}</td>
                      <td className="mono small">{p.only_in_a.map(formatMonth).join(', ') || '—'}</td>
                      <td className="mono small">{p.only_in_b.map(formatMonth).join(', ') || '—'}</td>
                      <td>
                        <span className={`chip ${p.consistent ? 'chip-success' : 'chip-bad'}`}>{p.consistent ? 'consistent' : 'mismatch'}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Block>
          ) : null}

          {f.entity_checks.length > 0 ? (
            <Block title="Entity consistency" count={f.entity_checks.length} tone={inconsistentEntities > 0 ? 'warn' : 'good'}>
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Values by document</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {f.entity_checks.map((e, i) => (
                    <tr key={i}>
                      <td>{humanize(e.field)}</td>
                      <td>
                        <ul className="plain-list small">
                          {Object.entries(e.values).map(([doc, v]) => (
                            <li key={doc}>
                              <span className="muted">{viewer.docName(doc)}:</span> {v}
                            </li>
                          ))}
                        </ul>
                        {e.note ? <div className="muted small">{e.note}</div> : null}
                      </td>
                      <td>
                        <span className={`chip ${e.consistent ? 'chip-success' : 'chip-bad'}`}>{e.consistent ? 'consistent' : 'mismatch'}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Block>
          ) : null}

          {f.recurring_transfers.length > 0 ? (
            <Block title="Recurring transfers" count={f.recurring_transfers.length} tone={f.recurring_transfers.some((r) => r.likely_debt_service) ? 'warn' : undefined}>
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Counterparty</th>
                    <th className="num">Amount</th>
                    <th className="num">Day</th>
                    <th className="num">Occurrences</th>
                    <th />
                    <th>Sources</th>
                  </tr>
                </thead>
                <tbody>
                  {f.recurring_transfers.map((r, i) => (
                    <tr key={i}>
                      <td>{r.counterparty}</td>
                      <td className="num mono">{formatCurrency(r.amount, currency)}</td>
                      <td className="num mono">{r.day_of_month_mode}</td>
                      <td className="num mono">{r.occurrences}</td>
                      <td>{r.likely_debt_service ? <span className="chip chip-bad">likely debt service</span> : null}</td>
                      <td>
                        <RefList refs={r.source_refs} label={`Recurring transfer to ${r.counterparty}`} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Block>
          ) : null}

          {f.self_transfers.length + f.round_trips.length > 0 ? (
            <Block title="Self-transfers and round-trips" count={f.self_transfers.length + f.round_trips.length} tone="warn">
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Reason</th>
                    <th>Date</th>
                    <th>Description</th>
                    <th className="num">Amount</th>
                    <th>Matched</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {[...f.self_transfers, ...f.round_trips].map((t) => (
                    <tr key={`${t.reason}-${t.row_id}`}>
                      <td className="mono">{t.row_id}</td>
                      <td>
                        <span className="chip chip-warn">{humanize(t.reason)}</span>
                      </td>
                      <td className="mono">{t.date}</td>
                      <td className="truncate" title={t.description}>
                        {t.description}
                      </td>
                      <td className="num mono">{formatCurrency(t.amount, currency)}</td>
                      <td className="mono">{t.matched_row_id ?? '—'}</td>
                      <td>
                        <RefChip r={t.source} label={`${humanize(t.reason)} ${t.row_id}`} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Block>
          ) : null}

          {f.payout_reconciliation ? (
            <Block title="Platform payout reconciliation" count={1} tone={f.payout_reconciliation.double_count_risk ? 'bad' : 'good'}>
              {f.payout_reconciliation.double_count_risk ? (
                <div className="callout callout-bad small">
                  <Icon name="alert" size={14} />
                  <span>Dashboard revenue and bank payouts overlap. Adding both double counts income.</span>
                </div>
              ) : null}
              <dl className="kv">
                <dt>Dashboard gross sales</dt>
                <dd className="mono">{formatCurrency(f.payout_reconciliation.dashboard_gross_sales, currency)}</dd>
                <dt>Dashboard payout</dt>
                <dd className="mono">{formatCurrency(f.payout_reconciliation.dashboard_payout, currency)}</dd>
                <dt>Bank platform payouts</dt>
                <dd className="mono">{formatCurrency(f.payout_reconciliation.bank_platform_payouts, currency)}</dd>
                <dt>Payout / bank ratio</dt>
                <dd className="mono">{f.payout_reconciliation.ratio_payout_to_bank === null ? '—' : f.payout_reconciliation.ratio_payout_to_bank.toFixed(2)}</dd>
              </dl>
            </Block>
          ) : null}

          {f.cash_reconciliation ? (
            <Block title="Cash reconciliation" count={1} tone={f.cash_reconciliation.double_count_risk ? 'bad' : 'good'}>
              <dl className="kv">
                <dt>Ledger income</dt>
                <dd className="mono">{formatCurrency(f.cash_reconciliation.ledger_income, currency)}</dd>
                <dt>Receipt sales</dt>
                <dd className="mono">{formatCurrency(f.cash_reconciliation.receipts_sales, currency)}</dd>
                <dt>Bank cash deposits</dt>
                <dd className="mono">{formatCurrency(f.cash_reconciliation.bank_cash_deposits, currency)}</dd>
              </dl>
            </Block>
          ) : null}

          {f.months_missing.length > 0 ? (
            <Block title="Months missing from statements" count={f.months_missing.length} tone="warn">
              <div className="ref-list">
                {f.months_missing.map((m) => (
                  <span key={m} className="chip chip-warn mono">
                    {formatMonth(m)}
                  </span>
                ))}
              </div>
            </Block>
          ) : null}

          {f.unsourced_figure_ids.length + f.unsourced_numerals.length > 0 ? (
            <Block title="Unsourced numbers" count={f.unsourced_figure_ids.length + f.unsourced_numerals.length} tone="bad">
              <ul className="plain-list">
                {f.unsourced_figure_ids.map((id) => (
                  <li key={id}>
                    Figure <span className="mono">{id}</span> has no source reference
                  </li>
                ))}
                {f.unsourced_numerals.map((u, i) => (
                  <li key={i}>
                    <span className="mono">{u.text}</span> in <em>{u.section}</em>
                    {u.context ? <span className="muted"> — “{u.context}”</span> : null}
                  </li>
                ))}
              </ul>
            </Block>
          ) : null}
        </div>
      )}
    </section>
  )
}

function ObjectionsSkeleton() {
  return (
    <div className="objections" aria-busy="true">
      <div className="panel objections-summary">
        <Skeleton w="40%" h={16} />
        <Skeleton w="100%" h={8} className="mt-3" radius={999} />
      </div>
      {Array.from({ length: 3 }, (_, i) => (
        <div key={i} className="objection sev-stripe-low">
          <div className="skeleton-inline">
            <Skeleton w={60} h={18} radius={999} />
            <Skeleton w={120} h={18} radius={999} />
          </div>
          <Skeleton w="70%" h={16} className="mt-3" />
          <SkeletonText lines={2} className="mt-2" />
        </div>
      ))}
    </div>
  )
}
