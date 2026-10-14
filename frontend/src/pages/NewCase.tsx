import { useRef, useState, type DragEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createCase, deleteDocument, documentPageUrl, errorMessage, uploadDocuments } from '../api'
import { DocIcon, Spinner } from '../components/Badges'
import { Icon } from '../components/Icons'
import { Crumbs } from '../components/Shell'
import { useToast } from '../components/Toast'
import { docTypeLabel, formatBytes } from '../format'
import type { Case, CaseCreate, DocType } from '../types'

const COUNTRY_DEFAULTS: Record<string, { language: string; currency: string }> = {
  ID: { language: 'id', currency: 'IDR' },
  VN: { language: 'vi', currency: 'VND' },
  PH: { language: 'tl', currency: 'PHP' },
}

const ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp'

interface ChecklistItem {
  title: string
  hint: string
  types: DocType[]
  match: RegExp
}

const CHECKLIST: ChecklistItem[] = [
  { title: 'Bank statement', hint: 'Last 6 months, all pages', types: ['bank_statement'], match: /statement|bank|rekening|sao\s*ke/i },
  { title: 'Seller dashboard captures', hint: 'Shopee / Lazada / Tokopedia monthly views', types: ['seller_dashboard'], match: /dashboard|shopee|lazada|tokopedia|tiktok/i },
  { title: 'Receipts or ledger', hint: 'Purchase receipts, logistics slips, handwritten books', types: ['receipt', 'logistics_receipt', 'handwritten_ledger'], match: /receipt|ledger|invoice|nota|resi|bill/i },
  { title: 'Premises photos', hint: 'Storefront, signage, stock on shelves', types: ['premises_photo'], match: /premise|shop|store|front|photo|toko|warung/i },
]

export default function NewCase() {
  const navigate = useNavigate()
  const toast = useToast()
  const [form, setForm] = useState<CaseCreate>({
    name: '',
    business_name: '',
    sector: '',
    country: 'ID',
    language: 'id',
    currency: 'IDR',
    requested_amount: null,
  })
  const [creating, setCreating] = useState(false)
  const [created, setCreated] = useState<Case | null>(null)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [removing, setRemoving] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  function update<K extends keyof CaseCreate>(key: K, value: CaseCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function onCountryChange(country: string) {
    const d = COUNTRY_DEFAULTS[country]
    setForm((f) => ({
      ...f,
      country,
      language: d ? d.language : f.language,
      currency: d ? d.currency : f.currency,
    }))
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    if (!form.name.trim() || !form.business_name.trim()) {
      toast.error('Case name and business name are required')
      return
    }
    setCreating(true)
    try {
      const c = await createCase({
        ...form,
        name: form.name.trim(),
        business_name: form.business_name.trim(),
        sector: form.sector.trim(),
      })
      setCreated(c)
      toast.success('Case created. Now add documents.')
    } catch (err) {
      toast.error(`Could not create case: ${errorMessage(err)}`)
    } finally {
      setCreating(false)
    }
  }

  async function onFiles(files: FileList | File[] | null) {
    if (!created || !files || files.length === 0) return
    const list = Array.from(files)
    setUploading(true)
    try {
      const c = await uploadDocuments(created.id, list)
      setCreated(c)
      toast.success(`Uploaded ${list.length} file${list.length === 1 ? '' : 's'}`)
    } catch (err) {
      toast.error(`Upload failed: ${errorMessage(err)}`)
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  async function onRemove(docId: string) {
    if (!created) return
    setRemoving(docId)
    try {
      setCreated(await deleteDocument(created.id, docId))
    } catch (err) {
      toast.error(`Could not remove document: ${errorMessage(err)}`)
    } finally {
      setRemoving(null)
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    void onFiles(e.dataTransfer.files)
  }

  const step = created ? 2 : 1
  const docs = created?.documents ?? []

  return (
    <div className="page">
      <Crumbs items={[{ label: 'Portfolio', to: '/' }, { label: 'New case' }]} />
      <header className="page-head">
        <div>
          <h1 className="page-title">New case</h1>
          <p className="page-sub">Describe the applicant, then upload the raw documents. Intake classifies them automatically.</p>
        </div>
      </header>

      <ol className="stepper" aria-label="Progress">
        <li className={`step${step === 1 ? ' current' : ' done'}`}>
          <span className="step-num">{step > 1 ? <Icon name="check" size={12} /> : '1'}</span>
          <span className="step-label">Applicant</span>
        </li>
        <li className="step-line" aria-hidden="true" />
        <li className={`step${step === 2 ? ' current' : ''}`}>
          <span className="step-num">2</span>
          <span className="step-label">Documents</span>
        </li>
      </ol>

      <div className="newcase-grid">
        <div className="newcase-main">
          <form className="panel form-panel" onSubmit={onCreate}>
            <div className="panel-head">
              <h2 className="panel-title">Applicant</h2>
              {created ? (
                <span className="chip chip-success">
                  <Icon name="check" size={12} /> Created · <span className="mono">{created.id}</span>
                </span>
              ) : null}
            </div>
            <fieldset className="form-grid" disabled={!!created}>
              <label className="field span-2">
                <span className="field-label">Case name</span>
                <input value={form.name} onChange={(e) => update('name', e.target.value)} placeholder="e.g. Warung Ibu Sari — working capital" required />
              </label>
              <label className="field span-2">
                <span className="field-label">Business name</span>
                <input
                  value={form.business_name}
                  onChange={(e) => update('business_name', e.target.value)}
                  placeholder="Legal or trading name as shown on documents"
                  required
                />
              </label>
              <label className="field span-2">
                <span className="field-label">Sector</span>
                <input value={form.sector} onChange={(e) => update('sector', e.target.value)} placeholder="e.g. Grocery retail, Online fashion, Auto repair" />
              </label>
              <label className="field">
                <span className="field-label">Country</span>
                <select value={form.country} onChange={(e) => onCountryChange(e.target.value)}>
                  <option value="ID">Indonesia</option>
                  <option value="VN">Vietnam</option>
                  <option value="PH">Philippines</option>
                  <option value="other">Other</option>
                </select>
                <span className="field-help">Sets the default document language and currency.</span>
              </label>
              <label className="field">
                <span className="field-label">Document language</span>
                <select value={form.language} onChange={(e) => update('language', e.target.value)}>
                  <option value="id">Indonesian</option>
                  <option value="vi">Vietnamese</option>
                  <option value="tl">Filipino</option>
                  <option value="en">English</option>
                </select>
              </label>
              <label className="field">
                <span className="field-label">Currency</span>
                <select value={form.currency} onChange={(e) => update('currency', e.target.value)}>
                  <option value="IDR">IDR — Indonesian rupiah</option>
                  <option value="VND">VND — Vietnamese dong</option>
                  <option value="PHP">PHP — Philippine peso</option>
                  <option value="USD">USD — US dollar</option>
                </select>
              </label>
              <label className="field">
                <span className="field-label">Requested amount</span>
                <div className="input-affix">
                  <span className="affix mono">{form.currency}</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="any"
                    value={form.requested_amount ?? ''}
                    onChange={(e) => update('requested_amount', e.target.value === '' ? null : Number(e.target.value))}
                    placeholder="Optional"
                    className="mono"
                  />
                </div>
              </label>
            </fieldset>
            {!created ? (
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={creating}>
                  {creating ? <Spinner small /> : null} Create case and continue
                  {!creating ? <Icon name="chevron-right" /> : null}
                </button>
              </div>
            ) : null}
          </form>

          <section className={`panel upload-panel${created ? '' : ' is-disabled'}`} aria-disabled={!created}>
            <div className="panel-head">
              <h2 className="panel-title">Documents</h2>
              {created ? (
                <span className="muted small">
                  {docs.length} file{docs.length === 1 ? '' : 's'}
                </span>
              ) : null}
            </div>
            <div
              className={`dropzone${dragOver ? ' over' : ''}${uploading ? ' busy' : ''}`}
              onDragOver={(e) => {
                e.preventDefault()
                if (created) setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => created && !uploading && fileInput.current?.click()}
              role="button"
              tabIndex={created ? 0 : -1}
              onKeyDown={(e) => {
                if ((e.key === 'Enter' || e.key === ' ') && created) fileInput.current?.click()
              }}
            >
              <input ref={fileInput} type="file" multiple accept={ACCEPT} hidden onChange={(e) => void onFiles(e.target.files)} disabled={!created} />
              {uploading ? (
                <>
                  <Spinner />
                  <div>
                    <strong>Uploading and rendering pages…</strong>
                  </div>
                </>
              ) : (
                <>
                  <div className="dropzone-icon" aria-hidden="true">
                    <Icon name="upload" size={20} />
                  </div>
                  <div>
                    <strong>{created ? 'Drop files here' : 'Create the case first'}</strong>
                    {created ? <span className="muted"> or click to browse</span> : null}
                  </div>
                  <div className="muted small">PDF, JPG, PNG, WEBP · up to 6 months of statements, dashboards, receipts, photos</div>
                </>
              )}
            </div>

            {created && docs.length > 0 ? (
              <ul className="file-rows">
                {docs.map((d) => (
                  <li key={d.doc_id} className="file-row">
                    <img
                      className="file-thumb"
                      src={documentPageUrl(created.id, d.doc_id, 1, 1)}
                      alt=""
                      loading="lazy"
                      onError={(e) => {
                        ;(e.currentTarget as HTMLImageElement).style.visibility = 'hidden'
                      }}
                    />
                    <DocIcon mime={d.mime_type} />
                    <div className="file-text">
                      <div className="file-name truncate" title={d.filename}>
                        {d.filename}
                      </div>
                      <div className="file-meta muted small">
                        {d.pages} page{d.pages === 1 ? '' : 's'} · {formatBytes(d.size_bytes)}
                        {d.doc_type ? ` · ${docTypeLabel(d.doc_type)}` : ''}
                      </div>
                    </div>
                    <button
                      className="icon-btn tip tip-left"
                      data-tip="Remove"
                      aria-label={`Remove ${d.filename}`}
                      onClick={() => void onRemove(d.doc_id)}
                      disabled={removing === d.doc_id}
                    >
                      {removing === d.doc_id ? <Spinner small /> : <Icon name="trash" />}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="form-actions">
              <button className="btn btn-primary" disabled={!created} onClick={() => created && navigate(`/cases/${created.id}`)}>
                Open workbench <Icon name="chevron-right" />
              </button>
              {created && docs.length === 0 ? <span className="muted small">You can also add documents later from the workbench.</span> : null}
            </div>
          </section>
        </div>

        <aside className="newcase-side">
          <section className="panel checklist-panel">
            <div className="panel-head">
              <h2 className="panel-title">What to upload</h2>
            </div>
            <ul className="checklist">
              {CHECKLIST.map((item) => {
                const classified = docs.filter((d) => d.doc_type && item.types.includes(d.doc_type)).length
                const guessed = docs.filter((d) => !d.doc_type && item.match.test(d.filename)).length
                const state = classified > 0 ? 'done' : guessed > 0 ? 'partial' : 'todo'
                return (
                  <li key={item.title} className={`check-item check-${state}`}>
                    <span className="check-mark" aria-hidden="true">
                      {state === 'done' ? <Icon name="check" size={12} /> : state === 'partial' ? <Icon name="clock" size={12} /> : null}
                    </span>
                    <div className="check-text">
                      <div className="check-title">{item.title}</div>
                      <div className="check-hint">{item.hint}</div>
                      {classified > 0 ? (
                        <div className="check-status good">
                          {classified} classified at intake
                        </div>
                      ) : guessed > 0 ? (
                        <div className="check-status">
                          {guessed} uploaded · classified after intake
                        </div>
                      ) : null}
                    </div>
                  </li>
                )
              })}
            </ul>
            <p className="muted small checklist-note">
              Document types are confirmed by the Intake stage in the workbench. Missing categories lower the memo's confidence and become challenger objections.
            </p>
          </section>
        </aside>
      </div>
    </div>
  )
}
