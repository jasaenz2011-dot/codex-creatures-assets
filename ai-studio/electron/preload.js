const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('studio', {
  // ComfyUI
  comfyStatus:    ()       => ipcRenderer.invoke('comfy:status'),
  comfyLaunch:    ()       => ipcRenderer.invoke('comfy:launch'),

  // Config
  getPresets:     (type)   => ipcRenderer.invoke('config:presets', type),

  // Generation
  generate:       (job)    => ipcRenderer.invoke('generate', job),
  getHistory:     ()       => ipcRenderer.invoke('history:get'),
  cancelJob:      (id)     => ipcRenderer.invoke('job:cancel', id),

  // File helpers
  uploadImage:    ()       => ipcRenderer.invoke('file:upload-image'),
  openOutput:     (p)      => ipcRenderer.invoke('file:open', p),
  getOutputDir:   ()       => ipcRenderer.invoke('file:output-dir'),

  // Events from main → renderer
  on: (channel, cb) => ipcRenderer.on(channel, (_e, ...args) => cb(...args)),
  off: (channel, cb) => ipcRenderer.removeListener(channel, cb),
});
