import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { countryFlag, countryName, formatCompact, formatCost, formatDateTime, formatDuration, formatTokens } from '../format'
import type { Case, ChallengeResult, Memo } from '../types'
import { RecommendationBadge, StatusBadge } from './Badges'
import { Icon } from './Icons'

interface Props {
  kase: Case
  memo: Memo | null
  challenge: ChallengeResult | null
  onExportMemo: () => void
  onOpenViewer?: () => void
}

export function CaseHeader({ kase, memo, challenge, onExportMemo, onOpenViewer }: Props) {
  const s = kase.stats
  const critical = challenge?.objections.filter((o) => o.severity === 'critical').length ?? 0
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [menuOpen])

  return (
    <header className="case-header">
      <div className="case-header-row">
        <Link to="/" className="back-link tip" data-tip="Back to portfolio" aria-label="Back to portfolio">
          <Icon name="arrow-left" />
        </Link>
        <div className="case-title-block">
          <div className="case-title-row">
            <h1 className="case-title">{kase.name}</h1>
            <StatusBadge status={kase.status} size="sm" />
            {kase.is_demo ? (
              <span className="tag tag-demo tip" data-tip="Demo case prepared for this showcase; not a real applicant">
                Demo
              </span>
            ) : null}
          </div>
          <div className="case-sub">
            <span className="case-sub-item">{kase.business_name}</span>
            <span className="case-sub-sep" aria-hidden="true" />
            <span className="case-sub-item">
              <span aria-hidden="true">{countryFlag(kase.country)}</span> {countryName(kase.country)}
            </span>
            {kase.sector ? (
              <>
                <span className="case-sub-sep" aria-hidden="true" />
                <span className="case-sub-item">{kase.sector}</span>
              </>
            ) : null}
            {kase.requested_amount ? (
              <>
                <span className="case-sub-sep" aria-hidden="true" />
                <span className="case-sub-item">
                  Requesting <span className="mono">{formatCompact(kase.requested_amount, kase.currency)}</span>
                </span>
              </>
            ) : null}
          </div>
        </div>

        <div className="case-header-right">
          {kase.decision ? (
            <div className="decision-summary tip tip-left" data-tip={`Signed by ${kase.decision.underwriter} · ${formatDateTime(kase.decision.decided_at)}`}>
              <span className="decision-summary-label">Decision</span>
              <RecommendationBadge value={kase.decision.outcome} />
            </div>
          ) : memo ? (
            <div className="decision-summary tip tip-left" data-tip={`Analyst recommendation · memo v${memo.version}`}>
              <span className="decision-summary-label">Recommended</span>
              <RecommendationBadge value={memo.draft.recommendation} />
            </div>
          ) : null}
          {onOpenViewer ? (
            <button className="btn btn-secondary btn-sm" onClick={onOpenViewer}>
              <Icon name="eye" /> Viewer
            </button>
          ) : null}
          <button className="btn btn-secondary btn-sm" onClick={onExportMemo} disabled={!memo}>
            <Icon name="print" /> Export memo
          </button>
          <div className="menu-anchor" ref={menuRef}>
            <button
              className={`icon-btn${menuOpen ? ' active' : ''}`}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="More actions"
              onClick={() => setMenuOpen((v) => !v)}
            >
              <Icon name="more" />
            </button>
            {menuOpen ? (
              <div className="menu" role="menu">
                <button role="menuitem" className="menu-item" onClick={() => { setMenuOpen(false); onExportMemo() }} disabled={!memo}>
                  <Icon name="print" /> Export memo (PDF)
                </button>
                <button
                  role="menuitem"
                  className="menu-item"
                  onClick={() => {
                    setMenuOpen(false)
                    void navigator.clipboard?.writeText(kase.id)
                  }}
                >
                  <Icon name="copy" /> Copy case ID
                </button>
                <div className="menu-sep" />
                <div className="menu-meta mono">{kase.id}</div>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="stats-strip" aria-label="Case statistics">
        <StatItem tip="Figures in the memo catalog with a source location or computation">
          Figures <strong className="mono">{s.n_figures}</strong>
        </StatItem>
        <StatItem tip={s.n_unsourced === 0 ? 'Every number in the memo links back to evidence' : 'Numbers in the memo that lack a source'} tone={s.n_unsourced === 0 ? 'good' : 'bad'}>
          Unsourced <strong className="mono">{s.n_unsourced}</strong>
          {s.n_unsourced === 0 ? <Icon name="check" size={12} /> : <Icon name="alert" size={12} />}
        </StatItem>
        <StatItem tip="Objections raised by the challenger agent">
          Objections <strong className="mono">{s.n_objections}</strong>
          {critical > 0 ? <span className="stat-sub">({critical} critical)</span> : null}
        </StatItem>
        <StatItem tip="Total pipeline processing time">
          <strong className="mono">{formatDuration(s.processing_seconds * 1000)}</strong>
        </StatItem>
        <StatItem tip={`LLM spend for this case · ${formatTokens(s.total_tokens)} tokens`}>
          <strong className="mono">{formatCost(s.total_cost_usd)}</strong>
        </StatItem>
        <StatItem tip={`${s.n_llm_calls} model calls${s.n_cached_calls ? `, ${s.n_cached_calls} served from cache` : ''}`}>
          <strong className="mono">{s.n_llm_calls}</strong> calls
          {s.n_cached_calls ? <span className="stat-sub">({s.n_cached_calls} cached)</span> : null}
        </StatItem>
      </div>
    </header>
  )
}

function StatItem({ children, tip, tone }: { children: ReactNode; tip: string; tone?: 'good' | 'bad' }) {
  return (
    <span className={`stat-item tip${tone ? ` stat-${tone}` : ''}`} data-tip={tip}>
      {children}
    </span>
  )
}
