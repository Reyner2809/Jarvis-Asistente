import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef } from 'react'

const LABELS = {
  idle:      { label: 'En reposo',   sub: 'Diga "Jarvis" para comenzar' },
  thinking:  { label: 'Pensando',    sub: 'Un momento, senor...' },
  searching: { label: 'Consultando', sub: 'Buscando en internet' },
  speaking:  { label: 'Respondiendo',sub: 'A su disposicion' },
  listening: { label: 'Escuchando',  sub: 'Le escucho, senor' },
}

/* Bumps alrededor del borde */
const BUMPS = [
  { angle:   0, band: 'bass',   drift:  0.08, color: 'cyan' },
  { angle:  30, band: 'mid',    drift: -0.05, color: 'magenta' },
  { angle:  60, band: 'treble', drift:  0.06, color: 'cyan' },
  { angle:  90, band: 'low',    drift: -0.09, color: 'magenta' },
  { angle: 120, band: 'upper',  drift:  0.07, color: 'cyan' },
  { angle: 150, band: 'bass',   drift: -0.06, color: 'magenta' },
  { angle: 180, band: 'mid',    drift:  0.05, color: 'cyan' },
  { angle: 210, band: 'treble', drift: -0.08, color: 'magenta' },
  { angle: 240, band: 'low',    drift:  0.09, color: 'cyan' },
  { angle: 270, band: 'upper',  drift: -0.07, color: 'magenta' },
  { angle: 300, band: 'bass',   drift:  0.06, color: 'cyan' },
  { angle: 330, band: 'mid',    drift: -0.05, color: 'magenta' },
]

/* Blobs — desplazamiento interno reactivo al audio.
   Movimiento mas amplio para que se note la reactividad. */
const BLOB_DEFS = [
  { band: 'bass',   dx: -0.9, dy: -0.7, maxD: 50 },
  { band: 'low',    dx:  0.8, dy:  0.9, maxD: 45 },
  { band: 'mid',    dx: -0.7, dy:  1.0, maxD: 40 },
  { band: 'upper',  dx:  1.0, dy: -0.8, maxD: 38 },
  { band: 'treble', dx:  0.6, dy:  0.7, maxD: 35 },
]

const BAR_COUNT = 48

export default function Orb({ status = 'idle', wakeFlash = false }) {
  const { label, sub } = LABELS[status] || LABELS.idle

  const phaseRef   = useRef(0)
  const orbRef     = useRef(null)
  const innerRef   = useRef(null)
  const swirlRefs  = useRef([])
  const blobRefs   = useRef([])
  const bumpRefs   = useRef([])
  const barRefs    = useRef([])

  useEffect(() => {
    let raf
    const tick = () => {
      const rs   = getComputedStyle(document.documentElement)
      const root = document.documentElement.style
      const now  = performance.now()
      const t    = now * 0.001

      const bands = {
        bass:   parseFloat(rs.getPropertyValue('--audio-bass'))      || 0,
        low:    parseFloat(rs.getPropertyValue('--audio-low'))       || 0,
        mid:    parseFloat(rs.getPropertyValue('--audio-mid'))       || 0,
        upper:  parseFloat(rs.getPropertyValue('--audio-upper-mid')) || 0,
        treble: parseFloat(rs.getPropertyValue('--audio-treble'))    || 0,
        level:  parseFloat(rs.getPropertyValue('--audio-level'))     || 0,
      }

      // Wave phase — acelera con audio para que swirls internos fluyan mas rapido
      const speed = 0.02 + bands.level * 0.5
      phaseRef.current = (phaseRef.current + speed) % 360
      root.setProperty('--wave-phase', `${phaseRef.current}deg`)

      const hasAudio = bands.level > 0.05
      const bandArr = [bands.bass, bands.low, bands.mid, bands.upper, bands.treble]

      /* ==== BLOBS — movimiento interno audio-reactivo ====
         Cada blob se desplaza dentro del orbe segun su banda.
         Movimiento contenido (max 35px) para que nunca salga. */
      BLOB_DEFS.forEach((def, i) => {
        const el = blobRefs.current[i]
        if (!el) return
        const bv = bands[def.band]
        if (hasAudio) {
          const tx = bv * def.dx * def.maxD
          const ty = bv * def.dy * def.maxD
          el.style.transform = `translate(${tx.toFixed(1)}px, ${ty.toFixed(1)}px)`
          el.style.scale = (1 + bv * 0.5).toFixed(3)
        } else {
          el.style.transform = ''
          el.style.scale = ''
        }
      })

      /* ==== BUMPS — protuberancias en el borde ==== */
      const orbR = 140
      const bumpBase = 30
      BUMPS.forEach((bump, i) => {
        const el = bumpRefs.current[i]
        if (!el) return
        const bv = bands[bump.band]
        const angle = (bump.angle + t * bump.drift * 57.3) * Math.PI / 180
        const edgeR = orbR - 8
        el.style.left = `${orbR + Math.cos(angle) * edgeR - bumpBase}px`
        el.style.top  = `${orbR + Math.sin(angle) * edgeR - bumpBase}px`
        if (hasAudio && bv > 0.05) {
          el.style.transform = `scale(${(0.3 + bv * 1.0).toFixed(2)})`
          el.style.opacity   = (bv * 0.7).toFixed(3)
        } else {
          el.style.transform = 'scale(0)'
          el.style.opacity   = '0'
        }
      })

      /* ==== GLOW — pulsa con bandas individuales ====
         Cyan glow reacciona a bass/mid, magenta a upper/treble. */
      if (orbRef.current) {
        if (hasAudio) {
          const gCyan = 50 + (bands.bass + bands.mid) * 70
          const gMag  = 70 + (bands.upper + bands.treble) * 55
          orbRef.current.style.boxShadow =
            `0 0 ${gCyan}px var(--orb-glow-1), ` +
            `0 0 ${gMag}px var(--orb-glow-2), ` +
            `inset 0 0 25px rgba(0,0,0,0.4)`
        } else {
          orbRef.current.style.boxShadow = ''
        }
      }

      /* ==== INNER — blur, saturacion y brillo reactivos ==== */
      if (innerRef.current) {
        if (hasAudio) {
          const blur = 16 + bands.level * 12
          const sat  = 1.4 + bands.level * 0.8
          const bri  = 1.0 + bands.level * 0.5
          innerRef.current.style.filter = `blur(${blur}px) saturate(${sat}) brightness(${bri})`
        } else {
          innerRef.current.style.filter = ''
        }
      }

      /* ==== SWIRLS — escala pulsante por banda ==== */
      const [sw1, sw2, sw3] = swirlRefs.current
      if (hasAudio) {
        if (sw1) sw1.style.scale = (1 + bands.bass   * 0.25).toFixed(3)
        if (sw2) sw2.style.scale = (1 + bands.mid    * 0.20).toFixed(3)
        if (sw3) sw3.style.scale = (1 + bands.treble * 0.22).toFixed(3)
      } else {
        swirlRefs.current.forEach(el => { if (el) el.style.scale = '' })
      }

      /* ==== ESPECTROGRAMA ==== */
      for (let i = 0; i < BAR_COUNT; i++) {
        const el = barRefs.current[i]
        if (!el) continue
        const pos = i / (BAR_COUNT - 1)
        const bandPos = pos * 4
        const bandIdx = Math.min(Math.floor(bandPos), 3)
        const frac = bandPos - bandIdx
        const val = bandArr[bandIdx] * (1 - frac) + bandArr[bandIdx + 1] * frac
        if (hasAudio && val > 0.02) {
          el.style.height = `${2 + val * 16}px`
          el.style.opacity = (0.3 + val * 0.5).toFixed(3)
        } else {
          el.style.height = '2px'
          el.style.opacity = '0.2'
        }
      }

      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  return (
    <div className="relative flex flex-col items-center">
      <div className={'relative w-[280px] h-[280px] orb-state-' + status}>

        <div className="bump-ring">
          {BUMPS.map((b, i) => (
            <div key={i} className={`bump bump-${b.color}`} ref={el => (bumpRefs.current[i] = el)} />
          ))}
        </div>

        <div className="orb" ref={orbRef}>
          <div className="orb-inner" ref={innerRef}>
            <div className="swirl swirl-1" ref={el => (swirlRefs.current[0] = el)} />
            <div className="swirl swirl-2" ref={el => (swirlRefs.current[1] = el)} />
            <div className="swirl swirl-3" ref={el => (swirlRefs.current[2] = el)} />
            <div className="blob b1" ref={el => (blobRefs.current[0] = el)} />
            <div className="blob b2" ref={el => (blobRefs.current[1] = el)} />
            <div className="blob b3" ref={el => (blobRefs.current[2] = el)} />
            <div className="blob b4" ref={el => (blobRefs.current[3] = el)} />
            <div className="blob b5" ref={el => (blobRefs.current[4] = el)} />
          </div>
          <div className="orb-glass" />
        </div>

        <AnimatePresence>
          {wakeFlash && (
            <motion.div
              key="wake-flash"
              initial={{ opacity: 0, scale: 1 }}
              animate={{ opacity: [0, 0.7, 0], scale: [1, 1.4, 1.6] }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
              className="absolute inset-0 rounded-full pointer-events-none"
              style={{ boxShadow: '0 0 80px 20px var(--orb-glow-1)' }}
            />
          )}
        </AnimatePresence>

        <div className="absolute left-1/2 -translate-x-1/2 top-[calc(100%+16px)] text-center whitespace-nowrap">
          <AnimatePresence mode="wait">
            <motion.div
              key={status}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
            >
              <div className="font-mono text-[11px] tracking-[2px] uppercase text-fg-2 mb-1">{label}</div>
              <div className="text-[13px] text-fg-3 mb-3">{sub}</div>
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="spectrogram" style={{ position: 'absolute', top: 'calc(100% + 58px)', left: '50%', transform: 'translateX(-50%)' }}>
          {Array.from({ length: BAR_COUNT }, (_, i) => (
            <div key={i} className="spec-bar" ref={el => (barRefs.current[i] = el)} />
          ))}
        </div>
      </div>
    </div>
  )
}
