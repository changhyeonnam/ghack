import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { getHealth } from '../api'
import { modelDisplayName } from '../format'
import type { Health } from '../types'
import { Icon, LensMark } from './Icons'
import { useTheme } from './theme'

/** Application chrome: wordmark, environment pill, theme toggle, user avatar. */
export function TopBar() {
  const [theme, toggleTheme] = useTheme()
  const [health, setHealth] = useState<Health | null | 'error'>(null)

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((h) => !cancelled && setHealth(h))
      .catch(() => !cancelled && setHealth('error'))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="wordmark" aria-label="LedgerLens home">
          <LensMark />
          <span>LedgerLens</span>
        </Link>
        <nav className="topnav" aria-label="Primary">
          <NavLink to="/" end className={({ isActive }) => `topnav-link${isActive ? ' active' : ''}`}>
            Portfolio
          </NavLink>
          <NavLink to="/cases/new" className={({ isActive }) => `topnav-link${isActive ? ' active' : ''}`}>
            New case
          </NavLink>
        </nav>
        <div className="topbar-right">
          <EnvPill health={health} />
          <button
            type="button"
            className="icon-btn tip tip-left"
            onClick={toggleTheme}
            data-tip={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
          </button>
          <div className="avatar tip tip-left" data-tip="Signed in as Underwriter (demo)" aria-label="Underwriter">
            <span className="avatar-initials">UW</span>
          </div>
        </div>
      </div>
    </header>
  )
}

function EnvPill({ health }: { health: Health | null | 'error' }) {
  if (health === null) return <span className="env-pill env-loading" aria-hidden="true" />
  if (health === 'error') {
    return (
      <span className="env-pill env-bad tip tip-left" data-tip="The API at /api/health did not respond">
        <span className="env-dot" />
        API unreachable
      </span>
    )
  }
  const model = modelDisplayName(health.models.flash)
  let label = ''
  let tone = 'env-live'
  if (health.llm_mode === 'live') label = `Live · ${model}`
  else if (health.llm_mode === 'cache_only') {
    label = `Cached · ${model}`
    tone = 'env-cached'
  } else {
    label = 'Offline demo'
    tone = 'env-mock'
  }
  const storage = health.storage === 'gcp' ? 'Google Cloud storage' : 'Local storage'
  const tip = `LLM mode: ${health.llm_mode} · Flash: ${health.models.flash} · Pro: ${health.models.pro} · ${storage}`
  return (
    <span className={`env-pill ${tone} tip tip-left`} data-tip={tip}>
      <span className="env-dot" />
      {label}
      <span className="env-sep" aria-hidden="true" />
      <span className="env-storage">{health.storage === 'gcp' ? 'GCP' : 'Local'}</span>
    </span>
  )
}

export interface Crumb {
  label: ReactNode
  to?: string
}

export function Crumbs({ items }: { items: Crumb[] }) {
  return (
    <nav className="crumbs" aria-label="Breadcrumb">
      <ol>
        {items.map((c, i) => (
          <li key={i}>
            {c.to ? <Link to={c.to}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}
            {i < items.length - 1 ? <Icon name="chevron-right" size={12} className="crumb-sep" /> : null}
          </li>
        ))}
      </ol>
    </nav>
  )
}
