const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('jarvis', {
  // ---- Controles de ventana ----
  windowMinimize:       () => ipcRenderer.send('window:minimize'),
  windowToggleMaximize: () => ipcRenderer.invoke('window:toggleMaximize'),
  windowClose:          () => ipcRenderer.send('window:close'),
  windowIsMaximized:    () => ipcRenderer.invoke('window:isMaximized'),
  onMaximizeChange: (cb) => {
    const h = (_e, isMax) => cb(isMax)
    ipcRenderer.on('window:isMaximized', h)
    return () => ipcRenderer.removeListener('window:isMaximized', h)
  },

  // ---- Bridge Python ----
  getBridgeUrl:   () => ipcRenderer.invoke('bridge:url'),
  getBridgeWsUrl: () => ipcRenderer.invoke('bridge:wsUrl'),

  // ---- Setup wizard ----
  getSystemInfo:    () => ipcRenderer.invoke('system:info'),
  setAutoStart:     (enabled) => ipcRenderer.invoke('setup:setAutoStart', enabled),
  isAutoStart:      () => ipcRenderer.invoke('setup:isAutoStart'),
  checkOllama:      () => ipcRenderer.invoke('setup:checkOllama'),
  installOllama:    () => ipcRenderer.invoke('setup:installOllama'),
  ollamaModels:     () => ipcRenderer.invoke('setup:ollamaModels'),
  ollamaPull:       (model) => ipcRenderer.invoke('setup:ollamaPull', model),
  startOllama:      () => ipcRenderer.invoke('setup:startOllama'),
  writeEnv:         (config) => ipcRenderer.invoke('setup:writeEnv', config),
  envExists:        () => ipcRenderer.invoke('setup:envExists'),
  readTelegram:     () => ipcRenderer.invoke('setup:readTelegram'),
  updateTelegram:   (data) => ipcRenderer.invoke('setup:updateTelegram', data),
  restartBridge:    () => ipcRenderer.invoke('bridge:restart'),
  verifyTelegram:   (token) => ipcRenderer.invoke('setup:verifyTelegram', token),
  checkFFmpeg:      () => ipcRenderer.invoke('setup:checkFFmpeg'),
  installFFmpeg:    () => ipcRenderer.invoke('setup:installFFmpeg'),
})
