import { useCallback, useEffect, useRef, useState } from 'react'
import { connectEvents, getState, sendCommand as apiSend } from './jarvis-api.js'
import { playTtsAudio } from './audio-player.js'

/**
 * Hook central que expone el estado de Jarvis a la UI:
 *  - state: info del bridge (provider, model, etc.)
 *  - status: idle | thinking | searching | speaking
 *  - connected: estado del WebSocket
 *  - messages: conversacion [{id, who, body, tool, time, code, file, streaming}]
 *  - sendCommand(text): envia un comando, espera respuesta, actualiza messages
 */
export function useJarvis() {
  const [bridgeState, setBridgeState] = useState(null)
  const [status, setStatus] = useState('idle')   // idle | thinking | searching | speaking | listening
  const [wsStatus, setWsStatus] = useState('connecting')
  const [voiceStatus, setVoiceStatus] = useState('off') // off | listening | paused
  const [wakeFlash, setWakeFlash] = useState(false)
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const currentToolCalls = useRef([])

  // Primer fetch del estado del bridge
  useEffect(() => {
    let cancel = false
    const load = async () => {
      try {
        const s = await getState()
        if (!cancel) setBridgeState(s)
      } catch {
        // bridge puede tardar unos segundos en estar listo; reintentar
        if (!cancel) setTimeout(load, 800)
      }
    }
    load()
    return () => { cancel = true }
  }, [])

  // WebSocket de eventos
  useEffect(() => {
    const close = connectEvents(
      (ev) => handleEvent(ev),
      (s) => setWsStatus(s),
    )
    return close
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleEvent = (ev) => {
    switch (ev.type) {
      case 'thinking':
        setStatus('thinking')
        break
      case 'searching':
        setStatus('searching')
        break
      case 'route':
        if (ev.route === 'fast') setStatus('idle')
        break
      case 'tool_call':
        currentToolCalls.current.push({ name: ev.name, args: ev.args })
        setMessages(m => [...m, {
          id: crypto.randomUUID(),
          who: 'jarvis',
          tool: { name: ev.name, meta: '· ejecutando...' },
          time: nowHHmm(),
        }])
        break
      case 'response':
        // No pisar 'speaking' — el audio puede seguir sonando
        setStatus(cur => {
          if (cur === 'speaking') return cur
          return voiceStatus === 'listening' ? 'listening' : 'idle'
        })
        // Agregar al chat si la respuesta vino por voz o es el saludo inicial.
        // Las respuestas a POST /api/command ya las agrega sendCommand directamente.
        if ((ev.source === 'voice' || ev.source === 'greeting') && ev.text) {
          setMessages(m => [...m, {
            id: crypto.randomUUID(),
            who: 'jarvis',
            body: ev.text,
            time: nowHHmm(),
            greeting: ev.source === 'greeting',
          }])
        }
        break

      // ---- Eventos del voice loop ----
      case 'voice_status':
        setVoiceStatus(ev.value)
        // No pisar 'speaking' — si Jarvis esta hablando, la pausa del mic
        // es interna al TTS y no debe cambiar el estado visible del orbe.
        setStatus(cur => {
          if (cur === 'speaking') return cur
          if (ev.value === 'listening') return 'listening'
          if (ev.value === 'off' || ev.value === 'paused') return 'idle'
          return cur
        })
        break
      case 'wake_detected':
        setWakeFlash(true)
        setTimeout(() => setWakeFlash(false), 600)
        break
      case 'transcribed':
        // Mostrar lo que el mic capturo como mensaje del usuario
        setMessages(m => [...m, {
          id: crypto.randomUUID(),
          who: 'user',
          body: ev.text,
          time: nowHHmm(),
          viaVoice: true,
        }])
        break
      case 'speaking':
        setStatus(ev.value ? 'speaking' : (voiceStatus === 'listening' ? 'listening' : 'idle'))
        break
      case 'tts_audio':
        // Poner speaking INMEDIATAMENTE — no esperar al evento 'speaking'
        // del bridge que puede llegar tarde o nunca.
        setStatus('speaking')
        ;(async () => {
          try {
            const base = await window.jarvis.getBridgeUrl()
            await playTtsAudio(ev.data, ev.format, base)
            // Audio termino — volver al estado correcto
            setStatus(voiceStatus === 'listening' ? 'listening' : 'idle')
          } catch (e) { console.error('playTtsAudio', e) }
        })()
        break
      case 'error':
        // Errores se muestran como alerta en la UI, NUNCA se hablan
        setStatus(voiceStatus === 'listening' ? 'listening' : 'idle')
        setMessages(m => [...m, {
          id: crypto.randomUUID(),
          who: 'jarvis',
          body: ev.message || 'Error desconocido',
          time: nowHHmm(),
          error: true,
        }])
        break
      default:
        break
    }
  }

  const sendCommand = useCallback(async (text) => {
    const t = text.trim()
    if (!t || sending) return
    setSending(true)
    // Push mensaje del usuario al instante (optimistic UI)
    setMessages(m => [...m, {
      id: crypto.randomUUID(),
      who: 'user',
      body: t,
      time: nowHHmm(),
    }])
    currentToolCalls.current = []
    setStatus('thinking')

    try {
      const res = await apiSend(t)
      if (res.error) {
        // Error del procesamiento — mostrar como alerta, no se habla
        setMessages(m => [...m, {
          id: crypto.randomUUID(),
          who: 'jarvis',
          body: res.error,
          time: nowHHmm(),
          error: true,
        }])
      } else if (res.response) {
        setMessages(m => [...m, {
          id: crypto.randomUUID(),
          who: 'jarvis',
          body: res.response,
          time: nowHHmm(),
        }])
      }
    } catch (e) {
      setMessages(m => [...m, {
        id: crypto.randomUUID(),
        who: 'jarvis',
        body: `Error de comunicacion: ${e.message}`,
        time: nowHHmm(),
        error: true,
      }])
    } finally {
      setSending(false)
      // No pisar 'speaking' — el TTS puede seguir sonando
      setStatus(cur => cur === 'speaking' ? cur : 'idle')
    }
  }, [sending])

  const toggleVoice = useCallback(async () => {
    try {
      const base = await window.jarvis.getBridgeUrl()
      const res = await fetch(`${base}/api/voice/toggle`, { method: 'POST' })
      return await res.json()
    } catch { return null }
  }, [])

  return {
    bridgeState,
    status,
    wsStatus,
    voiceStatus,
    wakeFlash,
    messages,
    sending,
    sendCommand,
    toggleVoice,
  }
}

function nowHHmm() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
