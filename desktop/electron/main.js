/**
 * Electron main process.
 *
 * Responsabilidades:
 *  1. Crear la ventana frameless de 1280x800.
 *  2. Spawn del bridge Python (jarvis-bridge.exe en prod, "python -m bridge.server" en dev).
 *  3. Exponer IPC para que el renderer controle la ventana (min/max/close).
 *  4. Limpieza: matar el bridge al cerrar.
 */

import { app, BrowserWindow, ipcMain, shell, Tray, Menu, nativeImage } from 'electron'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { existsSync } from 'node:fs'
import net from 'node:net'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const isDev = process.env.NODE_ENV === 'development'
const BRIDGE_PORT = 17891
const BRIDGE_HOST = '127.0.0.1'

let mainWindow = null
let bridgeProcess = null
let tray = null
let isQuitting = false  // diferencia entre "cerrar ventana" y "salir de la app"

// ---------------------------------------------------------------------------
// Bridge Python: spawn + health check
// ---------------------------------------------------------------------------

/** Chequea si el puerto ya esta en uso (otro bridge ya corriendo). */
function portInUse(port, host = BRIDGE_HOST) {
  return new Promise((resolve) => {
    const sock = net.connect({ port, host })
    sock.once('connect', () => { sock.destroy(); resolve(true) })
    sock.once('error', () => { resolve(false) })
    setTimeout(() => { sock.destroy(); resolve(false) }, 600)
  })
}

/** Espera a que el bridge responda /api/health. */
async function waitForBridge(timeoutMs = 20000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`http://${BRIDGE_HOST}:${BRIDGE_PORT}/api/health`)
      if (res.ok) return true
    } catch {}
    await new Promise((r) => setTimeout(r, 400))
  }
  return false
}

async function startBridge() {
  // Si ya hay algo escuchando (ej. el CLI ya lo lanzo en otra sesion), no
  // spawn-eamos otro. Reusamos.
  if (await portInUse(BRIDGE_PORT)) {
    console.log(`[bridge] ya corriendo en :${BRIDGE_PORT}, reusando`)
    return
  }

  // En dev: desde d:\...\jarvis\desktop\, subimos a la raiz y corremos python -m bridge.server
  // En prod: el installer deja jarvis-bridge.exe en resources/bridge/
  const projectRoot = isDev
    ? join(__dirname, '..', '..')             // .../jarvis
    : join(process.resourcesPath, 'bridge')    // .../resources/bridge

  const args = isDev ? ['-m', 'bridge.server', '--port', String(BRIDGE_PORT)] : ['--port', String(BRIDGE_PORT)]
  const cmd = isDev ? 'python' : join(projectRoot, 'jarvis-bridge.exe')
  const cwd = isDev ? projectRoot : projectRoot

  console.log(`[bridge] spawning: ${cmd} ${args.join(' ')}  (cwd=${cwd})`)

  bridgeProcess = spawn(cmd, args, {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })

  bridgeProcess.stdout.on('data', (d) => process.stdout.write(`[bridge] ${d}`))
  bridgeProcess.stderr.on('data', (d) => process.stderr.write(`[bridge] ${d}`))
  bridgeProcess.on('exit', (code) => {
    console.log(`[bridge] exited (code=${code})`)
    bridgeProcess = null
  })

  const ok = await waitForBridge()
  if (!ok) {
    console.error('[bridge] no respondio en el tiempo esperado')
  } else {
    console.log('[bridge] listo')
  }
}

function stopBridge() {
  if (bridgeProcess) {
    try { bridgeProcess.kill() } catch {}
    bridgeProcess = null
  }
}

// ---------------------------------------------------------------------------
// Ventana principal
// ---------------------------------------------------------------------------

function createWindow() {
  // Icono de la app — busca icon.ico en assets/
  const iconPath = join(__dirname, '..', 'assets', 'icon.ico')
  const hasIcon = existsSync(iconPath)

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: false,               // Title bar custom
    thickFrame: true,           // Windows: conserva el borde interno resizer invisible
    backgroundColor: '#08040a',
    show: false,
    ...(hasIcon ? { icon: iconPath } : {}),
    webPreferences: {
      preload: join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
  })

  mainWindow.once('ready-to-show', () => mainWindow.show())

  mainWindow.on('maximize',   () => mainWindow.webContents.send('window:isMaximized', true))
  mainWindow.on('unmaximize', () => mainWindow.webContents.send('window:isMaximized', false))

  // Al cerrar la ventana: OCULTAR al tray en vez de quitar, para que Jarvis
  // siga escuchando por voz y respondiendo en segundo plano.
  // Solo se cierra de verdad con "Cerrar Jarvis" del menu del tray.
  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault()
      mainWindow.hide()
    }
  })

  // Links externos -> navegador del sistema, no en la ventana
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    // DevTools NO se abre solo — abrir manualmente con Ctrl+Shift+I si hace falta
  } else {
    mainWindow.loadFile(join(__dirname, '..', 'dist', 'index.html'))
  }
}

// ---------------------------------------------------------------------------
// IPC: controles de ventana
// ---------------------------------------------------------------------------

ipcMain.on('window:minimize', () => mainWindow?.minimize())
ipcMain.handle('window:toggleMaximize', () => {
  if (!mainWindow) return false
  const wasMax = mainWindow.isMaximized()
  if (wasMax) mainWindow.unmaximize()
  else        mainWindow.maximize()
  console.log(`[window] toggleMaximize: ${wasMax ? 'max->normal' : 'normal->max'}`)
  return !wasMax
})
ipcMain.handle('window:isMaximized', () => !!mainWindow?.isMaximized())
ipcMain.on('window:close', () => mainWindow?.close())

ipcMain.handle('bridge:url', () => `http://${BRIDGE_HOST}:${BRIDGE_PORT}`)
ipcMain.handle('bridge:wsUrl', () => `ws://${BRIDGE_HOST}:${BRIDGE_PORT}/ws/events`)

// ---- Setup wizard IPC ----
ipcMain.handle('system:info', async () => {
  const os = await import('node:os')
  const totalRAM = Math.round(os.default.totalmem() / (1024 ** 3))
  const cpus = os.default.cpus()
  const cpuModel = cpus[0]?.model || 'Desconocido'
  const cpuCores = cpus.length
  // Detectar GPU via wmic
  let gpu = 'Desconocido'
  try {
    const { execSync } = await import('node:child_process')
    const out = execSync('wmic path win32_VideoController get Name /value', { encoding: 'utf8', timeout: 5000 })
    const match = out.match(/Name=(.+)/i)
    if (match) gpu = match[1].trim()
  } catch {}
  return { totalRAM, cpuModel, cpuCores, gpu }
})

ipcMain.handle('setup:setAutoStart', (_e, enabled) => {
  app.setLoginItemSettings({
    openAtLogin: enabled,
    path: process.execPath,
  })
  return true
})

ipcMain.handle('setup:isAutoStart', () => {
  return app.getLoginItemSettings().openAtLogin
})

// ---- Setup: Ollama ----
ipcMain.handle('setup:checkOllama', async () => {
  const { execSync } = await import('node:child_process')
  try {
    execSync('ollama --version', { timeout: 5000, stdio: 'pipe' })
    return true
  } catch { return false }
})

ipcMain.handle('setup:installOllama', async () => {
  const { exec } = await import('node:child_process')
  return new Promise((resolve) => {
    // Intentar con winget primero
    exec('winget install Ollama.Ollama --accept-source-agreements --accept-package-agreements --silent --disable-interactivity',
      { timeout: 300000 },
      (err) => {
        if (!err) return resolve({ ok: true })
        // Fallback: descarga directa
        const url = 'https://ollama.com/download/OllamaSetup.exe'
        const tmp = join(app.getPath('temp'), 'OllamaSetup.exe')
        exec(`powershell -Command "Invoke-WebRequest -Uri '${url}' -OutFile '${tmp}'; Start-Process '${tmp}' -ArgumentList '/VERYSILENT','/NORESTART' -Wait"`,
          { timeout: 600000 },
          (err2) => resolve({ ok: !err2, fallback: true })
        )
      }
    )
  })
})

ipcMain.handle('setup:ollamaModels', async () => {
  const { execSync } = await import('node:child_process')
  try {
    const out = execSync('ollama list', { timeout: 10000, encoding: 'utf8' })
    return out
  } catch { return '' }
})

ipcMain.handle('setup:ollamaPull', async (_e, model) => {
  const { exec } = await import('node:child_process')
  return new Promise((resolve) => {
    const proc = exec(`ollama pull ${model}`, { timeout: 3600000 })
    let output = ''
    proc.stdout?.on('data', d => { output += d })
    proc.stderr?.on('data', d => { output += d })
    proc.on('close', code => resolve({ ok: code === 0, output }))
  })
})

ipcMain.handle('setup:startOllama', async () => {
  const { exec } = await import('node:child_process')
  const localApp = join(process.env.LOCALAPPDATA || '', 'Programs', 'Ollama', 'ollama app.exe')
  try {
    if (existsSync(localApp)) {
      exec(`"${localApp}"`)
    } else {
      exec('ollama serve')
    }
    // Esperar a que arranque
    const { default: http } = await import('node:http')
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 1000))
      try {
        await new Promise((resolve, reject) => {
          http.get('http://localhost:11434/api/tags', r => { r.resume(); resolve() }).on('error', reject)
        })
        return true
      } catch {}
    }
  } catch {}
  return false
})

// ---- Setup: .env ----
// En prod el .env se escribe a %APPDATA%\Jarvis\.env (escribible sin admin,
// aunque se instale en Program Files). config.py lo busca ahi primero.
function userEnvPath() {
  const base = process.env.APPDATA || app.getPath('appData')
  return join(base, 'Jarvis', '.env')
}

ipcMain.handle('setup:envExists', async () => {
  const { existsSync } = await import('node:fs')
  const p = isDev
    ? join(__dirname, '..', '..', '.env')
    : userEnvPath()
  return existsSync(p)
})

// Lee los campos actuales de Telegram del .env del usuario
ipcMain.handle('setup:readTelegram', async () => {
  const { existsSync, readFileSync } = await import('node:fs')
  const p = isDev ? join(__dirname, '..', '..', '.env') : userEnvPath()
  if (!existsSync(p)) return { token: '', user_id: '', enable_voice: true }
  const text = readFileSync(p, 'utf8')
  const get = (k) => {
    const m = text.match(new RegExp('^' + k + '=(.*)$', 'm'))
    return m ? m[1].trim() : ''
  }
  return {
    token: get('TELEGRAM_BOT_TOKEN'),
    user_id: get('TELEGRAM_ALLOWED_USERS'),
    enable_voice: (get('TELEGRAM_ENABLE_VOICE') || 'true').toLowerCase() !== 'false',
  }
})

// Actualiza SOLO los 3 campos de Telegram en el .env existente,
// preservando el resto (provider, modelos, keys, etc.).
ipcMain.handle('setup:updateTelegram', async (_e, { token, user_id, enable_voice }) => {
  const { existsSync, readFileSync, writeFileSync, mkdirSync } = await import('node:fs')
  const p = isDev ? join(__dirname, '..', '..', '.env') : userEnvPath()
  let text = existsSync(p) ? readFileSync(p, 'utf8') : ''
  const setKey = (k, v) => {
    const line = `${k}=${v}`
    if (text.match(new RegExp('^' + k + '=.*$', 'm'))) {
      text = text.replace(new RegExp('^' + k + '=.*$', 'm'), line)
    } else {
      text = (text.endsWith('\n') || text === '' ? text : text + '\n') + line + '\n'
    }
  }
  setKey('TELEGRAM_BOT_TOKEN', token || '')
  setKey('TELEGRAM_ALLOWED_USERS', user_id || '')
  setKey('TELEGRAM_ENABLE_VOICE', enable_voice ? 'true' : 'false')
  mkdirSync(dirname(p), { recursive: true })
  writeFileSync(p, text, 'utf8')
  return true
})

// Reinicia el bridge Python para que tome la nueva config (no toca Electron).
ipcMain.handle('bridge:restart', async () => {
  try { stopBridge() } catch {}
  await new Promise(r => setTimeout(r, 800))
  await startBridge()
  return true
})

ipcMain.handle('setup:writeEnv', async (_e, config) => {
  const envPath = isDev
    ? join(__dirname, '..', '..', '.env')
    : userEnvPath()

  const lines = [
    '# JARVIS - Configuracion generada por Setup Wizard',
    '',
    `AI_PROVIDER=${config.provider || 'ollama'}`,
    'ASSISTANT_NAME=Jarvis',
    'VOICE_LANGUAGE=es',
    'VOICE_SPEED=180',
    '',
    `OPENAI_API_KEY=${config.openai_key || ''}`,
    `ANTHROPIC_API_KEY=${config.anthropic_key || ''}`,
    `GEMINI_API_KEY=${config.gemini_key || ''}`,
    '',
    'CLAUDE_MODEL=claude-sonnet-4-20250514',
    'OPENAI_MODEL=gpt-4o',
    'GEMINI_MODEL=gemini-2.0-flash',
    '',
    `OLLAMA_MODEL=${config.ollama_model || 'llama3.2'}`,
    'OLLAMA_ROUTER_MODEL=llama3.2',
    'OLLAMA_FALLBACK_MODEL=llama3.2',
    `OLLAMA_VISION_MODEL=${config.vision_model || ''}`,
    '',
    `TELEGRAM_BOT_TOKEN=${config.telegram_token || ''}`,
    `TELEGRAM_ALLOWED_USERS=${config.telegram_user_id || ''}`,
    'TELEGRAM_ENABLE_VOICE=true',
  ]

  const { writeFileSync, mkdirSync } = await import('node:fs')
  mkdirSync(dirname(envPath), { recursive: true })
  writeFileSync(envPath, lines.join('\n') + '\n', 'utf8')
  return true
})

// ---- Setup: verificar token Telegram ----
ipcMain.handle('setup:verifyTelegram', async (_e, token) => {
  const { default: https } = await import('node:https')
  return new Promise((resolve) => {
    https.get(`https://api.telegram.org/bot${token}/getMe`, (res) => {
      let data = ''
      res.on('data', c => { data += c })
      res.on('end', () => {
        try {
          const j = JSON.parse(data)
          resolve(j.ok ? { ok: true, username: j.result.username } : { ok: false })
        } catch { resolve({ ok: false }) }
      })
    }).on('error', () => resolve({ ok: false }))
  })
})

// ---- Setup: instalar FFmpeg ----
ipcMain.handle('setup:checkFFmpeg', async () => {
  const { execSync } = await import('node:child_process')
  try {
    execSync('ffmpeg -version', { timeout: 5000, stdio: 'pipe' })
    return true
  } catch { return false }
})

ipcMain.handle('setup:installFFmpeg', async () => {
  const { exec } = await import('node:child_process')
  return new Promise((resolve) => {
    exec('winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements --silent --disable-interactivity',
      { timeout: 300000 },
      (err) => resolve({ ok: !err })
    )
  })
})

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

function createTray() {
  const trayIconPath = join(__dirname, '..', 'assets', 'icon.ico')
  const icon = existsSync(trayIconPath)
    ? nativeImage.createFromPath(trayIconPath).resize({ width: 16, height: 16 })
    : nativeImage.createEmpty()
  tray = new Tray(icon)
  tray.setToolTip('Jarvis · Escuchando')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Mostrar Jarvis',
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Cerrar Jarvis',
      click: () => {
        isQuitting = true
        app.quit()
      }
    }
  ])
  tray.setContextMenu(contextMenu)

  // Click izquierdo en el tray icon: mostrar la ventana
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.focus()
      } else {
        mainWindow.show()
        mainWindow.focus()
      }
    }
  })
}

app.whenReady().then(async () => {
  // Arranque automatico al iniciar Windows — se re-asegura en cada lanzamiento
  // (el usuario puede desactivarlo borrando el shortcut en shell:startup, pero
  //  por defecto Jarvis siempre arranca con la PC).
  if (!isDev) {
    try {
      app.setLoginItemSettings({
        openAtLogin: true,
        path: process.execPath,
      })
    } catch {}
  }

  await startBridge()
  createTray()
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  // No cerrar la app cuando se cierra la ventana — Jarvis corre en el tray
})

app.on('before-quit', () => {
  isQuitting = true
  stopBridge()
})
