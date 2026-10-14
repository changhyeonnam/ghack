import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'
const KEY = 'ledgerlens.theme'

function readTheme(): Theme {
  try {
    const attr = document.documentElement.getAttribute('data-theme')
    if (attr === 'dark' || attr === 'light') return attr
    const stored = window.localStorage.getItem(KEY)
    if (stored === 'dark' || stored === 'light') return stored
  } catch {
    // localStorage unavailable (private mode, blocked storage)
  }
  return 'light'
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => (typeof document === 'undefined' ? 'light' : readTheme()))

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try {
      window.localStorage.setItem(KEY, theme)
    } catch {
      // ignore persistence failures
    }
  }, [theme])

  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), [])
  return [theme, toggle]
}

export type Breakpoint = 'wide' | 'mid' | 'narrow'

/** Layout breakpoint: wide ≥1280 (three columns), mid 900–1279 (viewer drawer), narrow <900 (stacked). */
export function useBreakpoint(): Breakpoint {
  const compute = (): Breakpoint => {
    if (typeof window === 'undefined') return 'wide'
    if (window.matchMedia('(min-width: 1280px)').matches) return 'wide'
    if (window.matchMedia('(min-width: 900px)').matches) return 'mid'
    return 'narrow'
  }
  const [bp, setBp] = useState<Breakpoint>(compute)
  useEffect(() => {
    const mqs = [window.matchMedia('(min-width: 1280px)'), window.matchMedia('(min-width: 900px)')]
    const onChange = () => setBp(compute())
    for (const m of mqs) m.addEventListener('change', onChange)
    return () => {
      for (const m of mqs) m.removeEventListener('change', onChange)
    }
  }, [])
  return bp
}
