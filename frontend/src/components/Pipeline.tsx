import { useEffect, useRef, useState } from 'react'
import { docTypeLabel, durationBetween, formatBytes, formatDuration, languageName } from '../format'
import type { Case, StageName } from '../types'
import { STAGE_ORDER } from '../types'
import { DocIcon, QualityFlagIcons, Spinner } from './Badges'
import { Icon } from './Icons'
import { useViewer } from './viewerContext'

interface Props {
  kase: Case
  running: StageName | null
  runQueue: StageName[]
  runStartedAt: number | null
  runError: string | null
  onRunNext: () => void
  onRunAll: () => void
  onRerun: (stage: StageName) => void
  onUpload: (files: File[]) => void
  uploading: boolean
}

export const STAGE_LABEL: Record<StageName, string> = {
  intake: 'Intake',
  extract: 'Extract',
  cashflow: 'Cashflow',
  analyze: 'Analyze',
  challenge: 'Challenge',
}

const STAGE_HINT: Record<StageName, string> = {
  intake: 'Classify documents, detect language and quality issues',
  extract: 'Structured extraction with a source location for every value',
  cashflow: 'Deterministic monthly model (Python, not the LLM)',
  analyze: 'Analyst drafts the memo from catalog figures only',
  challenge: 'Second agent runs the 12-question checklist and tools',
}

function useElapsed(since: number | null): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (since === null) return
    setNow(Date.now())
    const t = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(t)
  }, [since])
  return since === null ? 0 : Math.max(0, now - since)
}

export function Pipeline({ kase, running, runQueue, runStartedAt, runError, onRunNext, onRunAll, onRerun, onUpload, uploading }: Props) {
  const viewer = useViewer()
  const fileInput = useRef<HTMLInputElement>(null)
  const nextStage = STAGE_ORDER.find((s) => kase.stages.find((x) => x.name === s)?.status !== 'done')
  const allDone = !nextStage
  const busy = running !== null
  const noDocs = kase.documents.length === 0
  const elapsed = useElapsed(runStartedAt)
  const decided = kase.status === 'decided'

  const doneCount = kase.stages.filter((s) => s.status === 'done').length
  const queueIdx = running ? runQueue.indexOf(running) : -1
  const progressPct = busy && runQueue.length > 0 ? ((queueIdx + 0.5) / runQueue.length) * 100 : (doneCount / STAGE_ORDER.length) * 100

  const primaryLabel = busy
    ? `Running ${STAGE_LABEL[running]}…`
    : allDone
      ? 'Re-run challenge'
      : nextStage
        ? `Run ${STAGE_LABEL[nextStage].toLowerCase()}`
        : 'Run next stage'
  const onPrimary = () => {
    if (busy) return
    if (allDone) onRerun('challenge')
    else onRunNext()
  }
  const remaining = STAGE_ORDER.length - doneCount

  return (
    <aside className="rail">
      <section className="rail-section">
        <div className="rail-head">
          <h2 className="rail-title">Pipeline</h2>
          <span className="muted small mono">
            {doneCount}/{STAGE_ORDER.length}
          </span>
        </div>

        <div className={`progress${busy ? ' is-running' : ''}`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progressPct)}>
          <div className="progress-bar" style={{ width: `${progressPct}%` }} />
        </div>
        {busy ? (
          <div className="progress-status">
            <Spinner small />
            <span>
              {STAGE_LABEL[running]}
              {runQueue.length > 1 ? <span className="muted"> · {queueIdx + 1} of {runQueue.length}</span> : null}
            </span>
            <span className="mono muted progress-timer">{formatDuration(elapsed)}</span>
          </div>
        ) : null}

        <ol className="stages">
          {STAGE_ORDER.map((name) => {
            const st = kase.stages.find((s) => s.name === name)
            const status = st?.status ?? 'pending'
            const isRunning = running === name || status === 'running'
            const queued = busy && !isRunning && runQueue.includes(name) && runQueue.indexOf(name) > queueIdx
            const cls = isRunning ? 'running' : queued ? 'queued' : status
            return (
              <li key={name} className={`stage stage-${cls}`}>
                <div
                  className="stage-row tip tip-right"
                  tabIndex={0}
                  data-tip={`${STAGE_HINT[name]}${status === 'failed' && st?.error ? ` — ${st.error}` : ''}`}
                  aria-label={`${STAGE_LABEL[name]}: ${cls}`}
                >
                  <span className="stage-icon" aria-hidden="true">
                    {isRunning ? (
                      <Spinner small />
                    ) : status === 'done' ? (
                      <Icon name="check" size={12} />
                    ) : status === 'failed' ? (
                      <Icon name="alert" size={12} />
                    ) : (
                      <span className="stage-dot" />
                    )}
                  </span>
                  <span className="stage-title">{STAGE_LABEL[name]}</span>
                  <span className="stage-meta">
                    {st?.cached ? (
                      <span className="stage-cached tip" data-tip="Served from cache">
                        <Icon name="bolt" size={11} />
                      </span>
                    ) : null}
                    {st?.started_at && !isRunning ? <span className="mono">{durationBetween(st.started_at, st.finished_at)}</span> : null}
                  </span>
                </div>
              </li>
            )
          })}
        </ol>

        {runError ? (
          <div className="callout callout-bad small">
            <Icon name="alert-circle" size={14} />
            <span>{runError}</span>
          </div>
        ) : null}

        <div className="rail-actions">
          <button className="btn btn-primary btn-block" onClick={onPrimary} disabled={busy || noDocs || decided}>
            {busy ? <Spinner small /> : allDone ? <Icon name="refresh" /> : <Icon name="play" />}
            {primaryLabel}
          </button>
          {!allDone ? (
            <button className="btn btn-secondary btn-block" onClick={onRunAll} disabled={busy || noDocs || decided}>
              Run all remaining
              <span className="btn-count">{remaining}</span>
            </button>
          ) : null}
        </div>
        {noDocs ? <p className="rail-note">Upload at least one document to start the pipeline.</p> : null}
        {decided ? <p className="rail-note">This case is decided. The pipeline is locked.</p> : null}
      </section>

      <section className="rail-section rail-docs">
        <div className="rail-head">
          <h2 className="rail-title">Documents</h2>
          <span className="muted small mono">{kase.documents.length}</span>
        </div>
        {kase.documents.length === 0 ? (
          <p className="rail-note">No documents yet.</p>
        ) : (
          <ul className="doc-list">
            {kase.documents.map((d) => {
              const active = viewer.selection?.docId === d.doc_id
              return (
                <li key={d.doc_id}>
                  <button
                    className={`doc-item${active ? ' active' : ''}`}
                    onClick={() => viewer.openDocument(d.doc_id, 1)}
                    title={`${d.filename}\n${docTypeLabel(d.doc_type)} · ${d.pages} page${d.pages === 1 ? '' : 's'} · ${formatBytes(d.size_bytes)}`}
                  >
                    <DocIcon mime={d.mime_type} />
                    <span className="doc-text">
                      <span className="doc-name truncate">{d.filename}</span>
                      <span className="doc-meta">
                        <span className={d.doc_type ? '' : 'muted'}>{docTypeLabel(d.doc_type)}</span>
                        <span className="doc-meta-sep" aria-hidden="true" />
                        <span className="mono">{d.pages}p</span>
                        {d.language ? (
                          <>
                            <span className="doc-meta-sep" aria-hidden="true" />
                            <span className="tip" data-tip={languageName(d.language)}>
                              {d.language.toUpperCase()}
                            </span>
                          </>
                        ) : null}
                      </span>
                    </span>
                    <QualityFlagIcons flags={d.quality_flags} />
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        <input
          ref={fileInput}
          type="file"
          multiple
          hidden
          accept=".pdf,.jpg,.jpeg,.png,.webp"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) onUpload(Array.from(e.target.files))
            e.target.value = ''
          }}
        />
        <button className="btn btn-ghost btn-sm btn-block add-docs" onClick={() => fileInput.current?.click()} disabled={uploading || busy || decided}>
          {uploading ? <Spinner small /> : <Icon name="plus" />} Add documents
        </button>
      </section>
    </aside>
  )
}
