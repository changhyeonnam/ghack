import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { documentFileUrl, documentPageUrl } from '../api'
import { docTypeLabel, humanize, languageName } from '../format'
import { DocIcon, EmptyState, Kbd, QualityFlagIcons, Spinner, visibleFlags } from './Badges'
import { Icon } from './Icons'
import { useViewer } from './viewerContext'

type Zoom = 'fit' | 'actual'

export function DocumentViewer() {
  const viewer = useViewer()
  const { documents, selection, caseId } = viewer
  const [zoom, setZoom] = useState<Zoom>('fit')
  // Load state is derived from which src finished loading, so a cached image whose `load` event fires before any
  // effect runs can never be reset back to "loading".
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null)
  const [errorSrc, setErrorSrc] = useState<string | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const thumbsRef = useRef<HTMLDivElement>(null)

  const doc = useMemo(() => documents.find((d) => d.doc_id === selection?.docId) ?? null, [documents, selection?.docId])
  const page = selection?.page ?? 1
  const pages = doc?.pages ?? 1

  const src = doc ? documentPageUrl(caseId, doc.doc_id, page, zoom === 'actual' ? 2 : 1) : null

  const imgState: 'loading' | 'ok' | 'error' = src && loadedSrc === src ? 'ok' : src && errorSrc === src ? 'error' : 'loading'
  const imgRef = (el: HTMLImageElement | null) => {
    const attr = el?.getAttribute('src')
    if (el && attr && el.complete && el.naturalWidth > 0 && loadedSrc !== attr) setLoadedSrc(attr)
  }

  // Keep the active thumbnail in view (scroll the strip only, never the page).
  useEffect(() => {
    const strip = thumbsRef.current
    const el = strip?.querySelector<HTMLElement>('.thumb.active')
    if (!strip || !el) return
    const left = el.offsetLeft - strip.clientWidth / 2 + el.clientWidth / 2
    strip.scrollTo({ left: Math.max(0, left), behavior: 'smooth' })
  }, [page, doc?.doc_id])

  const pageHighlights = useMemo(
    () => (selection && doc ? selection.highlights.filter((h) => h.ref.doc_id === doc.doc_id && h.ref.page === page) : []),
    [selection, doc, page],
  )
  // Refs on other pages, de-duplicated by document + page (a derived figure can cite dozens of rows on one page).
  const otherPageRefs = useMemo(() => {
    if (!selection) return []
    const seen = new Set<string>()
    const out: typeof selection.highlights = []
    for (const h of selection.highlights) {
      if (h.ref.doc_id === doc?.doc_id && h.ref.page === page) continue
      const key = `${h.ref.doc_id}:${h.ref.page}`
      if (seen.has(key)) continue
      seen.add(key)
      out.push(h)
    }
    return out
  }, [selection, doc, page])
  const [showAllRefs, setShowAllRefs] = useState(false)
  useEffect(() => setShowAllRefs(false), [selection?.nonce])
  const MAX_OTHER = 6
  const shownOtherRefs = showAllRefs ? otherPageRefs : otherPageRefs.slice(0, MAX_OTHER)
  const withBox = pageHighlights.filter((h) => h.ref.bbox)
  const pageOnly = pageHighlights.filter((h) => !h.ref.bbox)

  const goPrev = () => doc && page > 1 && viewer.openDocument(doc.doc_id, page - 1)
  const goNext = () => doc && page < pages && viewer.openDocument(doc.doc_id, page + 1)

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    if (target.tagName === 'SELECT' || target.tagName === 'INPUT') return
    if (e.key === '[' || e.key === 'ArrowLeft' || e.key === 'PageUp') {
      e.preventDefault()
      goPrev()
    } else if (e.key === ']' || e.key === 'ArrowRight' || e.key === 'PageDown') {
      e.preventDefault()
      goNext()
    }
  }

  if (documents.length === 0) {
    return (
      <div className="viewer">
        <div className="viewer-toolbar">
          <span className="viewer-title">Document viewer</span>
        </div>
        <div className="viewer-stage">
          <EmptyState icon="file" title="No documents" hint="Upload documents to this case to view them here." />
        </div>
      </div>
    )
  }

  return (
    <div className="viewer" ref={rootRef} tabIndex={0} onKeyDown={onKey} aria-label="Document viewer">
      <div className="viewer-toolbar">
        <div className="viewer-doc">
          {doc ? <DocIcon mime={doc.mime_type} size={14} /> : null}
          <select className="viewer-doc-select" value={doc?.doc_id ?? ''} onChange={(e) => viewer.openDocument(e.target.value, 1)} aria-label="Document">
            {!doc ? <option value="">Select a document…</option> : null}
            {documents.map((d) => (
              <option key={d.doc_id} value={d.doc_id}>
                {d.filename}
                {d.doc_type ? ` · ${docTypeLabel(d.doc_type)}` : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="viewer-pager">
          <button className="icon-btn tip" data-tip="Previous page" disabled={!doc || page <= 1} onClick={goPrev} aria-label="Previous page">
            <Icon name="chevron-left" />
          </button>
          <span className="pager-text mono">
            {page}
            <span className="muted"> / {pages}</span>
          </span>
          <button className="icon-btn tip" data-tip="Next page" disabled={!doc || page >= pages} onClick={goNext} aria-label="Next page">
            <Icon name="chevron-right" />
          </button>
        </div>
        <div className="viewer-zoom">
          <div className="segmented segmented-sm" role="group" aria-label="Zoom">
            <button className={`segment${zoom === 'fit' ? ' active' : ''}`} onClick={() => setZoom('fit')} title="Fit to width">
              Fit
            </button>
            <button className={`segment${zoom === 'actual' ? ' active' : ''}`} onClick={() => setZoom('actual')} title="Actual size">
              100%
            </button>
          </div>
          {doc ? (
            <a className="icon-btn tip tip-left" data-tip="Open original file" href={documentFileUrl(caseId, doc.doc_id)} target="_blank" rel="noreferrer" aria-label="Open original file">
              <Icon name="external" />
            </a>
          ) : null}
        </div>
      </div>

      {selection && selection.highlights.length > 0 ? (
        <div className="viewer-context">
          <div className="viewer-context-main">
            <Icon name="anchor" size={12} />
            <span className="viewer-context-label truncate">{selection.highlights[0]?.label}</span>
            {withBox.length > 0 ? (
              <span className="muted small">
                {withBox.length} location{withBox.length === 1 ? '' : 's'} on this page
              </span>
            ) : pageOnly.length > 0 ? (
              <span className="muted small">On this page · no exact location recorded</span>
            ) : null}
          </div>
          {otherPageRefs.length > 0 ? (
            <div className="viewer-context-others">
              <span className="muted small">Also on</span>
              {shownOtherRefs.map((h) => (
                <button key={`${h.ref.doc_id}-${h.ref.page}`} className="ref-chip" onClick={() => viewer.openRefs([h.ref, ...selection.highlights.filter((x) => x !== h).map((x) => x.ref)], h.label)} title={`Open ${viewer.docName(h.ref.doc_id)} page ${h.ref.page}`}>
                  <span className="ref-doc truncate">{viewer.docName(h.ref.doc_id)}</span>
                  <span className="ref-page mono">p.{h.ref.page}</span>
                </button>
              ))}
              {otherPageRefs.length > MAX_OTHER ? (
                <button className="link-btn small" onClick={() => setShowAllRefs((v) => !v)}>
                  {showAllRefs ? 'Show fewer' : `+${otherPageRefs.length - MAX_OTHER} more`}
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className={`viewer-stage zoom-${zoom}`}>
        {!doc || !src ? (
          <EmptyState icon="file" title="Select a document" hint="Or click any number in the memo to jump to its source." />
        ) : (
          <div className="page-wrap" key={`${doc.doc_id}-${page}`}>
            {imgState === 'loading' ? (
              <div className="page-loading">
                <Spinner /> Rendering page…
              </div>
            ) : null}
            {imgState === 'error' ? (
              <div className="page-error">
                <Icon name="alert-circle" size={16} />
                Could not render this page. The backend may still be processing the file.
              </div>
            ) : null}
            <img
              src={src}
              alt={`${doc.filename} page ${page}`}
              className={`page-img${imgState === 'ok' ? '' : ' hidden'}`}
              ref={imgRef}
              onLoad={() => setLoadedSrc(src)}
              onError={() => setErrorSrc(src)}
              draggable={false}
            />
            {imgState === 'ok' && selection
              ? withBox.map((h) => {
                  const b = h.ref.bbox!
                  const style = {
                    left: `${b.xmin / 10}%`,
                    top: `${b.ymin / 10}%`,
                    width: `${Math.max(b.xmax - b.xmin, 4) / 10}%`,
                    height: `${Math.max(b.ymax - b.ymin, 4) / 10}%`,
                  }
                  return (
                    <div key={`${selection.nonce}-${h.index}`} className={`hl pulse${withBox.length > 3 ? ' hl-compact' : ''}`} style={style} title={h.ref.snippet ?? h.label}>
                      <span className="hl-pill">
                        {withBox.length > 1 ? <span className="hl-num">{h.index}</span> : null}
                        <span className="hl-label">{h.label}</span>
                      </span>
                      {h.ref.snippet ? <span className="hl-tip">“{h.ref.snippet}”</span> : null}
                    </div>
                  )
                })
              : null}
          </div>
        )}
      </div>

      {doc && pages > 1 ? (
        <div className="thumbs" ref={thumbsRef} role="list" aria-label="Pages">
          {Array.from({ length: pages }, (_, i) => i + 1).map((p) => {
            const hasRef = selection?.highlights.some((h) => h.ref.doc_id === doc.doc_id && h.ref.page === p)
            return (
              <button
                key={p}
                role="listitem"
                className={`thumb${p === page ? ' active' : ''}${hasRef ? ' has-ref' : ''}`}
                onClick={() => viewer.openDocument(doc.doc_id, p)}
                aria-label={`Page ${p}${hasRef ? ', has evidence' : ''}`}
                aria-current={p === page ? 'page' : undefined}
              >
                <img src={documentPageUrl(caseId, doc.doc_id, p, 1)} alt="" loading="lazy" draggable={false} />
                <span className="thumb-num mono">{p}</span>
                {hasRef ? <span className="thumb-ref" aria-hidden="true" /> : null}
              </button>
            )
          })}
        </div>
      ) : null}

      {doc ? (
        <div className="viewer-footer">
          <span className="truncate viewer-filename" title={doc.filename}>
            {doc.filename}
          </span>
          <span className="viewer-footer-meta">
            <span className={doc.doc_type ? '' : 'muted'}>{docTypeLabel(doc.doc_type)}</span>
            {doc.language ? (
              <>
                <span className="doc-meta-sep" aria-hidden="true" />
                <span className="tip tip-left" data-tip={languageName(doc.language)}>
                  {doc.language.toUpperCase()}
                </span>
              </>
            ) : null}
            {visibleFlags(doc.quality_flags).length > 0 ? (
              <>
                <span className="doc-meta-sep" aria-hidden="true" />
                <QualityFlagIcons flags={doc.quality_flags} />
              </>
            ) : null}
          </span>
          <span className="viewer-kbd muted small tip tip-left" data-tip={`Keyboard: ${humanize('previous')} / next page when the viewer is focused`}>
            <Kbd>[</Kbd>
            <Kbd>]</Kbd>
          </span>
        </div>
      ) : null}
    </div>
  )
}
