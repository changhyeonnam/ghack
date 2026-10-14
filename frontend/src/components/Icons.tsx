import type { SVGProps } from 'react'

export type IconName =
  | 'check'
  | 'check-circle'
  | 'alert'
  | 'alert-circle'
  | 'x'
  | 'chevron-left'
  | 'chevron-right'
  | 'chevron-down'
  | 'arrow-left'
  | 'file'
  | 'file-pdf'
  | 'image'
  | 'search'
  | 'plus'
  | 'sun'
  | 'moon'
  | 'user'
  | 'play'
  | 'refresh'
  | 'external'
  | 'print'
  | 'more'
  | 'info'
  | 'copy'
  | 'bolt'
  | 'cpu'
  | 'pen'
  | 'clock'
  | 'eye'
  | 'eye-off'
  | 'anchor'
  | 'shield-check'
  | 'upload'
  | 'trash'
  | 'tool'
  | 'layers'
  | 'minus'
  | 'spark'
  | 'hand'

const PATHS: Record<IconName, string> = {
  check: 'M4 10.5l3.5 3.5L16 5.5',
  'check-circle': 'M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm-3.5-8l2.5 2.5 4.5-5',
  alert: 'M10 3l8 14H2L10 3zm0 5v4m0 2.5v.5',
  'alert-circle': 'M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm0-12v5m0 2.5v.5',
  x: 'M5 5l10 10M15 5L5 15',
  'chevron-left': 'M12.5 4.5L7 10l5.5 5.5',
  'chevron-right': 'M7.5 4.5L13 10l-5.5 5.5',
  'chevron-down': 'M4.5 7.5L10 13l5.5-5.5',
  'arrow-left': 'M16 10H4m5-5l-5 5 5 5',
  file: 'M11 2H5.5A1.5 1.5 0 0 0 4 3.5v13A1.5 1.5 0 0 0 5.5 18h9a1.5 1.5 0 0 0 1.5-1.5V7l-5-5zm0 0v5h5',
  'file-pdf': 'M11 2H5.5A1.5 1.5 0 0 0 4 3.5v13A1.5 1.5 0 0 0 5.5 18h9a1.5 1.5 0 0 0 1.5-1.5V7l-5-5zm0 0v5h5M7 15v-4h1.5a1.25 1.25 0 0 1 0 2.5H7',
  image: 'M3.5 4.5h13v11h-13zM3.5 13l4-4 3 3 2-2 4 4m-3.5-7.5h.01',
  search: 'M9 15a6 6 0 1 0 0-12 6 6 0 0 0 0 12zm8 2l-3.5-3.5',
  plus: 'M10 4v12M4 10h12',
  minus: 'M4 10h12',
  sun: 'M10 14a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0-12v1.5M10 16.5V18M2 10h1.5M16.5 10H18M4.3 4.3l1.1 1.1m9.2 9.2l1.1 1.1m0-11.4l-1.1 1.1M5.4 14.6l-1.1 1.1',
  moon: 'M16.5 12.5A7 7 0 0 1 7.5 3.5a7 7 0 1 0 9 9z',
  user: 'M10 10a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zm-6.5 7a6.5 6.5 0 0 1 13 0',
  play: 'M6 4l10 6-10 6V4z',
  refresh: 'M16 10a6 6 0 0 1-10.4 4.1M4 10a6 6 0 0 1 10.4-4.1M14.5 3v3h-3M5.5 17v-3h3',
  external: 'M11 3h6v6m0-6l-8 8M15 11v4.5A1.5 1.5 0 0 1 13.5 17h-9A1.5 1.5 0 0 1 3 15.5v-9A1.5 1.5 0 0 1 4.5 5H9',
  print: 'M6 7V3h8v4M6 14H4.5A1.5 1.5 0 0 1 3 12.5v-4A1.5 1.5 0 0 1 4.5 7h11A1.5 1.5 0 0 1 17 8.5v4a1.5 1.5 0 0 1-1.5 1.5H14m-8-3h8v6H6v-6z',
  more: 'M10 5.5h.01M10 10h.01M10 14.5h.01',
  info: 'M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm0-8v4m0-7.5v.5',
  copy: 'M7 7V4.5A1.5 1.5 0 0 1 8.5 3h7A1.5 1.5 0 0 1 17 4.5v7a1.5 1.5 0 0 1-1.5 1.5H13M3 8.5A1.5 1.5 0 0 1 4.5 7h7A1.5 1.5 0 0 1 13 8.5v7a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 15.5v-7z',
  bolt: 'M11 2L4 11h5l-1 7 8-10h-5l0-6z',
  cpu: 'M6 6h8v8H6zM8.5 8.5h3v3h-3zM10 2v2m0 12v2M2 10h2m12 0h2M5 2v2m10-2v2M5 16v2m10-2v2M2 5h2m12 0h2M2 15h2m12 0h2',
  pen: 'M13.5 3.5l3 3L7 16H4v-3l9.5-9.5zM11.5 5.5l3 3',
  clock: 'M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm0-12v4l2.5 2',
  eye: 'M2 10s3-5.5 8-5.5 8 5.5 8 5.5-3 5.5-8 5.5S2 10 2 10zm8 2.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  'eye-off': 'M3 3l14 14M8.5 8.6A2.5 2.5 0 0 0 11.4 11.5M6.3 6.4C3.6 8 2 10 2 10s3 5.5 8 5.5c1.3 0 2.5-.4 3.5-.9M9 4.6c.3 0 .7-.1 1-.1 5 0 8 5.5 8 5.5s-.8 1.5-2.3 3',
  anchor: 'M10 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm0 0v10m-6-6a6 6 0 0 0 12 0M3 11h2m10 0h2',
  'shield-check': 'M10 2l6.5 2.5v5c0 4-2.8 7-6.5 8.5C6.3 16.5 3.5 13.5 3.5 9.5v-5L10 2zm-3 8l2 2 4-4.5',
  upload: 'M10 13V4m-4 4l4-4 4 4M4 15.5A1.5 1.5 0 0 0 5.5 17h9a1.5 1.5 0 0 0 1.5-1.5',
  trash: 'M4 6h12M8 6V4h4v2M6 6l.8 10h6.4L14 6M8.5 9v4.5m3-4.5v4.5',
  tool: 'M12.5 3.5a4 4 0 0 0-4.6 5.1L3 13.5v3h3l4.9-4.9A4 4 0 0 0 16.5 7.5L14 10l-2.5-1L10.5 6.5l2-3z',
  layers: 'M10 3l7.5 4L10 11 2.5 7 10 3zm-7.5 7l7.5 4 7.5-4M2.5 13.5L10 17.5l7.5-4',
  spark: 'M10 2l1.8 5.2L17 9l-5.2 1.8L10 16l-1.8-5.2L3 9l5.2-1.8L10 2zM16 14l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2z',
  hand: 'M7 10V4.5a1.5 1.5 0 0 1 3 0V9m0-5.5a1.5 1.5 0 0 1 3 0V10m0-4.5a1.5 1.5 0 0 1 3 0V13a5 5 0 0 1-5 5H9.5a5 5 0 0 1-4.1-2.1L3 12.3a1.5 1.5 0 0 1 2.4-1.8L7 12.5',
}

interface Props extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName
  size?: number
}

/** Inline stroke icon, 20×20 grid. Inherits `currentColor`. */
export function Icon({ name, size = 16, className, ...rest }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className ? `icon ${className}` : 'icon'}
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  )
}

/** Wordmark: a lens with a ledger stroke. */
export function LensMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="lens-mark">
      <circle cx="10.5" cy="10.5" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M16 16l5 5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M7 9h7M7 12h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}
