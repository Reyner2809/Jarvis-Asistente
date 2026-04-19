import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import Header from './components/Header.jsx'
import Orb from './components/Orb.jsx'
import SidePanel from './components/SidePanel.jsx'
import PanelToggle from './components/PanelToggle.jsx'
import BootScreen from './components/BootScreen.jsx'
import SetupWizard from './components/SetupWizard.jsx'
import { loadSavedTheme } from './lib/theme.js'
import { useJarvis } from './lib/useJarvis.js'

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [isMax, setIsMax] = useState(false)
  const [booting, setBooting] = useState(true)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [setupChecked, setSetupChecked] = useState(false)

  const jarvis = useJarvis()

  useEffect(() => { loadSavedTheme() }, [])

  // Verificar si es primera ejecucion:
  //  - Si no hay flag setupDone: mostrar wizard
  //  - Si el flag esta pero falta el .env de usuario: mostrar wizard igual
  //    (esto evita que un flag residual de un install previo saltee la config).
  useEffect(() => {
    (async () => {
      const done = localStorage.getItem('jarvis.setupDone')
      let envOk = false
      try { envOk = await window.jarvis.envExists() } catch {}
      setNeedsSetup(!done || !envOk)
      setSetupChecked(true)
    })()
  }, [])

  useEffect(() => {
    window.jarvis.windowIsMaximized().then(setIsMax)
    const unsub = window.jarvis.onMaximizeChange(setIsMax)
    return () => { unsub?.() }
  }, [])

  const toggleMax = async () => {
    const next = await window.jarvis.windowToggleMaximize()
    if (typeof next === 'boolean') setIsMax(next)
  }

  const providerLabel = jarvis.bridgeState
    ? `${jarvis.bridgeState.provider.toUpperCase()} · ${jarvis.bridgeState.light_model}`
    : 'Inicializando...'

  // No renderizar nada hasta verificar si necesita setup
  if (!setupChecked) return null

  // Wizard de primera ejecucion
  if (needsSetup) {
    return <SetupWizard onComplete={() => setNeedsSetup(false)} />
  }

  return (
    <div className="h-full w-full flex flex-col relative">
      <AnimatePresence>
        {booting && <BootScreen onDone={() => setBooting(false)} />}
      </AnimatePresence>

      <Header
        providerLabel={providerLabel}
        wsStatus={jarvis.wsStatus}
        voiceStatus={jarvis.voiceStatus}
        onToggleVoice={jarvis.toggleVoice}
        isMax={isMax}
        onToggleMax={toggleMax}
      />

      <div
        className="flex-1 grid overflow-hidden transition-[grid-template-columns] duration-[350ms] ease-[cubic-bezier(0.4,0,0.2,1)]"
        style={{ gridTemplateColumns: collapsed ? '1fr 0' : '1fr 360px' }}
      >
        <main
          className="relative flex items-center justify-center overflow-hidden"
          style={{ background: 'radial-gradient(ellipse at center, hsl(230,15%,6%) 0%, hsl(230,10%,4%) 70%)' }}
        >
          <Orb status={jarvis.status} wakeFlash={jarvis.wakeFlash} />
          <PanelToggle collapsed={collapsed} onClick={() => setCollapsed(v => !v)} />
        </main>

        <div
          className="overflow-hidden transition-opacity duration-200"
          style={{ opacity: collapsed ? 0 : 1, pointerEvents: collapsed ? 'none' : 'auto' }}
        >
          <SidePanel
            messages={jarvis.messages}
            onSend={jarvis.sendCommand}
            sending={jarvis.sending}
          />
        </div>
      </div>
    </div>
  )
}
