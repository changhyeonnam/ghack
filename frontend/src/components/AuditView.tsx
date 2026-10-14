import { useCallback, useEffect, useState } from 'react'
import { errorMessage, getAudit, getTraces, optional } from '../api'
import { auditEventTitle, formatCost, formatDateTime, formatDuration, formatNumber, formatUsd } from '../format'
import type { AgentTrace, AuditEntry } from '../types'
import { EmptyState, Skeleton, Spinner } from './Badges'
import { Icon, type IconName } from './Icons'
import { useToast } from './Toast'

interface Props {
  caseId: string
  /** Bumped by the parent whenever the case changes, to refetch. */
  refreshKey: string
}

type ActorKind = 'system' | 'agent' | 'tool' | 'underwriter' | 'other'

function actorKind(actor: string): ActorKind {
  const head = actor.split(':')[0] ?? ''
  if (head === 'system') return 'system'
  if (head === 'agent') return 'agent'
  if (head === 'tool') return 'tool'
  if (head === 'underwriter' || head === 'human' || head === 'user') return 'underwriter'
  return 'other'
}

const ACTOR_ICON: Record<ActorKind, IconName> = {
  system: 'cpu',
  agent: 'bolt',
  tool: 'tool',
  underwriter: 'pen',
  other: 'user',
}

function actorLabel(actor: string): string {
  const [head, tail] = actor.split(':')
  if (!tail) return head === 'system' ? 'System' : (head ?? actor)
  if (head === 'agent') return `${tail.charAt(0).toUpperCase()}${tail.slice(1)} agent`
  if (head === 'tool') return `${tail.replace(/_/g, ' ')} tool`
  return actor
}

export function AuditView({ caseId, refreshKey }: Props) {
  const toast = useToast()
  const [audit, setAudit] = useState<AuditEntry[] | null>(null)
  const [traces, setTraces] = useState<AgentTrace[] | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [a, t] = await Promise.all([optional(getAudit(caseId)), optional(getTraces(caseId))])
      setAudit(a ?? [])
      setTraces(t ?? [])
    } catch (e) {
      toast.error(`Could not load audit: ${errorMessage(e)}`)
    } finally {
      setLoading(false)
    }
  }, [caseId, toast])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  if (loading && !audit) return <AuditSkeleton />

  const totals = (traces ?? []).reduce(
    (acc, t) => ({
      inTok: acc.inTok + t.input_tokens,
      outTok: acc.outTok + t.output_tokens,
      cost: acc.cost + t.cost_usd,
      cached: acc.cached + (t.cached ? 1 : 0),
      errors: acc.errors + (t.status === 'error' ? 1 : 0),
    }),
    { inTok: 0, outTok: 0, cost: 0, cached: 0, errors: 0 },
  )

  return (
    <div className="audit">
      <section className="panel">
        <div className="panel-head">
          <h3 className="panel-title">Audit timeline</h3>
          <button className="btn btn-ghost btn-sm" onClick={() => void load()} disabled={loading}>
            {loading ? <Spinner small /> : <Icon name="refresh" size={14} />} Refresh
          </button>
        </div>
        {!audit || audit.length === 0 ? (
          <EmptyState icon="clock" title="No audit entries yet" hint="Every agent call and underwriter action is logged here." />
        ) : (
          <ol className="timeline">
            {[...audit].reverse().map((e) => {
              const kind = actorKind(e.actor)
              const hasDetails = Object.keys(e.details).length > 0
              return (
                <li key={e.id} className={`tl-item actor-${kind}`}>
                  <span className={`tl-avatar avatar-${kind}`} aria-hidden="true">
                    <Icon name={ACTOR_ICON[kind]} size={13} />
                  </span>
                  <div className="tl-body">
                    <div className="tl-head">
                      <span className="tl-event">{auditEventTitle(e.event, e.details)}</span>
                      <span className="tl-actor">{actorLabel(e.actor)}</span>
                      <span className="tl-time mono tip tip-left" data-tip={e.at}>
                        {formatDateTime(e.at)}
                      </span>
                    </div>
                    <DetailSummary details={e.details} />
                    {hasDetails ? (
                      <details className="tl-details">
                        <summary>
                          <Icon name="chevron-right" size={11} className="summary-chev" />
                          Details
                        </summary>
                        <pre className="mono-block">{JSON.stringify(e.details, null, 2)}</pre>
                      </details>
                    ) : null}
                  </div>
                </li>
              )
            })}
          </ol>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3 className="panel-title">LLM traces</h3>
          {traces && traces.length > 0 ? (
            <span className="muted small">
              {traces.length} call{traces.length === 1 ? '' : 's'} · {totals.cached} cached · {formatNumber(totals.inTok)} in / {formatNumber(totals.outTok)} out ·{' '}
              <span className="mono">{formatCost(totals.cost)}</span>
              {totals.errors > 0 ? <span className="bad"> · {totals.errors} error{totals.errors === 1 ? '' : 's'}</span> : null}
            </span>
          ) : null}
        </div>
        {!traces || traces.length === 0 ? (
          <EmptyState icon="bolt" title="No LLM calls recorded" hint="Run a pipeline stage to see model, prompt version, tokens and cost per call." />
        ) : (
          <div className="table-scroll table-sticky">
            <table className="table zebra compact">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Model</th>
                  <th>Prompt</th>
                  <th className="num">In</th>
                  <th className="num">Out</th>
                  <th className="num">Think</th>
                  <th className="num">Cost</th>
                  <th className="num">Duration</th>
                  <th>Status</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {traces.map((t) => (
                  <tr key={t.id} className={t.status === 'error' ? 'row-bad' : ''}>
                    <td>{t.agent}</td>
                    <td className="mono small">{t.model}</td>
                    <td className="mono small">{t.prompt_version}</td>
                    <td className="num mono">{formatNumber(t.input_tokens)}</td>
                    <td className="num mono">{formatNumber(t.output_tokens)}</td>
                    <td className="num mono">{formatNumber(t.thinking_tokens)}</td>
                    <td className="num mono">{t.cost_usd === 0 ? <span className="muted">—</span> : formatUsd(t.cost_usd, 4)}</td>
                    <td className="num mono">{formatDuration(t.duration_ms)}</td>
                    <td>
                      <span className="status-cell">
                        {t.cached ? (
                          <span className="chip chip-info tip" data-tip="Served from cache">
                            <Icon name="bolt" size={10} />
                          </span>
                        ) : null}
                        {t.status === 'error' ? (
                          <span className="chip chip-bad" title={t.error ?? ''}>
                            error
                          </span>
                        ) : (
                          <span className="chip chip-success">ok</span>
                        )}
                      </span>
                    </td>
                    <td className="mono small">{formatDateTime(t.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

/** One-line human summary for common detail shapes; falls back to nothing (the JSON is in the disclosure). */
function DetailSummary({ details }: { details: Record<string, unknown> }) {
  const parts: string[] = []
  const take = (k: string, fmt: (v: unknown) => string | null) => {
    if (k in details) {
      const s = fmt(details[k])
      if (s) parts.push(s)
    }
  }
  take('seconds', (v) => (typeof v === 'number' ? formatDuration(v * 1000) : null))
  take('recommendation', (v) => (typeof v === 'string' ? v.replace(/_/g, ' ') : null))
  take('figures', (v) => (typeof v === 'number' ? `${v} figures` : null))
  take('unsourced', (v) => (typeof v === 'number' ? `${v} unsourced` : null))
  take('objections', (v) => (typeof v === 'number' ? `${v} objections` : null))
  take('documents', (v) => (typeof v === 'number' ? `${v} documents` : null))
  take('transactions', (v) => (typeof v === 'number' ? `${v} transactions` : null))
  take('months', (v) => (typeof v === 'number' ? `${v} months` : null))
  take('outcome', (v) => (typeof v === 'string' ? v.replace(/_/g, ' ') : null))
  take('status', (v) => (typeof v === 'string' ? v : null))
  take('objection_id', (v) => (typeof v === 'string' ? v : null))
  take('language', (v) => (typeof v === 'string' ? v : null))
  if (parts.length === 0) return null
  return <div className="tl-summary">{parts.join(' · ')}</div>
}

function AuditSkeleton() {
  return (
    <div className="audit" aria-busy="true">
      <div className="panel">
        <Skeleton w={120} h={14} />
        <ol className="timeline mt-4">
          {Array.from({ length: 4 }, (_, i) => (
            <li key={i} className="tl-item">
              <Skeleton w={26} h={26} radius={999} />
              <div className="tl-body">
                <Skeleton w="50%" h={12} />
                <Skeleton w="30%" h={10} className="mt-2" />
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}
