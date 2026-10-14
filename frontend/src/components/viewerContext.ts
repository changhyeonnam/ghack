import { createContext, useContext } from 'react'
import type { DocumentMeta, SourceRef } from '../types'

export interface Highlight {
  ref: SourceRef
  /** Short label shown next to the box, e.g. the figure label or objection title. */
  label: string
  /** 1-based number drawn on the box when several refs are highlighted at once. */
  index: number
}

export interface ViewerSelection {
  docId: string
  page: number
  highlights: Highlight[]
  /** Changes on every selection so the pulse animation restarts. */
  nonce: number
}

export interface ViewerApi {
  caseId: string
  documents: DocumentMeta[]
  selection: ViewerSelection | null
  /** Open a document at a page with no highlight. */
  openDocument: (docId: string, page?: number) => void
  /** Open the first ref in the viewer and highlight all of them (those on the same page are drawn). */
  openRefs: (refs: SourceRef[], label: string) => void
  /** Convenience for a single ref. */
  openRef: (ref: SourceRef, label: string) => void
  docName: (docId: string) => string
}

export const ViewerContext = createContext<ViewerApi | null>(null)

export function useViewer(): ViewerApi {
  const ctx = useContext(ViewerContext)
  if (!ctx) throw new Error('useViewer must be used inside the Workbench')
  return ctx
}
