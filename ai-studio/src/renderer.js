/* AI Studio — renderer process */

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  type:          'image',   // 'image' | 'video'
  presets:       { image: [], video: [] },
  activePreset:  null,
  activeMode:    null,
  referenceImage: null,
  referenceVideo: null,
  outputs:       [],
  jobs:          {},
};

// ── DOM refs ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const elModelList    = $('model-list');
const elModeBar      = $('mode-bar');
const elGallery      = $('gallery');
const elGalleryEmpty = $('gallery-empty');
const elPrompt       = $('prompt-input');
const elGenBtn       = $('generate-btn');
const elStatusDot    = $('status-dot');
const elStatusText   = $('status-text');
const elLaunchBtn    = $('launch-btn');
const elAdvPanel     = $('advanced-panel');
const elRefPreview   = $('ref-preview');
const elDropOverlay  = $('drop-overlay');
const elQueueOverlay = $('queue-overlay');

// ── Boot ───────────────────────────────────────────────────────────────────
async function boot() {
  await loadAllPresets();
  setType('image');
  checkComfy();
  bindEvents();
}

async function loadAllPresets() {
  state.presets.image = await window.studio.getPresets('image');
  state.presets.video = await window.studio.getPresets('video');
}

// ── Type switch (Image / Video) ────────────────────────────────────────────
function setType(type) {
  state.type = type;

  document.querySelectorAll('.type-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.type === type));

  const presets = state.presets[type];
  renderModelList(presets);

  const first = presets[0] || null;
  selectPreset(first);
}

// ── Model list ─────────────────────────────────────────────────────────────
function renderModelList(presets) {
  elModelList.innerHTML = '';
  presets.forEach(p => {
    const el = document.createElement('div');
    el.className = 'model-item';
    el.dataset.id = p.id;
    el.innerHTML = `
      <div class="model-name">${p.displayName}</div>
      <div class="model-tags">${p.tags.map(t => `<span class="tag">${t}</span>`).join('')}</div>
    `;
    el.addEventListener('click', () => selectPreset(p));
    elModelList.appendChild(el);
  });
}

function selectPreset(preset) {
  state.activePreset = preset;

  document.querySelectorAll('.model-item').forEach(el =>
    el.classList.toggle('active', el.dataset.id === preset?.id));

  if (preset) {
    renderModes(preset.supportedModes);
    applyDefaults(preset.defaults);
  }
}

// ── Mode bar ───────────────────────────────────────────────────────────────
const MODE_LABELS = {
  'text-to-image':  'Text → Image',
  'image-to-image': 'Image → Image',
  'inpaint':        'Inpaint',
  'outpaint':       'Outpaint',
  'reference-guided': 'Reference',
  'text-to-video':  'Text → Video',
  'image-to-video': 'Image → Video',
  'reference-guided': 'Reference',
  'video-to-video': 'Video → Video',
};

function renderModes(modes) {
  elModeBar.innerHTML = '';
  modes.forEach((m, i) => {
    const btn = document.createElement('button');
    btn.className = 'mode-btn' + (i === 0 ? ' active' : '');
    btn.textContent = MODE_LABELS[m] || m;
    btn.dataset.mode = m;
    btn.addEventListener('click', () => selectMode(m));
    elModeBar.appendChild(btn);
  });
  selectMode(modes[0]);
}

function selectMode(mode) {
  state.activeMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.mode === mode));
  updateRefVisibility();
}

function updateRefVisibility() {
  const needsImage = ['image-to-image','inpaint','outpaint','reference-guided','image-to-video'].includes(state.activeMode);
  const needsVideo = ['video-to-video'].includes(state.activeMode);
  $('ref-image-btn').style.display = needsImage ? '' : 'none';
  $('ref-video-btn').style.display = needsVideo ? '' : 'none';
}

// ── Advanced defaults ──────────────────────────────────────────────────────
function applyDefaults(d = {}) {
  if (d.steps)    $('adv-steps').value    = d.steps;
  if (d.cfg)      $('adv-cfg').value      = d.cfg;
  if (d.width)    $('adv-width').value    = d.width;
  if (d.height)   $('adv-height').value   = d.height;
  if (d.negative) $('adv-negative').value = d.negative;
}

// ── ComfyUI status ─────────────────────────────────────────────────────────
async function checkComfy() {
  elStatusDot.className = 'checking';
  elStatusText.textContent = 'Checking ComfyUI…';
  const { running } = await window.studio.comfyStatus();
  if (running) {
    elStatusDot.className = 'ok';
    elStatusText.textContent = 'ComfyUI running';
    elLaunchBtn.classList.remove('visible');
  } else {
    elStatusDot.className = '';
    elStatusText.textContent = 'ComfyUI not running';
    elLaunchBtn.classList.add('visible');
  }
}

async function launchComfy() {
  elStatusDot.className = 'checking';
  elStatusText.textContent = 'Starting ComfyUI…';
  elLaunchBtn.classList.remove('visible');
  const result = await window.studio.comfyLaunch();
  if (result.status === 'launched' || result.status === 'already_running') {
    elStatusDot.className = 'ok';
    elStatusText.textContent = 'ComfyUI running';
  } else {
    elStatusDot.className = '';
    elStatusText.textContent = result.message || 'ComfyUI not found';
    elLaunchBtn.classList.add('visible');
  }
}

// ── Reference files ────────────────────────────────────────────────────────
async function pickRefImage() {
  const filePath = await window.studio.uploadImage();
  if (!filePath) return;
  state.referenceImage = filePath;
  $('ref-image-btn').classList.add('has-file');
  renderRefPreviews();
}

function renderRefPreviews() {
  elRefPreview.innerHTML = '';
  if (state.referenceImage) {
    const wrap = document.createElement('div');
    wrap.className = 'ref-thumb-wrap';
    wrap.innerHTML = `
      <img class="ref-thumb" src="file://${state.referenceImage}" />
      <button class="ref-remove" data-target="image">✕</button>
    `;
    wrap.querySelector('[data-target=image]').addEventListener('click', () => {
      state.referenceImage = null;
      $('ref-image-btn').classList.remove('has-file');
      renderRefPreviews();
    });
    elRefPreview.appendChild(wrap);
  }
}

// Drop zone
function initDropZone() {
  document.addEventListener('dragover', e => {
    e.preventDefault();
    elDropOverlay.classList.add('active');
  });
  document.addEventListener('dragleave', e => {
    if (!e.relatedTarget) elDropOverlay.classList.remove('active');
  });
  document.addEventListener('drop', e => {
    e.preventDefault();
    elDropOverlay.classList.remove('active');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (file.type.startsWith('image/')) {
      state.referenceImage = file.path;
      $('ref-image-btn').classList.add('has-file');
      renderRefPreviews();
    } else if (file.type.startsWith('video/')) {
      state.referenceVideo = file.path;
      $('ref-video-btn').classList.add('has-file');
    }
  });
}

// ── Generate ───────────────────────────────────────────────────────────────
async function generate() {
  const prompt = elPrompt.value.trim();
  if (!prompt) { elPrompt.focus(); return; }
  if (!state.activePreset) return;

  const job = {
    type:           state.type,
    presetId:       state.activePreset.id,
    mode:           state.activeMode,
    prompt,
    negative:       $('adv-negative').value,
    steps:          parseInt($('adv-steps').value),
    cfg:            parseFloat($('adv-cfg').value),
    width:          parseInt($('adv-width').value),
    height:         parseInt($('adv-height').value),
    seed:           parseInt($('adv-seed').value),
    referenceImage: state.referenceImage || '',
    referenceVideo: state.referenceVideo || '',
  };

  elGenBtn.disabled = true;
  elGenBtn.textContent = 'Queued…';

  const { id } = await window.studio.generate(job);
  addQueueToast(id, state.activePreset.displayName, prompt);
}

// ── Queue toasts ───────────────────────────────────────────────────────────
function addQueueToast(id, modelName, prompt) {
  const el = document.createElement('div');
  el.className = 'queue-item';
  el.id = `qi-${id}`;
  el.innerHTML = `
    <div class="qi-header">
      <div class="qi-dot"></div>
      <span class="qi-label">${modelName}</span>
    </div>
    <div class="qi-model">${truncate(prompt, 60)}</div>
  `;
  elQueueOverlay.appendChild(el);
}

function updateQueueToast(id, status) {
  const el = $(`qi-${id}`);
  if (!el) return;
  const dot = el.querySelector('.qi-dot');
  dot.className = `qi-dot ${status}`;
  setTimeout(() => el.remove(), 3000);
}

// ── Gallery ────────────────────────────────────────────────────────────────
function addOutputs(items) {
  if (!items?.length) return;
  state.outputs.unshift(...items);

  if (elGallery.classList.contains('empty')) {
    elGallery.classList.remove('empty');
    elGalleryEmpty.remove();
  }

  items.forEach(item => {
    const card = document.createElement('div');
    card.className = 'output-card';
    const isVideo = /\.(mp4|webm|mov)$/i.test(item.filename);
    card.innerHTML = `
      ${isVideo
        ? `<video src="file://${item.path}" autoplay loop muted playsinline></video>`
        : `<img src="file://${item.path}" loading="lazy" />`
      }
      <div class="output-info">
        <div class="output-prompt">${item.prompt}</div>
        <div class="output-meta">${item.preset}</div>
      </div>
    `;
    card.addEventListener('click', () => window.studio.openOutput(item.path));
    elGallery.prepend(card);
  });
}

// ── Events ─────────────────────────────────────────────────────────────────
function bindEvents() {
  // Type tabs
  document.querySelectorAll('.type-tab').forEach(t =>
    t.addEventListener('click', () => setType(t.dataset.type)));

  // Prompt send on Ctrl/Cmd+Enter
  elPrompt.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') generate();
  });
  elPrompt.addEventListener('input', () => {
    elPrompt.style.height = 'auto';
    elPrompt.style.height = Math.min(elPrompt.scrollHeight, 160) + 'px';
  });

  elGenBtn.addEventListener('click', generate);
  elLaunchBtn.addEventListener('click', launchComfy);

  $('advanced-toggle').addEventListener('click', () => {
    const open = elAdvPanel.classList.toggle('open');
    $('advanced-toggle').textContent = `⚙️ Advanced ${open ? '▴' : '▾'}`;
  });

  $('ref-image-btn').addEventListener('click', pickRefImage);
  $('ref-video-btn').addEventListener('click', async () => {
    const fp = await window.studio.uploadImage(); // reuse file dialog
    if (fp) { state.referenceVideo = fp; $('ref-video-btn').classList.add('has-file'); }
  });

  // Events from main process
  window.studio.on('job:queued', ({ id }) => {
    elGenBtn.textContent = 'Generating…';
  });

  window.studio.on('job:progress', ({ id }) => {
    // toast already shows spinner
  });

  window.studio.on('job:done', ({ id, result }) => {
    updateQueueToast(id, 'done');
    addOutputs(result);
    elGenBtn.disabled = false;
    elGenBtn.textContent = 'Generate';
  });

  window.studio.on('job:error', ({ id, error }) => {
    updateQueueToast(id, 'error');
    alert(`Generation failed: ${error}`);
    elGenBtn.disabled = false;
    elGenBtn.textContent = 'Generate';
  });

  initDropZone();
  setInterval(checkComfy, 30000);
}

// ── Helpers ────────────────────────────────────────────────────────────────
function truncate(str, n) {
  return str.length > n ? str.slice(0, n) + '…' : str;
}

// ── Start ──────────────────────────────────────────────────────────────────
boot();
