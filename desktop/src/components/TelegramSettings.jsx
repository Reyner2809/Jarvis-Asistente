import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

/**
 * Modal para ver y actualizar credenciales de Telegram.
 *
 * Muestra los valores actuales de %APPDATA%\Jarvis\.env (campos
 * TELEGRAM_BOT_TOKEN / TELEGRAM_ALLOWED_USERS / TELEGRAM_ENABLE_VOICE),
 * permite verificarlos contra la API de Telegram y guardar los cambios
 * sin tocar el resto del .env. Al guardar, reinicia el bridge.
 */
export default function TelegramSettings({ open, onClose }) {
  const [loaded, setLoaded] = useState(false)
  const [token, setToken] = useState('')
  const [userId, setUserId] = useState('')
  const [enableVoice, setEnableVoice] = useState(true)
  const [showToken, setShowToken] = useState(false)

  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState(null) // null | {ok, username?}

  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState('')

  useEffect(() => {
    if (!open) return
    setSavedMsg('')
    setVerifyResult(null)
    setLoaded(false)
    window.jarvis.readTelegram().then((data) => {
      setToken(data.token || '')
      setUserId(data.user_id || '')
      setEnableVoice(!!data.enable_voice)
      setLoaded(true)
    })
  }, [open])

  const verify = async () => {
    if (!token) return
    setVerifying(true)
    setVerifyResult(null)
    try {
      const r = await window.jarvis.verifyTelegram(token)
      setVerifyResult(r)
    } catch {
      setVerifyResult({ ok: false })
    } finally {
      setVerifying(false)
    }
  }

  const save = async () => {
    setSaving(true)
    setSavedMsg('')
    try {
      await window.jarvis.updateTelegram({ token, user_id: userId, enable_voice: enableVoice })
      setSavedMsg('Guardado. Reiniciando bridge...')
      await window.jarvis.restartBridge()
      setSavedMsg('Listo. Telegram activo con la nueva configuracion.')
      setTimeout(() => { setSavedMsg(''); onClose?.() }, 1200)
    } catch (e) {
      setSavedMsg(`Error: ${e?.message || e}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="w-full max-w-[520px] rounded-xl border border-[hsl(220,10%,18%)] bg-[hsl(230,10%,6%)] p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[15px] font-semibold text-fg-1">Configuracion de Telegram</h2>
              <button onClick={onClose} className="text-fg-3 hover:text-fg-1 text-sm px-2">✕</button>
            </div>
            <p className="text-[12px] text-fg-3 mb-4 leading-relaxed">
              Actualiza tu token y User ID de Telegram. Si no tienes, ve a <span className="text-fg-1 font-medium">@BotFather</span> y <span className="text-fg-1 font-medium">@userinfobot</span>.
            </p>

            {!loaded ? (
              <div className="text-fg-3 text-sm animate-pulse py-6 text-center">Cargando...</div>
            ) : (
              <div className="space-y-4">
                {/* Token */}
                <div>
                  <label className="text-[11px] text-fg-3 mb-1 block font-medium">Token del bot</label>
                  <div className="flex gap-2">
                    <input
                      type={showToken ? 'text' : 'password'}
                      value={token}
                      onChange={(e) => { setToken(e.target.value); setVerifyResult(null) }}
                      placeholder="123456:ABC-DEF..."
                      className="flex-1 px-3 py-2 rounded-lg bg-[hsl(220,10%,8%)] border border-[hsl(220,10%,18%)] text-fg-1 text-[13px] placeholder:text-fg-3/40 focus:outline-none focus:border-[var(--accent)]"
                    />
                    <button
                      onClick={() => setShowToken((v) => !v)}
                      className="px-3 py-2 rounded-lg text-[12px] text-fg-3 hover:text-fg-1 border border-[hsl(220,10%,18%)] hover:bg-[hsl(220,10%,10%)]"
                      title={showToken ? 'Ocultar' : 'Mostrar'}
                    >
                      {showToken ? 'Ocultar' : 'Ver'}
                    </button>
                    <button
                      onClick={verify}
                      disabled={!token || verifying}
                      className="px-3 py-2 rounded-lg text-[12px] font-medium text-white disabled:opacity-30"
                      style={{ background: 'var(--accent)' }}
                    >
                      {verifying ? '...' : 'Verificar'}
                    </button>
                  </div>
                  {verifyResult?.ok && (
                    <div className="text-green-400 text-[11px] mt-1.5">Bot valido: @{verifyResult.username}</div>
                  )}
                  {verifyResult && !verifyResult.ok && (
                    <div className="text-red-400 text-[11px] mt-1.5">Token invalido o sin conexion.</div>
                  )}
                </div>

                {/* User ID */}
                <div>
                  <label className="text-[11px] text-fg-3 mb-1 block font-medium">Tu User ID (autorizado)</label>
                  <input
                    type="text"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    placeholder="123456789"
                    className="w-full px-3 py-2 rounded-lg bg-[hsl(220,10%,8%)] border border-[hsl(220,10%,18%)] text-fg-1 text-[13px] placeholder:text-fg-3/40 focus:outline-none focus:border-[var(--accent)]"
                  />
                  <div className="text-[11px] text-fg-3 mt-1">Varios IDs: separalos con coma.</div>
                </div>

                {/* Voz */}
                <label className="flex items-center justify-between cursor-pointer">
                  <div>
                    <div className="text-[13px] text-fg-1 font-medium">Respuestas por voz</div>
                    <div className="text-[11px] text-fg-3">Si envias un audio, Jarvis responde con audio.</div>
                  </div>
                  <div className={`w-10 h-6 rounded-full transition-colors ${enableVoice ? 'bg-[var(--accent)]' : 'bg-[hsl(220,10%,25%)]'}`}
                       onClick={() => setEnableVoice((v) => !v)}>
                    <div className={`w-5 h-5 mt-0.5 rounded-full bg-white shadow transition-transform ${enableVoice ? 'translate-x-[18px]' : 'translate-x-0.5'}`} />
                  </div>
                </label>

                {savedMsg && (
                  <div className={`text-[12px] ${savedMsg.startsWith('Error') ? 'text-red-400' : 'text-fg-2'}`}>
                    {savedMsg}
                  </div>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    onClick={onClose}
                    className="px-4 py-2 rounded-lg text-[13px] text-fg-3 hover:text-fg-1"
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={save}
                    disabled={saving}
                    className="px-5 py-2 rounded-lg text-[13px] font-medium text-white disabled:opacity-40"
                    style={{ background: 'var(--accent)' }}
                  >
                    {saving ? 'Guardando...' : 'Guardar y reiniciar'}
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
