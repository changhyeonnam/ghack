import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import {
  errorMessage,
  getCase,
  getCashflow,
  getChallenge,
  getMemo,
  optional,
  resolveObjection,
  runStage,
  uploadDocuments,
} from '../api'
import { AuditView } from '../components/AuditView'
import { EmptyState, Skeleton } from '../components/Badges'
import { CaseHeader } from '../components/CaseHeader'
import { CashflowView } from '../components/CashflowView'
import { DecisionView } from '../components/DecisionView'
import { DocumentViewer } from '../components/DocumentViewer'
import { Icon } from '../components/Icons'
import { MemoView } from '../components/MemoView'
import { ObjectionsView } from '../components/ObjectionsView'
import { Pipeline } from '../components/Pipeline'
import { Crumbs } from '../components/Shell'
import { useBreakpoint } from '../components/theme'
import { useToast } from '../components/Toast'
import { ViewerContext, type ViewerApi, type ViewerSelection } from '../components/viewerContext'
import type { Case, CashflowSummary, ChallengeResult, Memo, ResolutionStatus, SourceRef, StageName } from '../types'
import { STAGE_ORDER } from '../types'

type Tab = 'memo' | 'objections' | 'cashflow' | 'decision' | 'audit'
const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'memo', label: 'Memo' },
  { id: 'objections', label: 'Objections' },
  { id: 'cashflow', label: 'Cashflow' },
  { id: 'decision', label: 'Decision' },
  { id: 'audit', label: 'Audit' },
]

const POLL_MS = 2000

function stageDone(c: Case | null, name: StageName): boolean {
  return c?.stages.find((s) => s.name === name)?.status === 'done'
}
function stageKey(c: Case | null, name: StageName): string {
  const s = c?.stages.find((x) => x.name === name)
  return s ? `${s.status}:${s.finished_at ?? ''}` : ''
}

export default function Workbench() {
  const { id = '' } = useParams()
  const toast = useToast()
  const bp = useBreakpoint()
  const [params, setParams] = useSearchParams()
  const tab = (TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : 'memo') as Tab
  const setTab = useCallback((t: Tab) => setParams({ tab: t }, { replace: true }), [setParams])

  const [kase, setKase] = useState<Case | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [running, setRunning] = useState<StageName | null>(null)
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null)
  const [runQueue, setRunQueue] = useState<StageName[]>([])
  const [runError, setRunError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [busyObjection, setBusyObjection] = useState<string | null>(null)

  const [memo, setMemo] = useState<Memo | null>(null)
  const [cashflow, setCashflow] = useState<CashflowSummary | null>(null)
  const [challenge, setChallenge] = useState<ChallengeResult | null>(null)
  const [artifactLoading, setArtifactLoading] = useState({ memo: false, cashflow: false, challenge: false })

  const [selection, setSelection] = useState<ViewerSelection | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const viewerRef = useRef<HTMLDivElement>(null)
  const nonce = useRef(0)

  // ---- Case loading & polling ----
  const refreshCase = useCallback(async () => {
    try {
      const c = await getCase(id)
      setKase(c)
      setLoadError(null)
      return c
    } catch (e) {
      setLoadError(errorMessage(e))
      return null
    }
  }, [id])

  useEffect(() => {
    setKase(null)
    setMemo(null)
    setCashflow(null)
    setChallenge(null)
    setSelection(null)
    void refreshCase()
  }, [refreshCase])

  const serverRunning = kase?.status === 'processing' || kase?.stages.some((s) => s.status === 'running')
  useEffect(() => {
    if (!running && !serverRunning) return
    const t = window.setInterval(() => void refreshCase(), POLL_MS)
    return () => window.clearInterval(t)
  }, [running, serverRunning, refreshCase])

  // Default viewer document once the case loads.
  useEffect(() => {
    if (kase && !selection && kase.documents.length > 0) {
      setSelection({ docId: kase.documents[0]!.doc_id, page: 1, highlights: [], nonce: 0 })
    }
  }, [kase, selection])

  // Close the slide-over when leaving the mid breakpoint.
  useEffect(() => {
    if (bp !== 'mid') setDrawerOpen(false)
  }, [bp])

  // ---- Artifacts: (re)load when the owning stage finishes ----
  const cashflowKey = stageKey(kase, 'cashflow')
  const analyzeKey = stageKey(kase, 'analyze')
  const challengeKey = stageKey(kase, 'challenge')

  useEffect(() => {
    if (!cashflowKey.startsWith('done:')) {
      setCashflow(null)
      return
    }
    let cancelled = false
    setArtifactLoading((s) => ({ ...s, cashflow: true }))
    optional(getCashflow(id))
      .then((v) => !cancelled && setCashflow(v))
      .catch((e) => toast.error(`Cashflow: ${errorMessage(e)}`))
      .finally(() => !cancelled && setArtifactLoading((s) => ({ ...s, cashflow: false })))
    return () => {
      cancelled = true
    }
  }, [id, cashflowKey, toast])

  useEffect(() => {
    if (!analyzeKey.startsWith('done:')) {
      setMemo(null)
      return
    }
    let cancelled = false
    setArtifactLoading((s) => ({ ...s, memo: true }))
    optional(getMemo(id))
      .then((v) => !cancelled && setMemo(v))
      .catch((e) => toast.error(`Memo: ${errorMessage(e)}`))
      .finally(() => !cancelled && setArtifactLoading((s) => ({ ...s, memo: false })))
    return () => {
      cancelled = true
    }
  }, [id, analyzeKey, toast])

  useEffect(() => {
    if (!challengeKey.startsWith('done:')) {
      setChallenge(null)
      return
    }
    let cancelled = false
    setArtifactLoading((s) => ({ ...s, challenge: true }))
    optional(getChallenge(id))
      .then((v) => !cancelled && setChallenge(v))
      .catch((e) => toast.error(`Challenge: ${errorMessage(e)}`))
      .finally(() => !cancelled && setArtifactLoading((s) => ({ ...s, challenge: false })))
    return () => {
      cancelled = true
    }
  }, [id, challengeKey, toast])

  // ---- Pipeline control ----
  const runStages = useCallback(
    async (stages: StageName[]) => {
      setRunError(null)
      setRunQueue(stages)
      setRunStartedAt(Date.now())
      for (const stage of stages) {
        setRunning(stage)
        try {
          const c = await runStage(id, stage)
          setKase(c)
          const st = c.stages.find((s) => s.name === stage)
          if (st?.status === 'failed') {
            setRunError(`${stage} failed: ${st.error ?? 'unknown error'}`)
            break
          }
        } catch (e) {
          const msg = `${stage} failed: ${errorMessage(e)}`
          setRunError(msg)
          toast.error(msg)
          await refreshCase()
          break
        }
      }
      setRunning(null)
      setRunQueue([])
      setRunStartedAt(null)
      await refreshCase()
    },
    [id, refreshCase, toast],
  )

  const pendingStages = useMemo(
    () => STAGE_ORDER.filter((s) => kase?.stages.find((x) => x.name === s)?.status !== 'done'),
    [kase],
  )

  const onRunNext = () => {
    const next = pendingStages[0]
    if (next) void runStages([next])
  }
  const onRunAll = () => {
    if (pendingStages.length > 0) void runStages(pendingStages)
  }
  const onRerun = (stage: StageName) => {
    // Re-running a stage re-runs it and everything after it.
    const idx = STAGE_ORDER.indexOf(stage)
    void runStages(STAGE_ORDER.slice(idx))
  }

  const onUpload = async (files: File[]) => {
    setUploading(true)
    try {
      setKase(await uploadDocuments(id, files))
      toast.success(`Uploaded ${files.length} file${files.length === 1 ? '' : 's'}`)
    } catch (e) {
      toast.error(`Upload failed: ${errorMessage(e)}`)
    } finally {
      setUploading(false)
    }
  }

  const onResolve = async (objectionId: string, status: ResolutionStatus) => {
    setBusyObjection(objectionId)
    try {
      setKase(await resolveObjection(id, objectionId, { status, by: 'demo-underwriter' }))
    } catch (e) {
      toast.error(`Could not update objection: ${errorMessage(e)}`)
    } finally {
      setBusyObjection(null)
    }
  }

  const onExportMemo = () => {
    if (tab !== 'memo') setTab('memo')
    window.setTimeout(() => window.print(), 200)
  }

  // ---- Viewer API ----
  const revealViewer = useCallback(() => {
    if (bp === 'mid') setDrawerOpen(true)
    else if (bp === 'narrow') viewerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [bp])

  const viewerApi = useMemo<ViewerApi>(() => {
    const documents = kase?.documents ?? []
    const docName = (docId: string) => documents.find((d) => d.doc_id === docId)?.filename ?? docId
    const openRefs = (refs: SourceRef[], label: string) => {
      if (refs.length === 0) return
      nonce.current += 1
      const first = refs[0]!
      setSelection({
        docId: first.doc_id,
        page: first.page || 1,
        highlights: refs.map((ref, i) => ({ ref, label, index: i + 1 })),
        nonce: nonce.current,
      })
      revealViewer()
    }
    return {
      caseId: id,
      documents,
      selection,
      docName,
      openRefs,
      openRef: (ref, label) => openRefs([ref], label),
      openDocument: (docId, page = 1) => {
        const doc = documents.find((d) => d.doc_id === docId)
        const clamped = Math.min(Math.max(1, page), doc?.pages ?? page)
        setSelection((prev) => ({
          docId,
          page: clamped,
          // Keep highlights when just paging within the same doc so the user can return to them.
          highlights: prev && prev.docId === docId ? prev.highlights : [],
          nonce: prev?.nonce ?? 0,
        }))
      },
    }
  }, [id, kase?.documents, selection, revealViewer])

  // ---- Render ----
  if (loadError && !kase) {
    return (
      <div className="page narrow">
        <Crumbs items={[{ label: 'Portfolio', to: '/' }, { label: 'Case' }]} />
        <EmptyState icon="alert-circle" title="Could not load case" hint={loadError} tone="bad" />
      </div>
    )
  }
  if (!kase) return <WorkbenchSkeleton />

  const refreshKey = `${kase.updated_at}|${kase.status}|${kase.stats.n_llm_calls}`
  const viewer = <DocumentViewer />

  return (
    <ViewerContext.Provider value={viewerApi}>
      <div className={`workbench bp-${bp}`}>
        <CaseHeader
          kase={kase}
          memo={memo}
          challenge={challenge}
          onExportMemo={onExportMemo}
          onOpenViewer={bp === 'mid' ? () => setDrawerOpen(true) : undefined}
        />
        <div className="wb-grid">
          <Pipeline
            kase={kase}
            running={running}
            runQueue={runQueue}
            runStartedAt={runStartedAt}
            runError={runError}
            onRunNext={onRunNext}
            onRunAll={onRunAll}
            onRerun={onRerun}
            onUpload={(files) => void onUpload(files)}
            uploading={uploading}
          />

          <main className="wb-center">
            <nav className="tabs" role="tablist">
              {TABS.map((t) => {
                let count: number | null = null
                if (t.id === 'objections' && challenge) count = challenge.objections.length
                return (
                  <button
                    key={t.id}
                    role="tab"
                    aria-selected={tab === t.id}
                    className={`tab${tab === t.id ? ' active' : ''}`}
                    onClick={() => setTab(t.id)}
                  >
                    {t.label}
                    {count !== null ? <span className="tab-count">{count}</span> : null}
                    {t.id === 'decision' && kase.decision ? (
                      <span className="tab-check">
                        <Icon name="check" size={12} />
                      </span>
                    ) : null}
                  </button>
                )
              })}
            </nav>
            <div className={`tab-panel panel-${tab}`}>
              {tab === 'memo' ? (
                <MemoView memo={memo} kase={kase} analyzeDone={stageDone(kase, 'analyze')} loading={artifactLoading.memo} />
              ) : null}
              {tab === 'objections' ? (
                <ObjectionsView
                  kase={kase}
                  challenge={challenge}
                  memo={memo}
                  challengeDone={stageDone(kase, 'challenge')}
                  loading={artifactLoading.challenge}
                  busyId={busyObjection}
                  onResolve={(oid, status) => void onResolve(oid, status)}
                />
              ) : null}
              {tab === 'cashflow' ? (
                <CashflowView cashflow={cashflow} cashflowDone={stageDone(kase, 'cashflow')} loading={artifactLoading.cashflow} />
              ) : null}
              {tab === 'decision' ? <DecisionView kase={kase} memo={memo} challenge={challenge} onCaseUpdate={setKase} /> : null}
              {tab === 'audit' ? <AuditView caseId={id} refreshKey={refreshKey} /> : null}
            </div>
          </main>

          {bp === 'mid' ? (
            <>
              <div className={`drawer-scrim${drawerOpen ? ' open' : ''}`} onClick={() => setDrawerOpen(false)} aria-hidden="true" />
              <aside className={`wb-right drawer${drawerOpen ? ' open' : ''}`} ref={viewerRef} aria-label="Document viewer" aria-hidden={!drawerOpen}>
                <button className="drawer-close icon-btn" onClick={() => setDrawerOpen(false)} aria-label="Close viewer">
                  <Icon name="x" />
                </button>
                {viewer}
              </aside>
            </>
          ) : (
            <aside className="wb-right" ref={viewerRef} aria-label="Document viewer">
              {viewer}
            </aside>
          )}
        </div>
      </div>
    </ViewerContext.Provider>
  )
}

function WorkbenchSkeleton() {
  return (
    <div className="workbench" aria-busy="true">
      <div className="case-header">
        <div className="case-header-row">
          <Skeleton w={240} h={20} />
          <Skeleton w={90} h={22} radius={999} />
        </div>
        <div className="stats-strip">
          <Skeleton w={360} h={12} />
        </div>
      </div>
      <div className="wb-grid">
        <aside className="rail">
          <div className="rail-section">
            <Skeleton w={80} h={12} />
            <div className="skeleton-stack">
              {Array.from({ length: 5 }, (_, i) => (
                <Skeleton key={i} h={32} />
              ))}
            </div>
          </div>
        </aside>
        <main className="wb-center">
          <div className="tabs">
            {TABS.map((t) => (
              <span key={t.id} className="tab">
                <Skeleton w={56} h={12} />
              </span>
            ))}
          </div>
          <div className="tab-panel">
            <div className="skeleton-stack">
              <Skeleton w="60%" h={24} />
              <Skeleton w="40%" h={12} />
              <div className="skeleton-row">
                {Array.from({ length: 4 }, (_, i) => (
                  <Skeleton key={i} h={64} />
                ))}
              </div>
              <Skeleton w="100%" h={12} />
              <Skeleton w="92%" h={12} />
              <Skeleton w="70%" h={12} />
            </div>
          </div>
        </main>
        <aside className="wb-right">
          <div className="viewer">
            <div className="viewer-toolbar">
              <Skeleton w="50%" h={28} />
            </div>
            <div className="viewer-stage">
              <Skeleton w="80%" h={320} />
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
