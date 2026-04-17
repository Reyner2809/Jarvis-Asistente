/**
 * Cliente API + WebSocket para el bridge Python.
 *
 * Encapsula:
 *  - getState() / healthCheck()
 *  - sendCommand(text)
 *  - WebSocket persistente con auto-reconnect que emite eventos al consumer.
 */

let cachedBridgeUrl = null
let cachedWsUrl = null

async function getUrls() {
  if (!cachedBridgeUrl) cachedBridgeUrl = await window.jarvis.getBridgeUrl()
  if (!cachedWsUrl) cachedWsUrl = await window.jarvis.getBridgeWsUrl()
  return { http: cachedBridgeUrl, ws: cachedWsUrl }
}

export async function healthCheck() {
  const { http } = await getUrls()
  const res = await fetch(`${http}/api/health`)
  if (!res.ok) throw new Error(`health ${res.status}`)
  return res.json()
}

export async function getState() {
  const { http } = await getUrls()
  const res = await fetch(`${http}/api/state`)
  if (!res.ok) throw new Error(`state ${res.status}`)
  return res.json()
}

export async function sendCommand(text) {
  const { http } = await getUrls()
  const res = await fetch(`${http}/api/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`command ${res.status}`)
  return res.json()
}

/**
 * Conecta al WebSocket de eventos con reintento automatico.
 *
 * @param {(event: object) => void} onEvent  callback por cada evento
 * @param {(status: 'connected'|'disconnected'|'reconnecting') => void} onStatus
 * @returns {() => void} funcion para cerrar la conexion
 */
export function connectEvents(onEvent, onStatus) {
  let ws = null
  let closed = false
  let retryMs = 500

  const open = async () => {
    if (closed) return
    const { ws: url } = await getUrls()
    ws = new WebSocket(url)

    ws.onopen = () => {
      retryMs = 500
      onStatus?.('connected')
    }
    ws.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data)
        onEvent?.(ev)
      } catch {}
    }
    ws.onclose = () => {
      if (closed) return
      onStatus?.('reconnecting')
      setTimeout(open, retryMs)
      retryMs = Math.min(retryMs * 2, 5000)  // backoff hasta 5s
    }
    ws.onerror = () => { /* onclose se encarga */ }
  }

  open()

  return () => {
    closed = true
    onStatus?.('disconnected')
    try { ws?.close() } catch {}
  }
}
