'use strict';

// A thin client over the same REST API an external orchestrator uses. The form is built
// from each pipeline's declared parameters, so adding a capability server-side needs no
// change here.

const $ = (id) => document.getElementById(id);

let PIPELINES = [];
let JOBS = [];
let openJobId = null;
const fileInputs = new Map();   // param name -> <input type=file>
const previewUrls = new Map();  // param name -> object URL currently painted
let lastZoneKey = null;         // dropzone the user last clicked, for paste targeting
let painter = null;             // mask painter state, see startPainter()

// ------------------------------------------------------------------- helpers

async function api(path, init) {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch { /* keep the status line */ }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

function duration(seconds) {
  if (seconds == null) return '—';
  const s = Math.round(seconds);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;
}

function ago(epoch) {
  const diff = Date.now() / 1000 - epoch;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(epoch * 1000).toLocaleDateString();
}

const currentPipeline = () => PIPELINES.find((p) => p.id === $('pipeline').value);

// --------------------------------------------------------------- form build

function fieldControl(param) {
  const id = `p_${param.name}`;
  if (param.type === 'enum') {
    const options = (param.choices || [])
      .map((c) => `<option value="${escapeHtml(c)}"${c === param.default ? ' selected' : ''}>${escapeHtml(c)}</option>`)
      .join('');
    return `<select id="${id}">${options}</select>`;
  }
  if (param.type === 'bool') {
    return `<input id="${id}" type="checkbox"${param.default ? ' checked' : ''}>`;
  }
  if (param.type === 'int' || param.type === 'float') {
    const step = param.type === 'int' ? '1' : 'any';
    const min = param.min != null ? ` min="${param.min}"` : '';
    const max = param.max != null ? ` max="${param.max}"` : '';
    const value = param.default != null ? ` value="${param.default}"` : '';
    return `<input id="${id}" type="number" step="${step}"${min}${max}${value}>`;
  }
  // Long free text gets a textarea; short strings a single line.
  const long = ['prompt', 'negative', 'text', 'script', 'voice_description',
                'reference_text'].includes(param.name);
  if (long) {
    const rows = param.name === 'negative' ? 2 : 4;
    return `<textarea id="${id}" rows="${rows}">${escapeHtml(param.default ?? '')}</textarea>`;
  }
  const placeholder = param.name === 'seed' ? 'blank = random' : '';
  return `<input id="${id}" type="text" value="${escapeHtml(param.default ?? '')}" placeholder="${placeholder}">`;
}

function renderFields() {
  const pipeline = currentPipeline();
  const host = $('fields');
  fileInputs.clear();
  if (!pipeline) { host.innerHTML = ''; return; }

  $('pipelineNote').textContent = pipeline.description || '';

  const parts = [];
  for (const key of pipeline.accepts_files || []) {
    // The mask is painted over the source image rather than uploaded: a mask made
    // elsewhere has to match the panel pixel for pixel, which is the whole friction.
    if (key === 'mask') {
      parts.push(`
        <div class="field">
          <span>mask <em class="hint">(paint over the image)</em></span>
          <div class="painter" id="painter">
            <p class="dz-empty painter-idle">Load an image above, then brush over the region to change.</p>
          </div>
          <div class="painter-tools" id="painterTools" hidden>
            <label class="brush">brush
              <input type="range" id="brushSize" min="8" max="220" value="70">
            </label>
            <button type="button" id="maskClear">clear</button>
            <small class="hint" id="maskState">nothing painted</small>
          </div>
          <input type="file" id="f_mask" accept="image/*" hidden>
        </div>`);
      continue;
    }
    const accept = key.includes('audio') ? 'audio/*' : 'image/*';
    const verb = key.includes('audio') ? 'Click or drop an audio file' : 'Click, drop, or paste an image';
    parts.push(`
      <label class="field">
        <span>${key} <em class="hint">(file)</em></span>
        <div class="dropzone" id="dz_${key}" data-key="${key}">
          <div class="dz-empty">
            <p class="dz-icon">${key.includes('audio') ? '\u{1F3B5}' : '\u{1F5BC}'}</p>
            <p>${verb}</p>
          </div>
        </div>
        <input type="file" id="f_${key}" accept="${accept}" hidden>
      </label>`);
  }
  for (const param of pipeline.params) {
    const req = param.required ? ' <em class="req">required</em>' : '';
    parts.push(`
      <label class="field">
        <span>${param.name}${req}</span>
        ${fieldControl(param)}
        ${param.help ? `<small class="hint">${escapeHtml(param.help)}</small>` : ''}
      </label>`);
  }
  host.innerHTML = parts.join('');

  for (const key of pipeline.accepts_files || []) {
    fileInputs.set(key, $(`f_${key}`));
    if (key !== 'mask') wireDropzone(key);
  }
  painter = null;
  if ((pipeline.accepts_files || []).includes('mask')) wirePainter();
}

// ----------------------------------------------------------------- dropzones

// A file input's .files is read-only, but it is assignable from a DataTransfer
// list. That is what lets a dropped or pasted File reach collectForm() unchanged.
function setFile(key, file, repaint = true) {
  const input = fileInputs.get(key);
  if (!input) return;
  const transfer = new DataTransfer();
  if (file) transfer.items.add(file);
  input.files = transfer.files;
  if (repaint) paintZone(key, file);
  if (key === 'image' && painter !== null) loadPainterSource(file);
}

function paintZone(key, file) {
  const zone = $(`dz_${key}`);
  if (!zone) return;

  const stale = previewUrls.get(key);
  if (stale) { URL.revokeObjectURL(stale); previewUrls.delete(key); }

  if (!file) {
    const audio = key.includes('audio');
    zone.innerHTML = `
      <div class="dz-empty">
        <p class="dz-icon">${audio ? '\u{1F3B5}' : '\u{1F5BC}'}</p>
        <p>${audio ? 'Click or drop an audio file' : 'Click, drop, or paste an image'}</p>
      </div>`;
    return;
  }

  const label = `${escapeHtml(file.name || 'pasted')} \u00b7 ${Math.round(file.size / 1024)} KB`;
  if (file.type.startsWith('image/')) {
    const url = URL.createObjectURL(file);
    previewUrls.set(key, url);
    zone.innerHTML = `<img src="${url}" alt=""><button type="button" class="chip-clear" data-clear="${key}">\u2715 clear</button>`;
  } else {
    zone.innerHTML = `<div class="dz-empty"><p class="dz-icon">\u{1F3B5}</p><p>${label}</p></div>
      <button type="button" class="chip-clear" data-clear="${key}">\u2715 clear</button>`;
  }
}

function wireDropzone(key) {
  const zone = $(`dz_${key}`);
  const input = fileInputs.get(key);
  if (!zone || !input) return;

  input.addEventListener('change', () => {
    const file = input.files?.[0] || null;
    paintZone(key, file);
    if (key === 'image' && painter !== null) loadPainterSource(file);
  });

  // The zone lives inside a <label> wrapping the input, so a bare click already
  // opens the picker. Only the clear chip has to opt out of that.
  zone.addEventListener('click', (event) => {
    lastZoneKey = key;
    const clear = event.target.closest('[data-clear]');
    if (clear) {
      event.preventDefault();
      event.stopPropagation();
      setFile(key, null);
    }
  });

  for (const name of ['dragenter', 'dragover']) {
    zone.addEventListener(name, (event) => {
      event.preventDefault();
      zone.classList.add('over');
    });
  }
  for (const name of ['dragleave', 'dragend']) {
    zone.addEventListener(name, () => zone.classList.remove('over'));
  }
  zone.addEventListener('drop', (event) => {
    event.preventDefault();
    zone.classList.remove('over');
    const file = event.dataTransfer?.files?.[0];
    if (file) { lastZoneKey = key; setFile(key, file); }
  });
}

// -------------------------------------------------------------- mask painter

// Two canvases at the source image's natural size. `mask` is the black/white PNG the
// pipeline consumes — white repaints, black comes back bit-identical. `overlay` is the
// red wash the user actually sees. Both take the same strokes; only mask is uploaded.
function wirePainter() {
  painter = { mask: null, overlay: null, view: null, image: null, drawing: false, dirty: false };
  $('brushSize')?.addEventListener('input', () => { /* radius read live on stroke */ });
  $('maskClear')?.addEventListener('click', () => {
    if (!painter?.mask) return;
    painter.mask.getContext('2d').fillStyle = '#000';
    painter.mask.getContext('2d').fillRect(0, 0, painter.mask.width, painter.mask.height);
    painter.overlay.getContext('2d').clearRect(0, 0, painter.overlay.width, painter.overlay.height);
    painter.dirty = false;
    redrawPainter();
    setFile('mask', null, false);
    $('maskState').textContent = 'nothing painted';
  });
  const current = fileInputs.get('image')?.files?.[0];
  if (current) loadPainterSource(current);
}

function loadPainterSource(file) {
  const host = $('painter');
  if (!host || !painter) return;
  setFile('mask', null, false);
  if (!file) {
    painter.image = null;
    host.innerHTML = '<p class="dz-empty painter-idle">Load an image above, then brush over the region to change.</p>';
    $('painterTools').hidden = true;
    return;
  }

  const img = new Image();
  const url = URL.createObjectURL(file);
  img.onload = () => {
    painter.image = img;
    painter.mask = document.createElement('canvas');
    painter.overlay = document.createElement('canvas');
    for (const canvas of [painter.mask, painter.overlay]) {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
    }
    const maskCtx = painter.mask.getContext('2d');
    maskCtx.fillStyle = '#000';
    maskCtx.fillRect(0, 0, painter.mask.width, painter.mask.height);

    host.innerHTML = '';
    const view = document.createElement('canvas');
    view.className = 'painter-view';
    view.width = img.naturalWidth;
    view.height = img.naturalHeight;
    host.appendChild(view);
    painter.view = view;
    painter.dirty = false;
    redrawPainter();
    wireStrokes(view);
    $('painterTools').hidden = false;
    $('maskState').textContent = 'nothing painted';
    URL.revokeObjectURL(url);
  };
  img.onerror = () => URL.revokeObjectURL(url);
  img.src = url;
}

function redrawPainter() {
  const ctx = painter.view.getContext('2d');
  ctx.clearRect(0, 0, painter.view.width, painter.view.height);
  ctx.drawImage(painter.image, 0, 0);
  ctx.drawImage(painter.overlay, 0, 0);
}

function wireStrokes(view) {
  // The canvas is displayed scaled to the column width, so every pointer position has
  // to be mapped back to natural pixels or the mask lands offset from what was brushed.
  const toNatural = (event) => {
    const box = view.getBoundingClientRect();
    return {
      x: (event.clientX - box.left) * (view.width / box.width),
      y: (event.clientY - box.top) * (view.height / box.height),
    };
  };

  const dab = (point) => {
    const radius = Number($('brushSize').value) / 2;
    for (const [canvas, style] of [[painter.mask, '#fff'], [painter.overlay, 'rgba(255,64,64,.45)']]) {
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = style;
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
      ctx.fill();
    }
    painter.dirty = true;
  };

  view.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    try { view.setPointerCapture(event.pointerId); } catch { /* capture is a nicety */ }
    painter.drawing = true;
    dab(toNatural(event));
    redrawPainter();
  });
  view.addEventListener('pointermove', (event) => {
    if (!painter.drawing) return;
    dab(toNatural(event));
    redrawPainter();
  });
  for (const name of ['pointerup', 'pointercancel']) {
    view.addEventListener(name, () => {
      if (!painter.drawing) return;
      painter.drawing = false;
      exportMask();
    });
  }
}

function exportMask() {
  if (!painter?.mask || !painter.dirty) return;
  painter.mask.toBlob((blob) => {
    if (!blob) return;
    setFile('mask', new File([blob], 'mask.png', { type: 'image/png' }), false);
    $('maskState').textContent = `mask ready · ${painter.mask.width}×${painter.mask.height} · ${Math.round(blob.size / 1024)} KB`;
  }, 'image/png');
}

// Where a paste lands when a pipeline exposes several file slots. The zone you
// last clicked wins; otherwise the first slot still empty; otherwise the first.
function pasteTarget() {
  const keys = [...fileInputs.keys()].filter((k) => !k.includes('audio'));
  if (!keys.length) return null;
  if (lastZoneKey && keys.includes(lastZoneKey)) return lastZoneKey;
  return keys.find((k) => !fileInputs.get(k)?.files?.[0]) || keys[0];
}

function handlePaste(event) {
  const items = [...(event.clipboardData?.items || [])];
  const image = items.find((item) => item.type.startsWith('image/'));
  if (!image) return;                       // let text pastes reach the prompt box
  const file = image.getAsFile();
  if (!file) return;
  const key = pasteTarget();
  if (!key) return;
  event.preventDefault();
  setFile(key, file);
  $(`dz_${key}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function collectForm() {
  const pipeline = currentPipeline();
  const form = new FormData();
  form.set('pipeline', pipeline.id);

  for (const param of pipeline.params) {
    const element = $(`p_${param.name}`);
    if (!element) continue;
    const value = param.type === 'bool'
      ? (element.checked ? 'true' : 'false')
      : element.value;
    if (value !== '' && value != null) form.set(param.name, value);
  }
  for (const [key, input] of fileInputs) {
    if (input?.files?.[0]) form.set(key, input.files[0], input.files[0].name);
  }
  return form;
}

// ------------------------------------------------------------------ status

async function refreshStatus() {
  try {
    const status = await api('/api/status');
    const dot = $('statusDot');
    if (!status.comfy_up) {
      dot.className = 'dot down';
      $('statusText').textContent = 'ComfyUI offline — image/video jobs will fail';
      return;
    }
    dot.className = status.current ? 'dot busy' : 'dot up';
    const bits = [`ComfyUI ${status.comfy_version || 'up'}`];
    if (status.gpu && status.gpu.vram_free != null) {
      bits.push(`${(status.gpu.vram_free / 1024 ** 3).toFixed(1)} GiB free`);
    }
    if (status.queued) bits.push(`${status.queued} queued`);
    $('statusText').textContent = bits.join(' · ');
  } catch {
    $('statusDot').className = 'dot down';
    $('statusText').textContent = 'service unreachable';
  }
}

// ---------------------------------------------------------------- generate

async function generate() {
  const button = $('generate');
  const error = $('formError');
  error.hidden = true;
  button.disabled = true;
  button.textContent = 'Queueing…';
  try {
    await api('/api/generate', { method: 'POST', body: collectForm() });
    await refreshJobs();
  } catch (exc) {
    error.textContent = exc.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = 'Queue job';
  }
}

// -------------------------------------------------------------------- jobs

async function refreshJobs() {
  const kind = $('kindFilter').value;
  let payload;
  try {
    payload = await api(`/api/jobs?limit=300${kind ? `&kind=${kind}` : ''}`);
  } catch { return; }
  JOBS = payload.jobs;
  $('jobCount').textContent = payload.total ? `(${payload.total})` : '';
  renderActive();
  renderGrid();
  if (openJobId) renderModal();
}

function renderActive() {
  const live = JOBS.filter((j) => j.status === 'running' || j.status === 'queued');
  const host = $('active');
  if (!live.length) { host.innerHTML = ''; return; }

  host.innerHTML = live.map((job) => {
    const running = job.status === 'running';
    const percent = Math.round((job.progress || 0) * 100);
    const elapsed = running && job.started_at
      ? duration(Date.now() / 1000 - job.started_at) : '';
    return `
      <div class="active-card">
        <div class="active-head">
          <strong>${running ? 'Running' : 'Queued'} · ${escapeHtml(job.pipeline)}</strong>
          <button data-cancel="${job.id}">Cancel</button>
        </div>
        <div class="bar"><i style="width:${running ? percent : 0}%"></i></div>
        <div class="active-meta">
          <span>${escapeHtml(job.stage || job.status)}${running ? ` · ${percent}%` : ''}</span>
          <span>${elapsed}</span>
        </div>
      </div>`;
  }).join('');

  host.querySelectorAll('[data-cancel]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try { await api(`/api/jobs/${button.dataset.cancel}/cancel`, { method: 'POST' }); }
      catch { /* it likely finished already */ }
      refreshJobs();
    });
  });
}

const summarise = (job) => {
  const p = job.params || {};
  return p.prompt || p.text || p.script || '(no text)';
};

function renderGrid() {
  const grid = $('grid');
  $('empty').hidden = JOBS.length > 0;

  grid.innerHTML = JOBS.map((job) => {
    const thumb = job.thumb
      ? `style="background-image:url('/api/jobs/${job.id}/thumb')"` : '';
    const placeholder = job.thumb ? '' : ({
      running: 'running…', queued: 'queued', error: 'failed', cancelled: 'cancelled',
    }[job.status] || job.kind);
    return `
      <article class="card" data-open="${job.id}">
        <div class="thumb" ${thumb}>${placeholder}</div>
        <div class="body">
          <div class="line1">${escapeHtml(summarise(job).slice(0, 110))}</div>
          <div class="line2">
            <span class="badge ${job.status}">${job.status}</span>
            <span>${escapeHtml(job.kind)}</span>
            <span>${ago(job.created_at)}</span>
          </div>
        </div>
      </article>`;
  }).join('');

  grid.querySelectorAll('[data-open]').forEach((card) => {
    card.addEventListener('click', () => openModal(card.dataset.open));
  });
}

// ------------------------------------------------------------------ viewer

const jobById = (id) => JOBS.find((j) => j.id === id);

function openModal(id) {
  if (!jobById(id)) return;
  openJobId = id;
  $('modal').hidden = false;
  document.body.style.overflow = 'hidden';
  renderModal(true);
}

function closeModal() {
  openJobId = null;
  $('viewer').innerHTML = '';
  $('modal').hidden = true;
  document.body.style.overflow = '';
}

function viewerFor(job) {
  if (!job.outputs || !job.outputs.length) return '<p class="empty">No output yet.</p>';
  const url = `/api/jobs/${job.id}/output?index=0`;
  if (job.kind === 'video') {
    return `<video id="player" controls playsinline preload="metadata" src="${url}"></video>`;
  }
  if (job.kind === 'image') {
    return job.outputs.map((_, i) =>
      `<img class="viewer-image" src="/api/jobs/${job.id}/output?index=${i}" alt="">`).join('');
  }
  if (job.kind === 'audio') {
    return `<audio id="player" controls src="${url}" style="width:100%"></audio>`;
  }
  return '<pre class="subs" id="subsBox">loading…</pre>';
}

function renderModal(reload = false) {
  const job = jobById(openJobId);
  if (!job) { closeModal(); return; }

  if (reload) {
    $('viewer').innerHTML = viewerFor(job);
    if (job.kind === 'subtitle' && job.outputs && job.outputs.length) {
      fetch(`/api/jobs/${job.id}/output?index=0`).then((r) => r.text())
        .then((t) => { const box = $('subsBox'); if (box) box.textContent = t; });
    }
  }

  const has = Boolean(job.outputs && job.outputs.length);
  const download = $('btnDownload');
  download.href = `/api/jobs/${job.id}/output?index=0&download=true`;
  download.style.display = has ? '' : 'none';
  $('btnFullscreen').style.display = job.kind === 'video' && has ? '' : 'none';

  const rows = [
    ['pipeline', job.pipeline], ['kind', job.kind], ['status', job.status],
    ['outputs', (job.outputs || []).length], ['took', duration(job.duration)],
    ['created', new Date(job.created_at * 1000).toLocaleString()],
  ];
  if (job.error) rows.push(['error', job.error]);
  $('modalParams').innerHTML = rows.map(([k, v]) =>
    `<div><dt>${k}</dt><dd>${escapeHtml(v)}</dd></div>`).join('');
  $('modalPrompt').textContent = JSON.stringify(job.params, null, 2);
}

function wireModal() {
  document.querySelectorAll('[data-close]').forEach((el) =>
    el.addEventListener('click', closeModal));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('modal').hidden) closeModal();
  });

  $('btnFullscreen').addEventListener('click', () => {
    const player = $('player');
    if (player && player.requestFullscreen) player.requestFullscreen();
  });

  $('btnReuse').addEventListener('click', () => {
    const job = jobById(openJobId);
    if (!job) return;
    $('pipeline').value = job.pipeline;
    renderFields();
    for (const [key, value] of Object.entries(job.params || {})) {
      const element = $(`p_${key}`);
      if (!element) continue;
      if (element.type === 'checkbox') element.checked = Boolean(value);
      else if (value != null) element.value = value;
    }
    closeModal();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  $('btnDelete').addEventListener('click', async () => {
    const job = jobById(openJobId);
    if (!job) return;
    if (!confirm('Delete this job and its files? This cannot be undone.')) return;
    try {
      await api(`/api/jobs/${job.id}`, { method: 'DELETE' });
      closeModal();
      refreshJobs();
    } catch (exc) { alert(exc.message); }
  });
}

// -------------------------------------------------------------------- boot

(async function main() {
  wireModal();
  $('generate').addEventListener('click', generate);
  $('kindFilter').addEventListener('change', refreshJobs);
  $('pipeline').addEventListener('change', renderFields);
  document.addEventListener('paste', handlePaste);

  const payload = await api('/api/pipelines');
  PIPELINES = payload.pipelines;
  $('pipeline').innerHTML = PIPELINES
    .map((p) => `<option value="${p.id}">${p.kind} — ${escapeHtml(p.title)}</option>`)
    .join('');
  renderFields();

  await refreshStatus();
  await refreshJobs();
  setInterval(refreshStatus, 3000);
  setInterval(refreshJobs, 1500);
})();
