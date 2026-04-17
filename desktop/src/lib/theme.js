/**
 * Sistema de tema dinamico.
 *
 * Recibe un hex (#rrggbb) y deriva TODAS las variables CSS (acento, glow,
 * fondos tintados, bordes, textos, colores del orbe) usando HSL math.
 * Persiste en localStorage.
 */

export const PRESETS = [
  { color: '#06b6d4', name: 'Cyan' },
  { color: '#3b82f6', name: 'Indigo' },
  { color: '#8b5cf6', name: 'Violet' },
  { color: '#ec4899', name: 'Pink' },
  { color: '#ee2a55', name: 'Crimson' },
  { color: '#f97316', name: 'Amber' },
  { color: '#eab308', name: 'Gold' },
  { color: '#22c55e', name: 'Emerald' },
]

const DEFAULT_ACCENT = '#06b6d4'
const STORAGE_KEY = 'jarvis.theme'

export function hexToHSL(hex) {
  hex = hex.replace('#', '')
  const r = parseInt(hex.substring(0, 2), 16) / 255
  const g = parseInt(hex.substring(2, 4), 16) / 255
  const b = parseInt(hex.substring(4, 6), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  let h, s
  const l = (max + min) / 2
  if (max === min) { h = 0; s = 0 }
  else {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break
      case g: h = (b - r) / d + 2; break
      case b: h = (r - g) / d + 4; break
    }
    h /= 6
  }
  return { h: h * 360, s: s * 100, l: l * 100 }
}

/** Aplica el tema al :root via CSS variables. */
export function applyTheme(hex) {
  const { h, s, l } = hexToHSL(hex)
  const root = document.documentElement.style
  const targetL = Math.max(50, Math.min(65, l))
  const targetS = Math.max(60, s)

  // UI accent
  root.setProperty('--accent',       `hsl(${h}, ${targetS}%, ${targetL}%)`)
  root.setProperty('--accent-muted', `hsla(${h}, ${targetS}%, ${targetL}%, 0.12)`)
  root.setProperty('--accent-glow',  `hsla(${h}, ${targetS}%, ${targetL}%, 0.35)`)

  // Blobs del orbe (legacy, mantenidos por compatibilidad)
  root.setProperty('--blob-1', `hsl(${h}, ${targetS}%, ${targetL}%)`)
  root.setProperty('--blob-2', `hsl(${h}, 85%, 70%)`)
  root.setProperty('--blob-3', `hsl(${h}, 75%, 65%)`)
  root.setProperty('--blob-4', `hsl(${h}, 90%, 60%)`)
  root.setProperty('--blob-5', `hsl(${h}, 95%, 72%)`)

  // Orb colors — color primario = accent, secundario = +105° (complementario)
  const h2 = (h + 105) % 360
  root.setProperty('--orb-cyan',         `hsl(${h}, ${targetS}%, ${targetL}%)`)
  root.setProperty('--orb-magenta',      `hsl(${h2}, ${targetS}%, ${targetL}%)`)
  root.setProperty('--orb-cyan-soft',    `hsla(${h}, ${targetS}%, ${targetL}%, 0.6)`)
  root.setProperty('--orb-magenta-soft', `hsla(${h2}, ${targetS}%, ${targetL}%, 0.6)`)
  root.setProperty('--orb-glow-1',       `hsla(${h}, ${targetS}%, ${targetL}%, 0.30)`)
  root.setProperty('--orb-glow-2',       `hsla(${h2}, ${targetS}%, ${targetL}%, 0.22)`)

  try { localStorage.setItem(STORAGE_KEY, hex) } catch {}
}

export function loadSavedTheme() {
  let saved = DEFAULT_ACCENT
  try { saved = localStorage.getItem(STORAGE_KEY) || DEFAULT_ACCENT } catch {}
  applyTheme(saved)
  return saved
}
