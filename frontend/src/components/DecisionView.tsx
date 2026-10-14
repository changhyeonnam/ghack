import { useEffect, useState, type FormEvent } from 'react'
import { errorMessage, generateLetter, getLetter, optional, signDecision } from '../api'
import { formatDateTime, languageName, modelDisplayName } from '../format'
import type { Case, ChallengeResult, CustomerLetter, Memo, Recommendation } from '../types'
import { RECOMMENDATIONS } from '../types'
import { REC_DESCRIPTION, RecommendationBadge, Skeleton, Spinner, recommendationLabel } from './Badges'
import { Icon } from './Icons'
import { useToast } from './Toast'

interface Props {
  kase: Case
  memo: Memo | null
  challenge: ChallengeResult | null
  onCaseUpdate: (c: Case) => void
}

export function DecisionView({ kase, memo, challenge, onCaseUpdate }: Props) {
  const toast = useToast()
  const decision = kase.decision
  const [outcome, setOutcome] = useState<Recommendation>(memo?.draft.recommendation ?? 'hold')
  const [conditions, setConditions] = useState<string[]>(memo?.draft.conditions ?? [])
  const [rationale, setRationale] = useState(memo?.draft.rationale ?? '')
  const [underwriter, setUnderwriter] = useState('demo-underwriter')
  const [signing, setSigning] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [prefilledFrom, setPrefilledFrom] = useState<string | null>(null)

  const [letter, setLetter] = useState<CustomerLetter | null>(null)
  const [letterLoading, setLetterLoading] = useState(false)
  const [letterLang, setLetterLang] = useState(kase.language || 'en')
  const [generating, setGenerating] = useState(false)
  const [copied, setCopied] = useState(false)

  // Prefill once from the memo when it becomes available (do not clobber edits).
  useEffect(() => {
    if (!memo || decision) return
    const key = `${memo.case_id}:${memo.version}`
    if (prefilledFrom === key) return
    setOutcome(memo.draft.recommendation)
    setConditions(memo.draft.conditions)
    setRationale(memo.draft.rationale)
    setPrefilledFrom(key)
  }, [memo, decision, prefilledFrom])

  useEffect(() => {
    if (!decision) return
    let cancelled = false
    setLetterLoading(true)
    optional(getLetter(kase.id))
      .then((l) => {
        if (!cancelled) setLetter(l)
      })
      .catch((e) => toast.error(`Could not load letter: ${errorMessage(e)}`))
      .finally(() => {
        if (!cancelled) setLetterLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [decision, kase.id, toast])

  useEffect(() => {
    if (!confirming) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setConfirming(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [confirming])

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!rationale.trim()) {
      toast.error('A rationale is required to sign the decision')
      return
    }
    setConfirming(true)
  }

  async function onSign() {
    setSigning(true)
    try {
      const c = await signDecision(kase.id, {
        outcome,
        conditions: conditions.map((s) => s.trim()).filter(Boolean),
        rationale: rationale.trim(),
        underwriter: underwriter.trim() || 'demo-underwriter',
      })
      onCaseUpdate(c)
      setConfirming(false)
      toast.success('Decision signed and logged')
    } catch (err) {
      toast.error(`Could not sign decision: ${errorMessage(err)}`)
    } finally {
      setSigning(false)
    }
  }

  async function onGenerateLetter() {
    setGenerating(true)
    try {
      setLetter(await generateLetter(kase.id, { language: letterLang }))
      toast.success('Customer letter generated')
    } catch (err) {
      toast.error(`Could not generate letter: ${errorMessage(err)}`)
    } finally {
      setGenerating(false)
    }
  }

  async function onCopyLetter() {
    if (!letter) return
    const text = [letter.subject, '', letter.body, '', ...(letter.next_steps.length ? ['Next steps:', ...letter.next_steps.map((s, i) => `${i + 1}. ${s}`)] : [])].join('\n')
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy to clipboard')
    }
  }

  const resolutions = kase.objection_resolutions
  const accepted = resolutions.filter((r) => r.status === 'accepted').length
  const dismissed = resolutions.filter((r) => r.status === 'dismissed').length
  const objectionsTotal = kase.stats.n_objections
  const open = Math.max(0, objectionsTotal - accepted - dismissed)
  const resolvedById = new Map(resolutions.map((r) => [r.objection_id, r.status]))
  const openCritical = (challenge?.objections ?? []).filter((o) => o.severity === 'critical' && (resolvedById.get(o.id) ?? 'open') === 'open').length

  if (!decision) {
    return (
      <>
        <form className="decision" onSubmit={onSubmit}>
          <section className="panel">
            <div className="panel-head">
              <h3 className="panel-title">Decision</h3>
              <span className="muted small">Written to the audit log and used to re-weight the challenger's checklist.</span>
            </div>

            {memo ? (
              <div className="decision-context">
                <span>
                  Analyst recommended <RecommendationBadge value={memo.draft.recommendation} />
                </span>
              </div>
            ) : (
              <div className="callout callout-warn small">
                <Icon name="info" size={14} />
                <span>No memo yet. You can still record a decision, but consider running Analyze and Challenge first.</span>
              </div>
            )}

            <fieldset className="field-group">
              <legend className="field-label">Outcome</legend>
              <div className="radio-cards" role="radiogroup">
                {RECOMMENDATIONS.map((r) => (
                  <label key={r} className={`radio-card rec-card-${r}${outcome === r ? ' selected' : ''}`}>
                    <input type="radio" name="outcome" value={r} checked={outcome === r} onChange={() => setOutcome(r)} />
                    <span className="radio-dot" aria-hidden="true" />
                    <span className="radio-text">
                      <span className="radio-title">{recommendationLabel(r)}</span>
                      <span className="radio-desc">{REC_DESCRIPTION[r]}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="field-group">
              <div className="field-label-row">
                <span className="field-label">Conditions</span>
                <span className="muted small">{conditions.length === 0 ? 'None' : `${conditions.length} condition${conditions.length === 1 ? '' : 's'}`}</span>
              </div>
              <ul className="cond-list">
                {conditions.map((c, i) => (
                  <li key={i} className="cond-row">
                    <span className="cond-num mono">{i + 1}</span>
                    <input value={c} onChange={(e) => setConditions((xs) => xs.map((x, j) => (j === i ? e.target.value : x)))} placeholder="Condition" />
                    <button type="button" className="icon-btn tip tip-left" data-tip="Remove" aria-label="Remove condition" onClick={() => setConditions((xs) => xs.filter((_, j) => j !== i))}>
                      <Icon name="x" size={14} />
                    </button>
                  </li>
                ))}
              </ul>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConditions((xs) => [...xs, ''])}>
                <Icon name="plus" size={14} /> Add condition
              </button>
            </div>

            <div className="form-grid">
              <label className="field span-2">
                <span className="field-label">Rationale</span>
                <textarea rows={6} value={rationale} onChange={(e) => setRationale(e.target.value)} required placeholder="Why this outcome, in the underwriter's own words." />
              </label>
              <label className="field">
                <span className="field-label">Underwriter</span>
                <input value={underwriter} onChange={(e) => setUnderwriter(e.target.value)} placeholder="Your name or id" />
              </label>
            </div>

            <div className="objection-summary">
              <span className="field-label">Objections</span>
              {objectionsTotal === 0 ? (
                <span className="muted small">No objections were raised.</span>
              ) : (
                <div className="resolution-counts">
                  <span className="res-count res-count-accepted">
                    <Icon name="check" size={11} />
                    <span className="mono">{accepted}</span> accepted
                  </span>
                  <span className="res-count res-count-dismissed">
                    <Icon name="x" size={11} />
                    <span className="mono">{dismissed}</span> dismissed
                  </span>
                  <span className={`res-count res-count-open${open > 0 ? ' is-open' : ''}`}>
                    <span className="mono">{open}</span> open
                  </span>
                </div>
              )}
              {openCritical > 0 ? (
                <div className="callout callout-bad small">
                  <Icon name="alert" size={14} />
                  <span>
                    {openCritical} critical objection{openCritical === 1 ? ' is' : 's are'} still open. Resolve {openCritical === 1 ? 'it' : 'them'} on the Objections tab or
                    explain in the rationale.
                  </span>
                </div>
              ) : null}
            </div>

            <div className="form-actions">
              <button type="submit" className={`btn btn-primary rec-btn-${outcome}`} disabled={signing}>
                <Icon name="pen" /> Sign decision
              </button>
              <span className="muted small">Signing is final for this case.</span>
            </div>
          </section>
        </form>

        {confirming ? (
          <div className="modal-scrim" onClick={() => !signing && setConfirming(false)}>
            <div className="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onClick={(e) => e.stopPropagation()}>
              <h3 id="confirm-title" className="modal-title">
                Sign this decision?
              </h3>
              <p className="modal-text">
                You are about to record <RecommendationBadge value={outcome} /> for <strong>{kase.business_name}</strong>
                {conditions.filter((c) => c.trim()).length > 0 ? ` with ${conditions.filter((c) => c.trim()).length} condition${conditions.filter((c) => c.trim()).length === 1 ? '' : 's'}` : ''}.
                This is written to the audit log and cannot be edited afterwards.
              </p>
              {openCritical > 0 ? (
                <div className="callout callout-bad small">
                  <Icon name="alert" size={14} />
                  <span>
                    {openCritical} critical objection{openCritical === 1 ? '' : 's'} still open.
                  </span>
                </div>
              ) : null}
              <div className="modal-actions">
                <button className="btn btn-secondary" onClick={() => setConfirming(false)} disabled={signing}>
                  Cancel
                </button>
                <button className={`btn btn-primary rec-btn-${outcome}`} onClick={() => void onSign()} disabled={signing} autoFocus>
                  {signing ? <Spinner small /> : <Icon name="pen" />} Sign as {underwriter.trim() || 'demo-underwriter'}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </>
    )
  }

  return (
    <div className="decision">
      <section className={`panel decision-signed rec-edge-${decision.outcome}`}>
        <div className="panel-head">
          <div>
            <h3 className="panel-title">
              <Icon name="shield-check" size={16} /> Signed decision
            </h3>
            <div className="muted small">
              by <strong>{decision.underwriter}</strong> · {formatDateTime(decision.decided_at)}
            </div>
          </div>
          <RecommendationBadge value={decision.outcome} large />
        </div>
        {decision.conditions.length > 0 ? (
          <div className="field-group">
            <span className="field-label">Conditions</span>
            <ol className="cond-static">
              {decision.conditions.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ol>
          </div>
        ) : null}
        <div className="field-group">
          <span className="field-label">Rationale</span>
          <p className="prewrap">{decision.rationale}</p>
        </div>
        {decision.objection_resolutions.length > 0 ? (
          <div className="field-group">
            <span className="field-label">Objections at signing</span>
            <div className="resolution-counts">
              <span className="res-count res-count-accepted">
                <Icon name="check" size={11} />
                <span className="mono">{decision.objection_resolutions.filter((r) => r.status === 'accepted').length}</span> accepted
              </span>
              <span className="res-count res-count-dismissed">
                <Icon name="x" size={11} />
                <span className="mono">{decision.objection_resolutions.filter((r) => r.status === 'dismissed').length}</span> dismissed
              </span>
              <span className="res-count res-count-open">
                <span className="mono">{decision.objection_resolutions.filter((r) => r.status === 'open').length}</span> open
              </span>
            </div>
          </div>
        ) : null}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3 className="panel-title">Customer letter</h3>
          <div className="inline-form">
            <select value={letterLang} onChange={(e) => setLetterLang(e.target.value)} aria-label="Letter language">
              <option value="id">Indonesian</option>
              <option value="vi">Vietnamese</option>
              <option value="tl">Filipino</option>
              <option value="en">English</option>
            </select>
            <button className="btn btn-secondary btn-sm" onClick={() => void onGenerateLetter()} disabled={generating}>
              {generating ? <Spinner small /> : <Icon name={letter ? 'refresh' : 'spark'} size={14} />} {letter ? 'Regenerate' : 'Generate letter'}
            </button>
          </div>
        </div>
        <p className="muted small">A plain-language explanation of the outcome in the applicant's own language. Review before sending.</p>
        {letterLoading ? (
          <div className="paper">
            <Skeleton w="60%" h={16} />
            <Skeleton w="100%" h={12} className="mt-3" />
            <Skeleton w="95%" h={12} className="mt-2" />
            <Skeleton w="80%" h={12} className="mt-2" />
          </div>
        ) : letter ? (
          <div className="paper">
            <div className="paper-head">
              <span className="muted small">
                {languageName(letter.language)} · {formatDateTime(letter.generated_at)} · <span className="tip" data-tip={letter.model}>{modelDisplayName(letter.model)}</span> ·{' '}
                <span className="mono">{letter.prompt_version}</span>
              </span>
              <button className="btn btn-ghost btn-sm" onClick={() => void onCopyLetter()}>
                <Icon name={copied ? 'check' : 'copy'} size={14} /> {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <div className="letter-subject">{letter.subject}</div>
            <div className="letter-body prewrap">{letter.body}</div>
            {letter.next_steps.length > 0 ? (
              <div className="letter-steps">
                <span className="field-label">Next steps</span>
                <ol className="cond-static">
                  {letter.next_steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="muted small">No letter generated yet.</p>
        )}
      </section>
    </div>
  )
}
