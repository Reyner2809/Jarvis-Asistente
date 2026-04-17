import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const STEPS = ['bienvenida', 'hardware', 'provider', 'telegram', 'instalacion', 'autostart', 'listo']

const CLOUD_PROVIDERS = [
  { id: 'claude',  name: 'Claude (Anthropic)', keyHint: 'sk-ant-...', url: 'console.anthropic.com' },
  { id: 'openai',  name: 'OpenAI (GPT)',       keyHint: 'sk-...',     url: 'platform.openai.com' },
  { id: 'gemini',  name: 'Google Gemini',       keyHint: 'AI...',      url: 'aistudio.google.com/apikey' },
]

export default function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(0)
  const [sysInfo, setSysInfo] = useState(null)
  const [provider, setProvider] = useState('ollama')
  const [ollamaModel, setOllamaModel] = useState('llama3.2')
  const [apiKey, setApiKey] = useState('')
  const [telegramToken, setTelegramToken] = useState('')
  const [telegramUserId, setTelegramUserId] = useState('')
  const [telegramBot, setTelegramBot] = useState(null)
  const [telegramSkip, setTelegramSkip] = useState(false)
  const [autoStart, setAutoStart] = useState(true)
  // Instalacion
  const [installLog, setInstallLog] = useState([])
  const [installing, setInstalling] = useState(false)
  const [installDone, setInstallDone] = useState(false)

  const currentStep = STEPS[step]

  useEffect(() => { window.jarvis.getSystemInfo().then(setSysInfo) }, [])

  const log = useCallback((msg, type = 'info') => {
    setInstallLog(prev => [...prev, { msg, type, time: Date.now() }])
  }, [])

  const next = () => setStep(s => Math.min(s + 1, STEPS.length - 1))
  const prev = () => setStep(s => Math.max(s - 1, 0))

  // ---- Verificar token Telegram ----
  const verifyTelegram = async () => {
    if (!telegramToken) return
    const res = await window.jarvis.verifyTelegram(telegramToken)
    if (res.ok) setTelegramBot(res.username)
    else setTelegramBot(null)
  }

  // ---- Proceso de instalacion completo ----
  const runInstall = async () => {
    setInstalling(true)
    setInstallLog([])

    const config = {
      provider,
      ollama_model: ollamaModel,
      vision_model: '',
      openai_key: '', anthropic_key: '', gemini_key: '',
      telegram_token: telegramSkip ? '' : telegramToken,
      telegram_user_id: telegramSkip ? '' : telegramUserId,
    }

    // Setear API key segun provider
    if (provider === 'claude') config.anthropic_key = apiKey
    else if (provider === 'openai') config.openai_key = apiKey
    else if (provider === 'gemini') config.gemini_key = apiKey

    // --- OLLAMA ---
    if (provider === 'ollama') {
      log('Verificando Ollama...', 'info')
      const hasOllama = await window.jarvis.checkOllama()

      if (hasOllama) {
        log('Ollama ya esta instalado', 'ok')
      } else {
        log('Instalando Ollama (puede tardar 2-5 minutos)...', 'warn')
        const res = await window.jarvis.installOllama()
        if (res.ok) {
          log('Ollama instalado correctamente', 'ok')
        } else {
          log('No se pudo instalar Ollama automaticamente. Instalalo desde ollama.ai', 'error')
          setInstalling(false)
          return
        }
      }

      // Iniciar Ollama
      log('Iniciando Ollama...', 'info')
      const started = await window.jarvis.startOllama()
      if (started) {
        log('Ollama corriendo', 'ok')
      } else {
        log('No se pudo iniciar Ollama. Abrelo manualmente.', 'warn')
      }

      // Descargar modelo ligero (siempre)
      log('Verificando modelo llama3.2 (ligero)...', 'info')
      const models = await window.jarvis.ollamaModels()
      if (models.includes('llama3.2')) {
        log('llama3.2 ya descargado', 'ok')
      } else {
        log('Descargando llama3.2 (~2GB)...', 'warn')
        const res = await window.jarvis.ollamaPull('llama3.2')
        log(res.ok ? 'llama3.2 descargado' : 'Error descargando llama3.2', res.ok ? 'ok' : 'error')
      }

      // Descargar modelo principal si es diferente
      if (ollamaModel !== 'llama3.2') {
        log(`Verificando modelo ${ollamaModel}...`, 'info')
        const models2 = await window.jarvis.ollamaModels()
        if (models2.includes(ollamaModel)) {
          log(`${ollamaModel} ya descargado`, 'ok')
        } else {
          const sizeHint = ollamaModel.includes('gemma4') ? '~9.6GB' : ollamaModel.includes('12b') ? '~7GB' : '~2GB'
          log(`Descargando ${ollamaModel} (${sizeHint}). Esto puede tardar varios minutos...`, 'warn')
          const res = await window.jarvis.ollamaPull(ollamaModel)
          if (res.ok) {
            log(`${ollamaModel} descargado`, 'ok')
            if (ollamaModel.includes('gemma4')) config.vision_model = ollamaModel
          } else {
            log(`Error descargando ${ollamaModel}. Usando llama3.2 como principal.`, 'error')
            config.ollama_model = 'llama3.2'
          }
        }
      }
    }

    // --- FFmpeg ---
    log('Verificando FFmpeg...', 'info')
    const hasFF = await window.jarvis.checkFFmpeg()
    if (hasFF) {
      log('FFmpeg ya instalado', 'ok')
    } else {
      log('Instalando FFmpeg (necesario para audio)...', 'warn')
      const res = await window.jarvis.installFFmpeg()
      log(res.ok ? 'FFmpeg instalado' : 'FFmpeg no se pudo instalar. Instala manualmente: winget install Gyan.FFmpeg', res.ok ? 'ok' : 'warn')
    }

    // --- Generar .env ---
    log('Generando configuracion (.env)...', 'info')
    try {
      await window.jarvis.writeEnv(config)
      log('Configuracion guardada', 'ok')
    } catch (e) {
      log(`Error guardando configuracion: ${e}`, 'error')
    }

    log('Instalacion completa', 'ok')
    setInstallDone(true)
    setInstalling(false)
  }

  const finish = async () => {
    try { await window.jarvis.setAutoStart(autoStart) } catch {}
    localStorage.setItem('jarvis.setupDone', 'true')
    onComplete()
  }

  const canNext = () => {
    if (currentStep === 'provider' && provider !== 'ollama' && !apiKey) return false
    if (currentStep === 'instalacion' && !installDone) return false
    return true
  }

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'hsl(230, 10%, 4%)' }}
    >
      <div className="w-full max-w-[560px] px-6 max-h-[90vh] overflow-y-auto">
        {/* Progress */}
        <div className="flex gap-1.5 mb-6 px-1">
          {STEPS.map((_, i) => (
            <div key={i} className="h-1 flex-1 rounded-full transition-colors duration-300"
              style={{ background: i <= step ? 'var(--accent, hsl(190,100%,60%))' : 'hsl(220,10%,18%)' }} />
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={currentStep}
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}>

            {/* =============== BIENVENIDA =============== */}
            {currentStep === 'bienvenida' && (
              <div className="text-center">
                <h1 className="text-2xl font-semibold text-fg-1 mb-2">Bienvenido a Jarvis</h1>
                <p className="text-fg-3 text-[14px] leading-relaxed mb-2">
                  Tu asistente de IA personal. Vamos a configurar todo para que funcione perfecto en tu PC.
                </p>
                <p className="text-fg-3 text-[13px] opacity-60">Esto incluye instalar el cerebro de IA, configurar Telegram y mas.</p>
              </div>
            )}

            {/* =============== HARDWARE =============== */}
            {currentStep === 'hardware' && (
              <div>
                <h2 className="text-xl font-semibold text-fg-1 mb-1">Tu equipo</h2>
                <p className="text-fg-3 text-[13px] mb-5">Detectamos tu hardware para recomendarte la mejor configuracion.</p>
                {sysInfo ? (
                  <div className="space-y-3">
                    <InfoRow label="CPU" value={sysInfo.cpuModel} sub={`${sysInfo.cpuCores} nucleos`} />
                    <InfoRow label="RAM" value={`${sysInfo.totalRAM} GB`} sub={sysInfo.totalRAM >= 16 ? 'Excelente' : sysInfo.totalRAM >= 8 ? 'Bueno' : 'Limitado'} />
                    <InfoRow label="GPU" value={sysInfo.gpu} />
                  </div>
                ) : (
                  <div className="text-fg-3 text-sm animate-pulse">Detectando hardware...</div>
                )}
                {sysInfo && sysInfo.totalRAM < 8 && (
                  <div className="mt-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-[12px]">
                    Tu PC tiene menos de 8GB de RAM. Recomendamos usar un proveedor en la nube.
                  </div>
                )}
              </div>
            )}

            {/* =============== PROVIDER =============== */}
            {currentStep === 'provider' && (
              <div>
                <h2 className="text-xl font-semibold text-fg-1 mb-1">Cerebro de Jarvis</h2>
                <p className="text-fg-3 text-[13px] mb-4">Elige que IA usara Jarvis. Puedes cambiarlo despues.</p>

                {/* Ollama */}
                <ProviderBtn
                  selected={provider === 'ollama'} onClick={() => setProvider('ollama')}
                  name="Ollama — GRATIS, local, sin internet"
                  desc="Corre en tu PC. No necesitas pagar ni crear cuentas. Privado."
                  badge="RECOMENDADO"
                />

                {/* Cloud */}
                {CLOUD_PROVIDERS.map(p => (
                  <ProviderBtn key={p.id}
                    selected={provider === p.id} onClick={() => setProvider(p.id)}
                    name={p.name} desc={`Requiere API key de ${p.url}`}
                  />
                ))}

                {/* Modelo Ollama */}
                {provider === 'ollama' && sysInfo && (
                  <div className="mt-4">
                    <div className="text-[12px] text-fg-3 mb-2 font-medium">Modelo:</div>
                    <div className="space-y-1.5">
                      <ModelBtn selected={ollamaModel === 'llama3.2'} onClick={() => setOllamaModel('llama3.2')}
                        name="Llama 3.2" desc="Rapido, ligero. 4GB+ RAM" disabled={false} />
                      {sysInfo.totalRAM >= 16 && (
                        <ModelBtn selected={ollamaModel === 'gemma4:e4b'} onClick={() => setOllamaModel('gemma4:e4b')}
                          name="Gemma 4 E4B" desc="Mas inteligente, vision. 16GB+ RAM" disabled={sysInfo.totalRAM < 16} />
                      )}
                    </div>
                  </div>
                )}

                {/* API Key */}
                {provider !== 'ollama' && (
                  <div className="mt-4">
                    <label className="text-[12px] text-fg-3 mb-1.5 block font-medium">API Key</label>
                    <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)}
                      placeholder={CLOUD_PROVIDERS.find(p => p.id === provider)?.keyHint || 'API key'}
                      className="w-full px-3 py-2 rounded-lg bg-[hsl(220,10%,8%)] border border-[hsl(220,10%,18%)] text-fg-1 text-[13px] placeholder:text-fg-3/40 focus:outline-none focus:border-[var(--accent)]" />
                  </div>
                )}
              </div>
            )}

            {/* =============== TELEGRAM =============== */}
            {currentStep === 'telegram' && (
              <div>
                <h2 className="text-xl font-semibold text-fg-1 mb-1">Telegram (opcional)</h2>
                <p className="text-fg-3 text-[13px] mb-4">
                  Controla Jarvis desde tu celular: envia mensajes, audios, fotos y documentos.
                </p>

                {telegramSkip ? (
                  <div>
                    <p className="text-fg-3 text-[13px] mb-3">Omitido. Puedes configurarlo despues.</p>
                    <button onClick={() => setTelegramSkip(false)} className="text-[12px] text-[var(--accent)] hover:underline">Quiero configurarlo</button>
                  </div>
                ) : (
                  <div>
                    {/* Guia */}
                    <div className="bg-[hsl(220,10%,8%)] rounded-lg p-4 mb-4 text-[12px] text-fg-3 space-y-1.5">
                      <div className="text-fg-2 font-medium mb-2">Como crear tu bot:</div>
                      <div>1. Abre Telegram y busca <span className="text-fg-1 font-medium">@BotFather</span></div>
                      <div>2. Envia <span className="text-fg-1 font-medium">/newbot</span></div>
                      <div>3. Dale un nombre y username (terminado en "bot")</div>
                      <div>4. BotFather te dara un <span className="text-fg-1 font-medium">token</span> — copialo abajo</div>
                    </div>

                    <label className="text-[12px] text-fg-3 mb-1 block">Token del bot</label>
                    <div className="flex gap-2 mb-3">
                      <input type="text" value={telegramToken} onChange={e => { setTelegramToken(e.target.value); setTelegramBot(null) }}
                        placeholder="123456789:ABCdefGHI..."
                        className="flex-1 px-3 py-2 rounded-lg bg-[hsl(220,10%,8%)] border border-[hsl(220,10%,18%)] text-fg-1 text-[13px] placeholder:text-fg-3/40 focus:outline-none focus:border-[var(--accent)]" />
                      <button onClick={verifyTelegram} disabled={!telegramToken}
                        className="px-3 py-2 rounded-lg text-[12px] font-medium text-white disabled:opacity-30"
                        style={{ background: 'var(--accent)' }}>Verificar</button>
                    </div>
                    {telegramBot && <div className="text-green-400 text-[12px] mb-3">Bot valido: @{telegramBot}</div>}

                    {/* User ID */}
                    <div className="bg-[hsl(220,10%,8%)] rounded-lg p-4 mb-3 text-[12px] text-fg-3 space-y-1.5">
                      <div className="text-fg-2 font-medium mb-2">Tu User ID (seguridad):</div>
                      <div>1. Busca <span className="text-fg-1 font-medium">@userinfobot</span> en Telegram</div>
                      <div>2. Envia <span className="text-fg-1 font-medium">/start</span></div>
                      <div>3. Copia el numero <span className="text-fg-1 font-medium">Id</span> que te responde</div>
                    </div>

                    <label className="text-[12px] text-fg-3 mb-1 block">Tu User ID</label>
                    <input type="text" value={telegramUserId} onChange={e => setTelegramUserId(e.target.value)}
                      placeholder="123456789"
                      className="w-full px-3 py-2 rounded-lg bg-[hsl(220,10%,8%)] border border-[hsl(220,10%,18%)] text-fg-1 text-[13px] placeholder:text-fg-3/40 focus:outline-none focus:border-[var(--accent)] mb-3" />

                    <button onClick={() => setTelegramSkip(true)} className="text-[12px] text-fg-3 hover:text-fg-2">Omitir Telegram</button>
                  </div>
                )}
              </div>
            )}

            {/* =============== INSTALACION =============== */}
            {currentStep === 'instalacion' && (
              <div>
                <h2 className="text-xl font-semibold text-fg-1 mb-1">Instalacion</h2>
                <p className="text-fg-3 text-[13px] mb-4">
                  {installing ? 'Instalando componentes...' : installDone ? 'Instalacion completa.' : 'Presiona "Instalar" para comenzar.'}
                </p>

                {/* Log */}
                <div className="bg-[hsl(220,10%,6%)] rounded-lg p-3 h-[220px] overflow-y-auto font-mono text-[11px] space-y-1 mb-4">
                  {installLog.length === 0 && !installing && (
                    <div className="text-fg-3 opacity-50">Esperando...</div>
                  )}
                  {installLog.map((l, i) => (
                    <div key={i} className={l.type === 'ok' ? 'text-green-400' : l.type === 'error' ? 'text-red-400' : l.type === 'warn' ? 'text-yellow-400' : 'text-fg-3'}>
                      {l.type === 'ok' ? '  ' : l.type === 'error' ? '  ' : l.type === 'warn' ? '  ' : '  '} {l.msg}
                    </div>
                  ))}
                  {installing && <div className="text-fg-3 animate-pulse">  Procesando...</div>}
                </div>

                {!installDone && !installing && (
                  <button onClick={runInstall}
                    className="w-full py-2.5 rounded-lg text-[13px] font-medium text-white"
                    style={{ background: 'var(--accent)' }}>
                    Instalar
                  </button>
                )}
              </div>
            )}

            {/* =============== AUTOSTART =============== */}
            {currentStep === 'autostart' && (
              <div>
                <h2 className="text-xl font-semibold text-fg-1 mb-1">Inicio automatico</h2>
                <p className="text-fg-3 text-[13px] mb-5">Jarvis puede iniciar con Windows para estar siempre disponible.</p>
                <button onClick={() => setAutoStart(v => !v)}
                  className={`w-full p-4 rounded-lg border transition flex items-center justify-between ${
                    autoStart ? 'border-[var(--accent)] bg-[var(--accent-muted)]' : 'border-[hsl(220,10%,18%)] bg-[hsl(220,10%,8%)]'
                  }`}>
                  <div className="text-left">
                    <div className="text-[13px] font-medium text-fg-1">Iniciar con Windows</div>
                    <div className="text-[11px] text-fg-3">Jarvis se abrira automaticamente al encender tu PC</div>
                  </div>
                  <div className={`w-10 h-6 rounded-full transition-colors ${autoStart ? 'bg-[var(--accent)]' : 'bg-[hsl(220,10%,25%)]'}`}>
                    <div className={`w-5 h-5 mt-0.5 rounded-full bg-white shadow transition-transform ${autoStart ? 'translate-x-[18px]' : 'translate-x-0.5'}`} />
                  </div>
                </button>
              </div>
            )}

            {/* =============== LISTO =============== */}
            {currentStep === 'listo' && (
              <div className="text-center">
                <h2 className="text-2xl font-semibold text-fg-1 mb-2">Todo listo</h2>
                <p className="text-fg-3 text-[14px] mb-4">Jarvis esta configurado y listo para ayudarte.</p>
                <div className="text-left bg-[hsl(220,10%,8%)] rounded-lg p-4 space-y-2 text-[12px]">
                  <SummaryRow label="Proveedor" value={provider === 'ollama' ? 'Ollama (Local)' : CLOUD_PROVIDERS.find(p => p.id === provider)?.name} />
                  {provider === 'ollama' && <SummaryRow label="Modelo" value={ollamaModel} />}
                  <SummaryRow label="Telegram" value={telegramSkip || !telegramToken ? 'No configurado' : `@${telegramBot || 'configurado'}`} />
                  <SummaryRow label="Inicio automatico" value={autoStart ? 'Si' : 'No'} />
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Botones */}
        <div className="flex justify-between mt-6 mb-4">
          {step > 0 && currentStep !== 'instalacion' ? (
            <button onClick={prev} className="px-4 py-2 text-[13px] text-fg-3 hover:text-fg-1 transition">Atras</button>
          ) : <div />}

          {currentStep === 'listo' ? (
            <button onClick={finish} className="px-6 py-2.5 rounded-lg text-[13px] font-medium text-white" style={{ background: 'var(--accent)' }}>
              Comenzar
            </button>
          ) : currentStep === 'instalacion' ? (
            installDone ? (
              <button onClick={next} className="px-6 py-2.5 rounded-lg text-[13px] font-medium text-white" style={{ background: 'var(--accent)' }}>
                Siguiente
              </button>
            ) : null
          ) : (
            <button onClick={next} disabled={!canNext()}
              className="px-6 py-2.5 rounded-lg text-[13px] font-medium text-white transition disabled:opacity-30"
              style={{ background: 'var(--accent)' }}>
              Siguiente
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function InfoRow({ label, value, sub }) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-[hsl(220,10%,8%)] border border-[hsl(220,10%,15%)]">
      <span className="text-[12px] text-fg-3 font-medium">{label}</span>
      <div className="text-right">
        <span className="text-[13px] text-fg-1">{value}</span>
        {sub && <span className="text-[11px] text-fg-3 ml-2">({sub})</span>}
      </div>
    </div>
  )
}

function ProviderBtn({ selected, onClick, name, desc, badge }) {
  return (
    <button onClick={onClick}
      className={`w-full text-left p-3 rounded-lg border transition mb-2 ${
        selected ? 'border-[var(--accent)] bg-[var(--accent-muted)]' : 'border-[hsl(220,10%,18%)] bg-[hsl(220,10%,8%)] hover:border-[hsl(220,10%,28%)]'
      }`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[13px] font-medium text-fg-1">{name}</div>
          <div className="text-[11px] text-fg-3">{desc}</div>
        </div>
        {badge && <span className="text-[9px] font-bold px-2 py-0.5 rounded-full" style={{ background: 'var(--accent)', color: 'white' }}>{badge}</span>}
      </div>
    </button>
  )
}

function ModelBtn({ selected, onClick, name, desc, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`w-full text-left p-3 rounded-lg border transition ${
        selected ? 'border-[var(--accent)] bg-[var(--accent-muted)]' : disabled ? 'border-[hsl(220,10%,15%)] opacity-40 cursor-not-allowed' : 'border-[hsl(220,10%,18%)] hover:border-[hsl(220,10%,28%)]'
      }`}>
      <div className="text-[13px] font-medium text-fg-1">{name}</div>
      <div className="text-[11px] text-fg-3">{desc}</div>
    </button>
  )
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex justify-between">
      <span className="text-fg-3">{label}</span>
      <span className="text-fg-1 font-medium">{value}</span>
    </div>
  )
}
