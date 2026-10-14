import { useState } from 'react'
import { formatCurrency, formatDateTime } from '../format'
import type { Figure, Objection, ObjectionResolution, ResolutionStatus } from '../types'
import { QUESTION_TITLES } from '../types'
import { SeverityPill, Spinner } from './Badges'
import { Icon } from './Icons'
import { RefList } from './RefChip'
import { useViewer } from './viewerContext'

interface Props {
  objection: Objection
  resolution: ObjectionResolution | undefined
  currency: string
  figuresById: Map<string, Figure>
  busy: boolean
  onResolve: (status: ResolutionStatus) => void
}

export function ObjectionCard({ objection: o, resolution, currency, figuresById, busy, onResolve }: Props) {
  const [showTool, setShowTool] = useState(false)
  const viewer = useViewer()
  const status: ResolutionStatus = resolution?.status ?? 'open'
  const qTitle = QUESTION_TITLES[o.question_id] ?? 'Checklist question'
  const hasImpact = o.financial_impact !== null && o.financial_impact !== undefined

  return (
    <article className={`objection sev-stripe-${o.severity} res-${status}`} aria-labelledby={`obj-${o.id}`}>
      <header className="objection-head">
        <div className="objection-pills">
          <SeverityPill severity={o.severity} />
          <span className="pill pill-q tip" data-tip={qTitle}>
            {o.question_id}
            <span className="pill-q-title">{qTitle}</span>
          </span>
          {status !== 'open' ? (
            <span className={`pill res-pill-${status}`}>
              <Icon name={status === 'accepted' ? 'check' : 'x'} size={10} />
              {status}
            </span>
          ) : null}
        </div>
        <span className="mono muted small objection-id">{o.id}</span>
      </header>

      <h3 className="objection-title" id={`obj-${o.id}`}>
        {o.title}
      </h3>
      <p className="objection-claim">{o.claim}</p>

      <div className="objection-grid">
        {hasImpact ? (
          <div className="objection-field">
            <span className="field-k">Impact</span>
            <span className="mono objection-impact">{formatCurrency(o.financial_impact, currency)}</span>
          </div>
        ) : null}
        <div className="objection-field objection-field-wide">
          <span className="field-k">Evidence</span>
          <RefList refs={o.evidence_refs} label={o.title} />
        </div>
        {o.figure_ids.length > 0 ? (
          <div className="objection-field objection-field-wide">
            <span className="field-k">Figures</span>
            <span className="ref-list">
              {o.figure_ids.map((id) => {
                const f = figuresById.get(id)
                return (
                  <button
                    key={id}
                    type="button"
                    className="derived-chip"
                    disabled={!f || f.source_refs.length === 0}
                    onClick={() => f && viewer.openRefs(f.source_refs, f.label)}
                    title={f ? f.label : 'Figure not in memo catalog'}
                  >
                    <span className="mono">{id}</span>
                    {f ? <span className="derived-label truncate">{f.label}</span> : null}
                  </button>
                )
              })}
            </span>
          </div>
        ) : null}
      </div>

      <div className="callout callout-action">
        <Icon name="hand" size={14} />
        <div>
          <span className="callout-k">Suggested action</span>
          <span>{o.suggested_action}</span>
        </div>
      </div>

      {o.tool_evidence ? (
        <div className="tool-evidence">
          <button className="disclosure" onClick={() => setShowTool((v) => !v)} aria-expanded={showTool}>
            <Icon name="chevron-right" size={12} className={showTool ? 'rot-90' : ''} />
            <Icon name="tool" size={12} />
            Tool evidence
          </button>
          {showTool ? <pre className="mono-block">{o.tool_evidence}</pre> : null}
        </div>
      ) : null}

      <footer className="objection-actions">
        {status === 'open' ? (
          <div className="resolve-group" role="group" aria-label="Resolve objection">
            <button className="resolve-btn resolve-accept" disabled={busy} onClick={() => onResolve('accepted')}>
              {busy ? <Spinner small /> : <Icon name="check" size={14} />} Accept
            </button>
            <button className="resolve-btn resolve-dismiss" disabled={busy} onClick={() => onResolve('dismissed')}>
              {busy ? <Spinner small /> : <Icon name="x" size={14} />} Dismiss
            </button>
          </div>
        ) : (
          <>
            <span className="muted small resolved-by">
              <Icon name={status === 'accepted' ? 'check-circle' : 'eye-off'} size={13} />
              {status === 'accepted' ? 'Accepted' : 'Dismissed'}
              {resolution?.by ? ` by ${resolution.by}` : ''}
              {resolution?.at ? ` · ${formatDateTime(resolution.at)}` : ''}
            </span>
            <button className="link-btn" disabled={busy} onClick={() => onResolve('open')}>
              Reopen
            </button>
          </>
        )}
      </footer>
    </article>
  )
}
