// Typed fetch helpers for every endpoint in docs/API.md.
// All paths are relative (/api/...) so the same build works behind the Vite proxy,
// FastAPI static serving, and Firebase Hosting rewrites.

import type {
  AgentTrace,
  AuditEntry,
  Benchmark,
  Case,
  CaseCreate,
  CashflowSummary,
  ChallengeResult,
  CustomerLetter,
  DecisionRequest,
  DocumentExtraction,
  FeedbackPriorities,
  Health,
  IntakeResult,
  LetterRequest,
  Memo,
  ResolutionRequest,
  StageName,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Fired when the API reports that live AI analysis is paused (budget cap or provider billing limit). */
export const AI_LIMIT_EVENT = 'ledgerlens:ai-limit'

/** True when the case was created in another browser and shared with everyone (read-only here). */
export function isSharedFromOthers(c: { workspace?: string | null }): boolean {
  return Boolean(c.workspace) && c.workspace !== workspaceId()
}

// Each browser gets its own copy of the demo cases, so one reviewer signing a case does not lock it for the next.
const WORKSPACE_KEY = 'ledgerlens.workspace'
let memoryWorkspace = ''

function newWorkspaceId(): string {
  const bytes = new Uint8Array(12)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

export function workspaceId(): string {
  try {
    let id = localStorage.getItem(WORKSPACE_KEY)
    if (!id) {
      id = newWorkspaceId()
      localStorage.setItem(WORKSPACE_KEY, id)
    }
    return id
  } catch {
    // Storage blocked (private mode, sandbox): keep one id for this page load.
    memoryWorkspace ||= newWorkspaceId()
    return memoryWorkspace
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('X-LedgerLens-Workspace', workspaceId())
  const res = await fetch(path, { ...init, headers })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (body && body.detail !== undefined) {
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      // Non-JSON error body; keep the status text.
    }
    if (res.status === 402) window.dispatchEvent(new CustomEvent(AI_LIMIT_EVENT))
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function json<T>(path: string, method: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

// ---- Health ----
export const getHealth = () => request<Health>('/api/health')

// ---- Cases ----
export const listCases = () => request<Case[]>('/api/cases')
export const createCase = (body: CaseCreate) => json<Case>('/api/cases', 'POST', body)
export const getCase = (caseId: string) => request<Case>(`/api/cases/${encodeURIComponent(caseId)}`)
export const deleteCase = (caseId: string) =>
  json<{ deleted: boolean }>(`/api/cases/${encodeURIComponent(caseId)}`, 'DELETE')

// ---- Documents ----
export function uploadDocuments(caseId: string, files: File[]): Promise<Case> {
  const form = new FormData()
  for (const f of files) form.append('files', f, f.name)
  return request<Case>(`/api/cases/${encodeURIComponent(caseId)}/documents`, { method: 'POST', body: form })
}
export const deleteDocument = (caseId: string, docId: string) =>
  json<Case>(`/api/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(docId)}`, 'DELETE')
export const documentFileUrl = (caseId: string, docId: string) =>
  `/api/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(docId)}/file`
export const documentPageUrl = (caseId: string, docId: string, page: number, scale: 1 | 2 = 1) =>
  `/api/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(docId)}/pages/${page}?scale=${scale}`

// ---- Pipeline ----
export const runStage = (caseId: string, stage: StageName | 'all') =>
  json<Case>(`/api/cases/${encodeURIComponent(caseId)}/run?stage=${stage}`, 'POST')

// ---- Artifacts (404 "not ready" until the stage has run) ----
export const getIntake = (caseId: string) => request<IntakeResult>(`/api/cases/${encodeURIComponent(caseId)}/intake`)
export const getExtractions = (caseId: string) =>
  request<DocumentExtraction[]>(`/api/cases/${encodeURIComponent(caseId)}/extractions`)
export const getCashflow = (caseId: string) =>
  request<CashflowSummary>(`/api/cases/${encodeURIComponent(caseId)}/cashflow`)
export const getMemo = (caseId: string) => request<Memo>(`/api/cases/${encodeURIComponent(caseId)}/memo`)
export const getChallenge = (caseId: string) =>
  request<ChallengeResult>(`/api/cases/${encodeURIComponent(caseId)}/challenge`)
export const getLetter = (caseId: string) => request<CustomerLetter>(`/api/cases/${encodeURIComponent(caseId)}/letter`)
export const getAudit = (caseId: string) => request<AuditEntry[]>(`/api/cases/${encodeURIComponent(caseId)}/audit`)
export const getTraces = (caseId: string) => request<AgentTrace[]>(`/api/cases/${encodeURIComponent(caseId)}/traces`)

// ---- Underwriter actions ----
export const resolveObjection = (caseId: string, objectionId: string, body: ResolutionRequest) =>
  json<Case>(
    `/api/cases/${encodeURIComponent(caseId)}/objections/${encodeURIComponent(objectionId)}/resolution`,
    'POST',
    body,
  )
export const signDecision = (caseId: string, body: DecisionRequest) =>
  json<Case>(`/api/cases/${encodeURIComponent(caseId)}/decision`, 'POST', body)
export const generateLetter = (caseId: string, body: LetterRequest) =>
  json<CustomerLetter>(`/api/cases/${encodeURIComponent(caseId)}/letter`, 'POST', body)

// ---- Feedback loop & misc ----
export const getFeedbackPriorities = () => request<FeedbackPriorities>('/api/feedback/priorities')
export const getBenchmark = () => request<Benchmark>('/api/benchmark/latest')
export const seedDemo = (force = false) => json<{ cases: string[] }>(`/api/demo/seed${force ? '?force=true' : ''}`, 'POST')

/** Resolve an optional artifact: returns null on 404 ("not ready"), rethrows anything else. */
export async function optional<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message
  if (e instanceof Error) return e.message
  return String(e)
}
