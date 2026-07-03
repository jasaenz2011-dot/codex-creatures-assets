const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path  = require('path');
const fs    = require('fs');
const { v4: uuidv4 } = require('uuid');
const comfy = require('./comfyui');

const IS_DEV  = process.argv.includes('--dev');
const OUT_DIR = path.join(app.getPath('pictures'), 'AI-Studio');

let win;

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------
function createWindow() {
  win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'AI Studio',
    backgroundColor: '#0f0f0f',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, '../src/index.html'));
  if (IS_DEV) win.webContents.openDevTools();
}

app.whenReady().then(() => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('window-all-closed', () => {
  comfy.stop();
  if (process.platform !== 'darwin') app.quit();
});

// ---------------------------------------------------------------------------
// ComfyUI IPC
// ---------------------------------------------------------------------------
ipcMain.handle('comfy:status', async () => {
  const running = await comfy.isRunning();
  return { running, url: comfy.COMFY_URL };
});

ipcMain.handle('comfy:launch', async () => {
  const installPath = comfy.findComfyUI();
  if (!installPath) {
    return { status: 'not_found', message: 'ComfyUI not found. Please install it and restart.' };
  }
  return comfy.launch(installPath);
});

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------
function loadPresets(type) {
  const file = path.join(__dirname, `../config/${type}-presets.json`);
  return JSON.parse(fs.readFileSync(file, 'utf-8'));
}

ipcMain.handle('config:presets', (_e, type) => loadPresets(type));

// ---------------------------------------------------------------------------
// Generation
// ---------------------------------------------------------------------------
const jobQueue = new Map();

ipcMain.handle('generate', async (_e, job) => {
  const jobId = uuidv4();
  job.id = jobId;
  jobQueue.set(jobId, { ...job, status: 'queued' });

  win.webContents.send('job:queued', { id: jobId });

  try {
    const result = await runJob(job);
    jobQueue.set(jobId, { ...job, status: 'done', result });
    win.webContents.send('job:done', { id: jobId, result });
    return { id: jobId, result };
  } catch (err) {
    jobQueue.set(jobId, { ...job, status: 'error', error: err.message });
    win.webContents.send('job:error', { id: jobId, error: err.message });
    return { id: jobId, error: err.message };
  }
});

ipcMain.handle('job:cancel', (_e, id) => {
  jobQueue.delete(id);
  return { cancelled: id };
});

async function runJob(job) {
  const presets = loadPresets(job.type); // 'image' or 'video'
  const preset  = presets.find(p => p.id === job.presetId);
  if (!preset) throw new Error(`Unknown preset: ${job.presetId}`);

  const workflowPath = path.join(__dirname, '../workflows', job.type, preset.workflow);
  let workflow = JSON.parse(fs.readFileSync(workflowPath, 'utf-8'));

  workflow = injectParams(workflow, job, preset);

  // Queue workflow in ComfyUI
  const queueRes = await fetch(`${comfy.COMFY_URL}/prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: workflow, client_id: job.id }),
  });
  if (!queueRes.ok) throw new Error(`ComfyUI queue error: ${queueRes.statusText}`);
  const { prompt_id } = await queueRes.json();

  // Poll for completion
  const outputs = await pollComfyJob(prompt_id, job.id);
  const saved   = await saveOutputs(outputs, job, preset);
  return saved;
}

function injectParams(workflow, job, preset) {
  const w = JSON.stringify(workflow);
  const replaced = w
    .replace(/__PROMPT__/g,           (job.prompt    || '').replace(/"/g, '\\"'))
    .replace(/__NEGATIVE__/g,         (job.negative   || preset.defaults?.negative || '').replace(/"/g, '\\"'))
    .replace(/__STEPS__/g,            job.steps       || preset.defaults?.steps    || 20)
    .replace(/__CFG__/g,              job.cfg         || preset.defaults?.cfg      || 7)
    .replace(/__WIDTH__/g,            job.width       || preset.defaults?.width    || 512)
    .replace(/__HEIGHT__/g,           job.height      || preset.defaults?.height   || 512)
    .replace(/__SEED__/g,             job.seed        ?? Math.floor(Math.random() * 2**32))
    .replace(/__MODEL_FILE__/g,       preset.modelFile)
    .replace(/__REFERENCE_IMAGE__/g,  job.referenceImage || '');
  return JSON.parse(replaced);
}

async function pollComfyJob(promptId, clientId, timeoutMs = 300000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res  = await fetch(`${comfy.COMFY_URL}/history/${promptId}`);
    const data = await res.json();
    if (data[promptId]?.outputs) {
      return data[promptId].outputs;
    }
    win.webContents.send('job:progress', { id: clientId, promptId });
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error('Generation timed out after 5 minutes');
}

async function saveOutputs(outputs, job, preset) {
  const dateDir  = new Date().toISOString().slice(0, 10);
  const saveDir  = path.join(OUT_DIR, dateDir, preset.id);
  fs.mkdirSync(saveDir, { recursive: true });

  const saved = [];
  for (const nodeId of Object.keys(outputs)) {
    const node = outputs[nodeId];
    for (const img of (node.images || [])) {
      const src = `${comfy.COMFY_URL}/view?filename=${img.filename}&subfolder=${img.subfolder}&type=${img.type}`;
      const res  = await fetch(src);
      const buf  = Buffer.from(await res.arrayBuffer());
      const ext  = img.filename.split('.').pop();
      const dest = path.join(saveDir, `${Date.now()}.${ext}`);
      fs.writeFileSync(dest, buf);
      saved.push({ path: dest, filename: path.basename(dest), prompt: job.prompt, preset: preset.displayName });
    }
    for (const vid of (node.videos || [])) {
      const src = `${comfy.COMFY_URL}/view?filename=${vid.filename}&subfolder=${vid.subfolder}&type=${vid.type}`;
      const res  = await fetch(src);
      const buf  = Buffer.from(await res.arrayBuffer());
      const ext  = vid.filename.split('.').pop();
      const dest = path.join(saveDir, `${Date.now()}.${ext}`);
      fs.writeFileSync(dest, buf);
      saved.push({ path: dest, filename: path.basename(dest), prompt: job.prompt, preset: preset.displayName });
    }
  }
  return saved;
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------
ipcMain.handle('history:get', () => {
  return Array.from(jobQueue.values());
});

// ---------------------------------------------------------------------------
// File helpers
// ---------------------------------------------------------------------------
ipcMain.handle('file:upload-image', async () => {
  const result = await dialog.showOpenDialog(win, {
    title: 'Select reference image',
    filters: [{ name: 'Images', extensions: ['png','jpg','jpeg','webp','bmp'] }],
    properties: ['openFile'],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('file:open', (_e, filePath) => {
  shell.showItemInFolder(filePath);
});

ipcMain.handle('file:output-dir', () => OUT_DIR);
