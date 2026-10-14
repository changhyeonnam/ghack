import { formatFigure, humanize } from '../format'
import type { Figure } from '../types'
import { Icon } from './Icons'
import { useViewer } from './viewerContext'

interface Props {
  figure: Figure
  selected?: boolean
  onSelect: (figure: Figure) => void
  /** Larger tile for key-figure rows. */
  size?: 'inline' | 'card'
  /** Print footnote number. */
  footnote?: number
}

function isSourced(f: Figure): boolean {
  return f.source_refs.length > 0 || (f.origin !== 'document' && (f.derived_from.length > 0 || !!f.computation))
}

/** A number in the memo. Every chip is clickable and leads back to a document location. */
export function FigureChip({ figure, selected, onSelect, size = 'inline', footnote }: Props) {
  const viewer = useViewer()
  const sourced = isSourced(figure)
  const refs = figure.source_refs
  const refSummary =
    refs.length > 0
      ? refs
          .slice(0, 3)
          .map((r) => `${viewer.docName(r.doc_id)} p.${r.page}`)
          .join(', ') + (refs.length > 3 ? ` +${refs.length - 3}` : '')
      : figure.derived_from.length > 0
        ? `Derived from ${figure.derived_from.length} figure${figure.derived_from.length === 1 ? '' : 's'}`
        : figure.computation ?? 'No source'

  const pop = (
    <span className="fig-pop" role="tooltip">
      <span className="fig-pop-label">{figure.label}</span>
      <span className="fig-pop-value mono">{formatFigure(figure)}</span>
      {figure.computation ? <span className="fig-pop-comp mono">{figure.computation}</span> : null}
      <span className="fig-pop-refs">
        <Icon name={refs.length > 0 ? 'anchor' : 'tool'} size={11} />
        {refSummary}
      </span>
      <span className="fig-pop-id mono">{figure.id}</span>
    </span>
  )

  if (size === 'card') {
    return (
      <button
        type="button"
        className={`fig-card${selected ? ' selected' : ''}${sourced ? '' : ' unsourced'}`}
        onClick={() => onSelect(figure)}
        aria-label={`${figure.label}: ${formatFigure(figure)}. Open evidence`}
      >
        <span className="fig-card-label">{figure.label}</span>
        <span className="fig-card-value mono">{formatFigure(figure, true)}</span>
        <span className="fig-card-meta">
          <Icon name={refs.length > 0 ? 'anchor' : 'tool'} size={11} />
          {refs.length > 0 ? `${refs.length} ref${refs.length === 1 ? '' : 's'}` : figure.origin === 'computed' ? 'computed' : humanize(figure.origin)}
        </span>
        {pop}
      </button>
    )
  }
  return (
    <button
      type="button"
      className={`fig-chip${selected ? ' selected' : ''}${sourced ? '' : ' unsourced'}${figure.origin === 'computed' ? ' computed' : ''}`}
      onClick={() => onSelect(figure)}
      data-fig={figure.id}
      aria-label={`${figure.label}: ${formatFigure(figure)}. Open evidence`}
    >
      <span className="fig-chip-value">{formatFigure(figure)}</span>
      <Icon name={refs.length > 0 ? 'anchor' : 'tool'} size={10} className="fig-chip-icon" />
      {footnote !== undefined ? <sup className="fig-fn print-only">{footnote}</sup> : null}
      {pop}
    </button>
  )
}

export function UnresolvedChip({ id }: { id: string }) {
  return (
    <span className="fig-chip unresolved" title="Figure id not found in the catalog">
      <Icon name="alert" size={10} className="fig-chip-icon" />
      {id}
    </span>
  )
}

/** Split a paragraph into text and {fig:ID} tokens. */
export function tokenize(text: string): Array<{ kind: 'text'; value: string } | { kind: 'fig'; id: string }> {
  const out: Array<{ kind: 'text'; value: string } | { kind: 'fig'; id: string }> = []
  const re = /\{fig:([^}]+)\}/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ kind: 'text', value: text.slice(last, m.index) })
    out.push({ kind: 'fig', id: m[1]!.trim() })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ kind: 'text', value: text.slice(last) })
  return out
}
