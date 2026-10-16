import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorMessage, getChallenge, isSharedFromOthers, listCases, optional, seedDemo } from '../api'
import { EmptyState, RecommendationBadge, Skeleton, Spinner, StageDots, StatusBadge, recommendationLabel } from '../components/Badges'
import { Icon } from '../components/Icons'
import { useToast } from '../components/Toast'
import { countryFlag, countryName, formatCompact, formatDateTime, formatRelative } from '../format'
import type { Case, CaseStatus, Severity } from '../types'

type Filter = 'all' | 'review' | 'challenged' | 'decided'

const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'review', label: 'In review' },
  { id: 'challenged', label: 'Challenged' },
  { id: 'decided', label: 'Decided' },
]

const REVIEW_STATUSES: CaseStatus[] = ['documents_uploaded', 'processing', 'memo_ready', 'challenged']

interface SeverityCounts {
  critical: number
  high: number
}

export default function CaseList() {
  const [cases, setCases] = useState<Case[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [seeding, setSeeding] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const [severities, setSeverities] = useState<Record<string, SeverityCounts>>({})
  const toast = useToast()
  const navigate = useNavigate()

  const refresh = useCallback(async () => {
    try {
      let list = await listCases()
      // First visit from this browser: prepare its own copy of the three demo cases so there is something to open.
      if (!list.some((c) => c.is_demo && c.workspace === 'you')) {
        await seedDemo()
        list = await listCases()
      }
      setCases(list)
    } catch (e) {
      toast.error(`Could not load cases: ${errorMessage(e)}`)
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // Severity breakdown per case is only available from the challenge artifact; fetch it lazily
  // for cases that have objections (bounded to keep the portfolio light).
  useEffect(() => {
    if (!cases) return
    const targets = cases.filter((c) => c.stats.n_objections > 0 && !(c.id in severities)).slice(0, 25)
    if (targets.length === 0) return
    let cancelled = false
    void Promise.all(
      targets.map(async (c) => {
        const ch = await optional(getChallenge(c.id)).catch(() => null)
        const counts: SeverityCounts = { critical: 0, high: 0 }
        for (const o of ch?.objections ?? []) {
          if (o.severity === 'critical') counts.critical++
          else if (o.severity === 'high') counts.high++
        }
        return [c.id, counts] as const
      }),
    ).then((pairs) => {
      if (cancelled) return
      setSeverities((prev) => {
        const next = { ...prev }
        for (const [id, counts] of pairs) next[id] = counts
        return next
      })
    })
    return () => {
      cancelled = true
    }
  }, [cases, severities])

  async function onSeed(force = false) {
    if (force && !window.confirm('Reset the three demo cases to their unprocessed state? Your decisions on them will be discarded.')) return
    setSeeding(true)
    try {
      const res = await seedDemo(force)
      toast.success(`${force ? 'Reset' : 'Loaded'} ${res.cases.length} demo case${res.cases.length === 1 ? '' : 's'}`)
      await refresh()
    } catch (e) {
      toast.error(`Demo seed failed: ${errorMessage(e)}`)
    } finally {
      setSeeding(false)
    }
  }

  const kpis = useMemo(() => {
    const list = cases ?? []
    let openObjections = 0
    let unsourced = 0
    for (const c of list) {
      const resolved = c.objection_resolutions.filter((r) => r.status !== 'open').length
      openObjections += Math.max(0, c.stats.n_objections - resolved)
      unsourced += c.stats.n_unsourced
    }
    return {
      inReview: list.filter((c) => REVIEW_STATUSES.includes(c.status)).length,
      decided: list.filter((c) => c.status === 'decided').length,
      openObjections,
      unsourced,
    }
  }, [cases])

  const visible = useMemo(() => {
    const list = cases ?? []
    const q = query.trim().toLowerCase()
    return list
      .filter((c) => {
        if (filter === 'review') return REVIEW_STATUSES.includes(c.status)
        if (filter === 'challenged') return c.status === 'challenged'
        if (filter === 'decided') return c.status === 'decided'
        return true
      })
      .filter((c) => {
        if (!q) return true
        return [c.name, c.business_name, c.sector, c.country, countryName(c.country), c.id].some((s) =>
          (s ?? '').toLowerCase().includes(q),
        )
      })
      .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
  }, [cases, filter, query])

  const counts = useMemo(() => {
    const list = cases ?? []
    return {
      all: list.length,
      review: list.filter((c) => REVIEW_STATUSES.includes(c.status)).length,
      challenged: list.filter((c) => c.status === 'challenged').length,
      decided: list.filter((c) => c.status === 'decided').length,
    }
  }, [cases])

  const hasCases = !!cases && cases.length > 0

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Portfolio</h1>
          <p className="page-sub">Applications under review. Every memo number traces back to a document; a challenger agent contests it before you sign.</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={() => onSeed()} disabled={seeding}>
            {seeding ? <Spinner small /> : <Icon name="layers" />} Load demo cases
          </button>
          {(cases ?? []).some((c) => c.is_demo) && (
            <button className="btn btn-secondary" onClick={() => onSeed(true)} disabled={seeding} title="Restore the demo cases to their unprocessed state">
              Reset demo
            </button>
          )}
          <button className="btn btn-primary" onClick={() => navigate('/cases/new')}>
            <Icon name="plus" /> New case
          </button>
        </div>
      </header>

      <section className="kpi-row" aria-label="Portfolio summary">
        <KpiTile label="Cases in review" value={kpis.inReview} loading={loading} icon="eye" />
        <KpiTile label="Decided" value={kpis.decided} loading={loading} icon="pen" />
        <KpiTile
          label="Open objections"
          value={kpis.openObjections}
          loading={loading}
          icon="alert-circle"
          tone={kpis.openObjections > 0 ? 'warn' : undefined}
        />
        <KpiTile
          label="Unsourced numbers"
          value={kpis.unsourced}
          loading={loading}
          icon="shield-check"
          tone={kpis.unsourced === 0 ? 'good' : 'bad'}
          hint={kpis.unsourced === 0 && hasCases ? 'Every memo number is sourced' : undefined}
        />
      </section>

      <section className="panel table-panel">
        <div className="toolbar">
          <div className="filter-chips" role="tablist" aria-label="Filter cases">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                role="tab"
                aria-selected={filter === f.id}
                className={`filter-chip${filter === f.id ? ' active' : ''}`}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
                <span className="filter-count">{counts[f.id]}</span>
              </button>
            ))}
          </div>
          <label className="search">
            <Icon name="search" size={14} />
            <input
              type="search"
              placeholder="Search applicant, business, sector…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search cases"
            />
          </label>
        </div>

        {loading ? (
          <TableSkeleton />
        ) : !hasCases ? (
          <EmptyState
            icon="layers"
            title="No cases yet"
            hint="Create a case and upload the applicant's documents, or load the three demo cases to explore the workbench."
            action={
              <>
                <button className="btn btn-secondary" onClick={() => onSeed()} disabled={seeding}>
                  {seeding ? <Spinner small /> : null} Load demo cases
                </button>
                <button className="btn btn-primary" onClick={() => navigate('/cases/new')}>
                  <Icon name="plus" /> New case
                </button>
              </>
            }
          />
        ) : visible.length === 0 ? (
          <EmptyState icon="search" title="No matching cases" hint="Try another filter or clear the search." />
        ) : (
          <div className="table-scroll">
            <table className="table case-table">
              <thead>
                <tr>
                  <th>Applicant</th>
                  <th>Country / sector</th>
                  <th className="num">Requested</th>
                  <th>Status</th>
                  <th>Pipeline</th>
                  <th>Objections</th>
                  <th>Decision / expected</th>
                  <th className="num">Updated</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => (
                  <CaseRow key={c.id} c={c} severity={severities[c.id]} onOpen={() => navigate(`/cases/${c.id}`)} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

function KpiTile({
  label,
  value,
  loading,
  tone,
  hint,
  icon,
}: {
  label: string
  value: number
  loading: boolean
  tone?: 'good' | 'bad' | 'warn'
  hint?: string
  icon: 'eye' | 'pen' | 'alert-circle' | 'shield-check'
}) {
  return (
    <div className={`kpi${tone ? ` kpi-${tone}` : ''}`}>
      <div className="kpi-head">
        <span className="kpi-label">{label}</span>
        <span className="kpi-icon">
          <Icon name={icon} size={14} />
        </span>
      </div>
      {loading ? <Skeleton w={56} h={28} /> : <div className="kpi-value mono">{value}</div>}
      {hint ? <div className="kpi-hint">{hint}</div> : null}
    </div>
  )
}

function CaseRow({ c, severity, onOpen }: { c: Case; severity: SeverityCounts | undefined; onOpen: () => void }) {
  const resolved = c.objection_resolutions.filter((r) => r.status !== 'open').length
  const open = Math.max(0, c.stats.n_objections - resolved)
  return (
    <tr
      className="row-link"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen()
        }
      }}
    >
      <td>
        <div className="applicant">
          <span className="applicant-flag" aria-hidden="true">
            {countryFlag(c.country)}
          </span>
          <div className="applicant-text">
            <div className="applicant-name">
              {c.name}
              {c.is_demo ? (
                <span className="tag tag-demo tip" data-tip="Demo case prepared for this showcase; not a real applicant">
                  Demo
                </span>
              ) : null}
              {isSharedFromOthers(c) ? (
                <span className="tag tag-shared tip" data-tip="Analysed by another visitor; you can open it read-only">
                  Shared
                </span>
              ) : null}
            </div>
            <div className="applicant-biz">{c.business_name}</div>
          </div>
        </div>
      </td>
      <td>
        <div className="cell-stack">
          <span>{countryName(c.country)}</span>
          <span className="muted small truncate" title={c.sector}>
            {c.sector || 'Sector not set'}
          </span>
        </div>
      </td>
      <td className="num mono">{c.requested_amount ? formatCompact(c.requested_amount, c.currency) : <span className="muted">—</span>}</td>
      <td>
        <StatusBadge status={c.status} size="sm" />
      </td>
      <td>
        <StageDots stages={c.stages} />
      </td>
      <td>
        <ObjectionCell total={c.stats.n_objections} open={open} severity={severity} />
      </td>
      <td>
        {c.decision ? (
          <RecommendationBadge value={c.decision.outcome} />
        ) : c.demo_expected_outcome ? (
          <span className="muted small tip" data-tip="Expected outcome defined for this demo case">
            Expected: {recommendationLabel(c.demo_expected_outcome)}
          </span>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
      <td className="num nowrap">
        <span className="muted small tip tip-left" data-tip={formatDateTime(c.updated_at)}>
          {formatRelative(c.updated_at)}
        </span>
      </td>
    </tr>
  )
}

function ObjectionCell({ total, open, severity }: { total: number; open: number; severity: SeverityCounts | undefined }) {
  if (total === 0) {
    return (
      <span className="muted small inline-icon">
        <Icon name="check" size={12} /> none
      </span>
    )
  }
  return (
    <div className="obj-cell">
      {severity ? (
        <>
          {severity.critical > 0 ? <SevCount sev="critical" n={severity.critical} /> : null}
          {severity.high > 0 ? <SevCount sev="high" n={severity.high} /> : null}
        </>
      ) : (
        <Skeleton w={28} h={18} radius={999} />
      )}
      <span className="muted small">
        {total} total{open > 0 ? ` · ${open} open` : ' · all resolved'}
      </span>
    </div>
  )
}

function SevCount({ sev, n }: { sev: Severity; n: number }) {
  return (
    <span className={`pill sev-${sev} tip`} data-tip={`${n} ${sev} objection${n === 1 ? '' : 's'}`}>
      {n}
    </span>
  )
}

function TableSkeleton() {
  return (
    <div className="table-skeleton" aria-hidden="true">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="table-skeleton-row">
          <Skeleton w="28%" h={14} />
          <Skeleton w="14%" h={14} />
          <Skeleton w="10%" h={14} />
          <Skeleton w="12%" h={18} radius={999} />
          <Skeleton w="12%" h={10} />
          <Skeleton w="10%" h={14} />
        </div>
      ))}
    </div>
  )
}
