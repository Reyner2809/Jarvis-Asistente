import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useState } from 'react'

/**
 * BootScreen — pantalla de arranque cinematografica (~3.5s).
 *
 * Inspiracion: pantalla de carga estilo Opera GX / pantallas de boot HUD,
 * con identidad propia. Cinco capas en cascada:
 *
 *   - Background: degradado oscuro radial + grid sutil
 *   - Anillos concentricos animados que se expanden desde el centro
 *   - Wordmark "JARVIS" con letras separadas que entran una por una
 *   - Tagline en mono ("MARK V · DIGITAL VALET")
 *   - Barra de progreso real con steps de inicializacion (% real)
 *   - Fade-out hacia la app principal
 *
 * Los anillos y la tipografia se tinen con el acento del usuario para
 * coherencia visual.
 */
export default function BootScreen({ onDone }) {
  const [phase, setPhase] = useState(0)
  const [progress, setProgress] = useState(0)
  const [stepText, setStepText] = useState('Inicializando núcleo')

  // Steps de carga visibles
  const steps = [
    { at: 0,    text: 'Inicializando núcleo' },
    { at: 25,   text: 'Cargando modelos locales' },
    { at: 55,   text: 'Conectando bridge' },
    { at: 78,   text: 'Calibrando subsistemas' },
    { at: 95,   text: 'Online' },
  ]

  useEffect(() => {
    const t1 = setTimeout(() => setPhase(1), 100)   // anillos
    const t2 = setTimeout(() => setPhase(2), 600)   // wordmark
    const t3 = setTimeout(() => setPhase(3), 1500)  // tagline + bar
    const t4 = setTimeout(() => onDone?.(),  3500)  // fade out

    // Progreso animado
    let p = 0
    const tick = setInterval(() => {
      p = Math.min(100, p + 2.5)
      setProgress(p)
      const cur = [...steps].reverse().find(s => p >= s.at)
      if (cur) setStepText(cur.text)
      if (p >= 100) clearInterval(tick)
    }, 60)

    return () => { [t1, t2, t3, t4].forEach(clearTimeout); clearInterval(tick) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onDone])

  const letters = 'JARVIS'.split('')

  return (
    <motion.div
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className="fixed inset-0 z-[1000] flex items-center justify-center overflow-hidden"
      style={{
        background: 'radial-gradient(ellipse at center, hsl(230,15%,7%) 0%, hsl(230,12%,3%) 80%)',
      }}
    >
      {/* Grid sutil de fondo */}
      <div
        className="absolute inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage:
            'linear-gradient(var(--accent-muted) 1px, transparent 1px), linear-gradient(90deg, var(--accent-muted) 1px, transparent 1px)',
          backgroundSize: '64px 64px',
        }}
      />

      {/* Anillos concentricos expandiendose */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        {phase >= 1 && [0, 0.6, 1.2].map(d => (
          <motion.div
            key={d}
            initial={{ scale: 0.2, opacity: 0 }}
            animate={{ scale: [0.2, 1.6, 2.2], opacity: [0, 0.4, 0] }}
            transition={{ duration: 3, delay: d, repeat: Infinity, repeatDelay: 1, ease: 'easeOut' }}
            className="absolute w-[360px] h-[360px] rounded-full border"
            style={{ borderColor: 'var(--accent)' }}
          />
        ))}
      </div>

      {/* Centro: wordmark + tagline + barra */}
      <div className="relative z-10 flex flex-col items-center">

        {/* Wordmark con letras animadas una por una */}
        <div className="flex items-center" style={{ gap: '14px' }}>
          {letters.map((ch, i) => (
            <motion.span
              key={i}
              initial={{ opacity: 0, y: 16, filter: 'blur(8px)' }}
              animate={phase >= 2 ? { opacity: 1, y: 0, filter: 'blur(0px)' } : {}}
              transition={{ duration: 0.45, delay: 0.06 * i, ease: [0.2, 0.8, 0.2, 1] }}
              className="font-light"
              style={{
                fontSize: 78,
                lineHeight: 1,
                letterSpacing: 0,
                color: 'hsl(220, 15%, 96%)',
                textShadow: '0 0 30px var(--accent-glow), 0 0 60px var(--accent-muted)',
              }}
            >
              {ch}
            </motion.span>
          ))}
        </div>

        {/* Tagline */}
        <AnimatePresence>
          {phase >= 3 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
              className="mt-3 font-mono text-[11px] tracking-[6px] uppercase"
              style={{ color: 'var(--accent)' }}
            >
              MARK · V · DIGITAL VALET
            </motion.div>
          )}
        </AnimatePresence>

        {/* Barra de progreso */}
        <AnimatePresence>
          {phase >= 3 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="mt-12 w-[320px]"
            >
              <div className="flex items-center justify-between font-mono text-[10px] tracking-[1.5px] uppercase mb-2">
                <span className="text-fg-3">{stepText}</span>
                <span style={{ color: 'var(--accent)' }}>{Math.round(progress)}%</span>
              </div>
              <div className="h-[2px] w-full bg-[hsl(230,10%,15%)] overflow-hidden rounded-full">
                <motion.div
                  className="h-full"
                  style={{
                    background: 'var(--accent)',
                    boxShadow: '0 0 8px var(--accent-glow)',
                    width: `${progress}%`,
                  }}
                  transition={{ duration: 0.1 }}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Marca de version abajo */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 font-mono text-[10px] tracking-[3px] text-fg-4 uppercase">
        Jarvis Desktop · v1.0
      </div>
    </motion.div>
  )
}
