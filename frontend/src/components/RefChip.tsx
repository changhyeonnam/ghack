import type { SourceRef } from '../types'
import { Icon } from './Icons'
import { useViewer } from './viewerContext'

/** Clickable "filename · p.N" chip that opens the document viewer at that ref. */
export function RefChip({ r, label, index }: { r: SourceRef; label: string; index?: number }) {
  const viewer = useViewer()
  const name = viewer.docName(r.doc_id)
  const active =
    viewer.selection?.docId === r.doc_id &&
    viewer.selection?.page === r.page &&
    viewer.selection.highlights.some((h) => h.ref === r)
  return (
    <button
      type="button"
      className={`ref-chip${active ? ' active' : ''}`}
      onClick={() => viewer.openRef(r, label)}
      title={r.snippet ? `“${r.snippet}”` : `${name}, page ${r.page}`}
    >
      {index !== undefined ? <span className="ref-idx">{index}</span> : <Icon name="anchor" size={10} />}
      <span className="ref-doc truncate">{name}</span>
      <span className="ref-page mono">p.{r.page}</span>
      {!r.bbox ? (
        <span className="ref-nobbox tip" data-tip="No exact location on the page">
          <Icon name="file" size={10} />
        </span>
      ) : null}
    </button>
  )
}

export function RefList({ refs, label }: { refs: SourceRef[]; label: string }) {
  if (refs.length === 0) return <span className="muted small">No source references</span>
  return (
    <span className="ref-list">
      {refs.map((r, i) => (
        <RefChip key={`${r.doc_id}-${r.page}-${i}`} r={r} label={label} index={refs.length > 1 ? i + 1 : undefined} />
      ))}
    </span>
  )
}
