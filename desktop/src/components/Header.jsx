import { useEffect, useRef, useState } from 'react'
import Icon from './Icon.jsx'
import { PRESETS, applyTheme } from '../lib/theme.js'

export default function Header({ providerLabel = '—', wsStatus = 'connecting', voiceStatus = 'off', onToggleVoice, isMax, onToggleMax }) {
  const dotColor = wsStatus === 'connected' ? 'var(--ok)' : wsStatus === 'reconnecting' ? 'var(--warn)' : 'var(--err)'
  const dotShadow = `0 0 0 3px ${wsStatus === 'connected' ? 'hsla(145,70%,50%,0.15)' : wsStatus === 'reconnecting' ? 'hsla(38,95%,55%,0.15)' : 'hsla(0,80%,60%,0.15)'}`
  return (
    <header
      className="h-10 flex items-center justify-between pl-4 pr-2 bg-bg-1 border-b border-border select-none"
      style={{ WebkitAppRegion: 'drag' }}
    >
      <div className="flex items-center gap-3">
        <span className="text-[13px] font-semibold tracking-[0.2px]">Jarvis</span>
        <span className="w-px h-3.5 bg-border-strong" />
        <div className="flex items-center gap-2 font-mono text-[11px] text-fg-3">
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: dotColor, boxShadow: dotShadow }}
          />
          <span>{providerLabel}</span>
        </div>
      </div>

      <div className="flex items-center gap-0.5" style={{ WebkitAppRegion: 'no-drag' }}>
        <PaletteButton />
        <IconBtn
          title={voiceStatus === 'listening' ? 'Voz: escuchando (click para pausar)' : voiceStatus === 'paused' ? 'Voz pausada (click para activar)' : 'Voz no disponible'}
          onClick={onToggleVoice}
          active={voiceStatus === 'listening'}
        ><Icon name="volume" /></IconBtn>
        <div className="flex gap-0.5 ml-1 pl-1.5 border-l border-border">
          <IconBtn title="Minimizar" onClick={() => window.jarvis.windowMinimize()}>
            <Icon name="minus" />
          </IconBtn>
          <IconBtn title={isMax ? 'Restaurar' : 'Maximizar'} onClick={onToggleMax}>
            <Icon name={isMax ? 'squares' : 'square'} strokeWidth={1.5} />
          </IconBtn>
          <IconBtn title="Cerrar" danger onClick={() => window.jarvis.windowClose()}>
            <Icon name="x" />
          </IconBtn>
        </div>
      </div>
    </header>
  )
}

function IconBtn({ children, title, onClick, danger = false, active = false }) {
  const base = 'inline-flex items-center justify-center w-7 h-7 rounded-md transition '
  const cls = danger
    ? base + 'text-fg-3 hover:bg-red-600 hover:text-white'
    : active
      ? base + 'text-[var(--accent)] bg-[var(--accent-muted)]'
      : base + 'text-fg-3 hover:bg-bg-3 hover:text-fg-1'
  return (
    <button type="button" onClick={onClick} title={title} className={cls}>
      {children}
    </button>
  )
}

function PaletteButton() {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(null)
  const popRef = useRef(null)
  const btnRef = useRef(null)

  // Cerrar al clicar fuera
  useEffect(() => {
    const h = (e) => {
      if (popRef.current?.contains(e.target) || btnRef.current?.contains(e.target)) return
      setOpen(false)
    }
    document.addEventListener('click', h)
    return () => document.removeEventListener('click', h)
  }, [])

  // Leer el color activo del localStorage al montar
  useEffect(() => {
    try { setActive(localStorage.getItem('jarvis.theme')) } catch {}
  }, [])

  const pick = (hex) => {
    applyTheme(hex)
    setActive(hex)
  }

  return (
    <div className="relative">
      <button
        ref={btnRef}
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen(v => !v) }}
        title="Color"
        className="inline-flex items-center justify-center w-7 h-7 rounded-md text-fg-3 hover:bg-bg-3 hover:text-fg-1 transition"
      >
        <Icon name="palette" />
      </button>

      {open && (
        <div
          ref={popRef}
          className="absolute top-[34px] right-0 min-w-[220px] p-3 rounded-lg bg-bg-2 border border-border-strong shadow-[0_8px_24px_rgba(0,0,0,0.4)] z-50"
        >
          <div className="text-[11px] font-medium text-fg-3 mb-2.5 tracking-[0.3px]">Color de acento</div>
          <div className="grid grid-cols-8 gap-1.5 mb-2.5">
            {PRESETS.map(p => (
              <button
                key={p.color}
                type="button"
                onClick={() => pick(p.color)}
                title={p.name}
                className="aspect-square rounded-full border-[1.5px] transition hover:scale-110"
                style={{
                  background: p.color,
                  borderColor: active?.toLowerCase() === p.color.toLowerCase() ? 'hsl(220,15%,96%)' : 'transparent',
                }}
              />
            ))}
          </div>
          <div className="pt-2.5 border-t border-border flex items-center justify-between gap-2.5">
            <span className="text-[11px] text-fg-2">Personalizado</span>
            <input
              type="color"
              value={active || '#ee2a55'}
              onChange={(e) => pick(e.target.value)}
              className="w-8 h-6 rounded border border-border bg-transparent cursor-pointer"
            />
          </div>
        </div>
      )}
    </div>
  )
}
