/**
 * Iconos SVG inline (estilo Lucide). Evita dependencia extra y garantiza
 * que todos compartan el mismo stroke width (1.8) y tamano (15px default).
 */

const paths = {
  palette: <>
    <path d="M12 22a10 10 0 1 1 10-10c0 2.5-2 4-4 4h-2a2 2 0 0 0-2 2v2c0 1.1-.9 2-2 2Z"/>
    <circle cx="7" cy="12" r="1.2"/><circle cx="10" cy="7.5" r="1.2"/>
    <circle cx="14.5" cy="7.5" r="1.2"/><circle cx="17.5" cy="12" r="1.2"/>
  </>,
  settings: <>
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </>,
  volume: <>
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
  </>,
  telegram: <>
    <path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4 20-7z"/>
  </>,
  minus:    <path d="M5 12h14"/>,
  square:   <rect x="5" y="5" width="14" height="14" rx="1"/>,
  squares:  <><rect x="7" y="3" width="14" height="14" rx="1"/><rect x="3" y="7" width="14" height="14" rx="1"/></>,
  x:        <><path d="M18 6 6 18"/><path d="m6 6 12 12"/></>,
  chevron:  <path d="m15 18-6-6 6-6"/>,
  paperclip: <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>,
  image: <><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></>,
  send:  <><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></>,
  file:  <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></>,
}

export default function Icon({ name, size = 15, className = '', strokeWidth = 1.8 }) {
  const d = paths[name]
  if (!d) return null
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {d}
    </svg>
  )
}
