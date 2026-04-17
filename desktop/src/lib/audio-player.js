/**
 * Reproductor de audio TTS con analyzer para animacion audio-reactiva.
 *
 * Recibe base64 del bridge, decodifica, crea un AudioContext + AnalyserNode,
 * actualiza la CSS var --audio-level cada frame con el RMS normalizado del
 * audio que esta sonando. El orbe escucha esa var y escala/brilla proporcional.
 *
 * Al terminar, avisa al bridge via POST /api/voice/tts_ended para que libere
 * el mic. Tambien hace fade-out suave del audio-level para que el orbe
 * transicione sin saltos.
 */

let _audioCtx = null
function getAudioContext() {
  if (!_audioCtx || _audioCtx.state === 'closed') {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  }
  return _audioCtx
}

let _currentUrl = null

export async function playTtsAudio(base64Data, format, bridgeUrl) {
  // Decodificar base64 a blob
  const binary = atob(base64Data)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  const mime = format === 'wav' ? 'audio/wav' : 'audio/mpeg'
  const blob = new Blob([bytes], { type: mime })

  // Limpiar URL anterior si habia
  if (_currentUrl) { try { URL.revokeObjectURL(_currentUrl) } catch {} }
  const url = URL.createObjectURL(blob)
  _currentUrl = url

  const audio = new Audio(url)
  audio.crossOrigin = 'anonymous'

  const ctx = getAudioContext()
  // Algunos browsers requieren user-gesture para arrancar el context
  if (ctx.state === 'suspended') {
    try { await ctx.resume() } catch {}
  }

  const source = ctx.createMediaElementSource(audio)
  const analyser = ctx.createAnalyser()
  analyser.fftSize = 1024
  analyser.smoothingTimeConstant = 0.2        // muy bajo — sigue cada silaba
  source.connect(analyser)
  analyser.connect(ctx.destination)

  const freqData = new Uint8Array(analyser.frequencyBinCount)
  const sampleRate = ctx.sampleRate
  const nyquist = sampleRate / 2
  const binHz = nyquist / analyser.frequencyBinCount
  let raf = null

  // Promedio de amplitud entre dos frecuencias (en Hz) -> 0..255
  const bandAvg = (minHz, maxHz) => {
    const minBin = Math.max(0, Math.floor(minHz / binHz))
    const maxBin = Math.min(freqData.length, Math.ceil(maxHz / binHz))
    if (maxBin <= minBin) return 0
    let s = 0
    for (let i = minBin; i < maxBin; i++) s += freqData[i]
    return s / (maxBin - minBin)
  }

  // Curva conservadora: div alto + exponente lineal = mucho rango dinamico.
  // Solo picos reales de volumen llegan cerca de 1.0.
  const curve = (v, div = 90) => Math.max(0, Math.min(1, v / div))

  const tick = () => {
    if (audio.paused || audio.ended) return
    analyser.getByteFrequencyData(freqData)

    const bass     = curve(bandAvg(80,   250),  80)
    const low      = curve(bandAvg(250,  500),  85)
    const mid      = curve(bandAvg(500, 1500),  90)
    const upperMid = curve(bandAvg(1500, 4000), 95)
    const treble   = curve(bandAvg(4000, 10000), 85)

    const overall  = (bass * 1.2 + low * 1.1 + mid + upperMid * 0.9 + treble * 0.7) / 4.9

    const root = document.documentElement.style
    root.setProperty('--audio-level',     overall.toFixed(3))
    root.setProperty('--audio-bass',      bass.toFixed(3))
    root.setProperty('--audio-low',       low.toFixed(3))
    root.setProperty('--audio-mid',       mid.toFixed(3))
    root.setProperty('--audio-upper-mid', upperMid.toFixed(3))
    root.setProperty('--audio-treble',    treble.toFixed(3))

    raf = requestAnimationFrame(tick)
  }

  const onEnd = () => {
    if (raf) cancelAnimationFrame(raf)
    // Fade de TODAS las bandas a 0 en 350ms para una vuelta suave al reposo.
    const start = performance.now()
    const vars = ['--audio-level', '--audio-bass', '--audio-low', '--audio-mid', '--audio-upper-mid', '--audio-treble']
    const rootStyle = getComputedStyle(document.documentElement)
    const initial = vars.map(v => parseFloat(rootStyle.getPropertyValue(v) || '0') || 0)
    const fade = (now) => {
      const t = Math.min(1, (now - start) / 350)
      vars.forEach((v, i) => {
        document.documentElement.style.setProperty(v, (initial[i] * (1 - t)).toFixed(3))
      })
      if (t < 1) requestAnimationFrame(fade)
      else vars.forEach(v => document.documentElement.style.setProperty(v, '0'))
    }
    requestAnimationFrame(fade)
    // Notificar al bridge para liberar el mic
    try { fetch(`${bridgeUrl}/api/voice/tts_ended`, { method: 'POST' }) } catch {}
    // Limpiar recursos
    try { source.disconnect(); analyser.disconnect() } catch {}
    try { URL.revokeObjectURL(url) } catch {}
    if (_currentUrl === url) _currentUrl = null
  }

  audio.addEventListener('ended', onEnd)
  audio.addEventListener('error', onEnd)

  try {
    await audio.play()
    tick()
  } catch (e) {
    console.error('play() fallo', e)
    onEnd()
  }
}
