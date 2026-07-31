'use strict';

const $ = (id) => document.getElementById(id);

let OPTIONS = null;
let JOBS = [];
let openJobId = null;
let pickedFile = null;

// ------------------------------------------------------------------ helpers

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

const pad = (n) => String(n).padStart(2, '0');

function duration(seconds) {
  if (seconds == null) return '—';
  const s = Math.round(seconds);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${pad(s % 60)}s`;
}

function ago(epoch) {
  const diff = Date.now() / 1000 - epoch;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(epoch * 1000).toLocaleDateString();
}

function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// ------------------------------------------------------------------- setup

async function loadOptions() {
  OPTIONS = await api('/api/options');

  const preset = $('preset');
  preset.innerHTML = OPTIONS.presets
    .map((p) => `<option value="${p.id}">${p.width}×${p.height}</option>`).join('');
  preset.value = OPTIONS.defaults.preset;

  const frames = $('frames');
  frames.innerHTML = OPTIONS.frames.map((f) => `<option value="${f}">${f}</option>`).join('');
  frames.value = OPTIONS.defaults.frames;

  $('sampler').innerHTML = OPTIONS.samplers.map((s) => `<option>${s}</option>`).join('');
  $('scheduler').innerHTML = OPTIONS.schedulers.map((s) => `<option>${s}</option>`).join('');

  $('steps').value = OPTIONS.defaults.steps;
  $('cfg').value = OPTIONS.defaults.cfg;
  $('fps').value = OPTIONS.defaults.fps;
  $('shift').value = OPTIONS.defaults.shift;
  $('sampler').value = OPTIONS.defaults.sampler;
  $('scheduler').value = OPTIONS.defaults.scheduler;
  $('negative').value = OPTIONS.default_negative;

  preset.addEventListener('change', updateNotes);
  frames.addEventListener('change', updateNotes);
  $('fps').addEventListener('input', updateNotes);
  updateNotes();
}

function updateNotes() {
  const preset = OPTIONS.presets.find((p) => p.id === $('preset').value);
  $('presetNote').textContent = preset ? preset.note : '';
  const frames = Number($('frames').value);
  const fps = Number($('fps').value) || 24;
  $('framesNote').textContent = `${(frames / fps).toFixed(1)}s at ${fps} fps`;
}

// ------------------------------------------------------------------ status

async function refreshStatus() {
  try {
    const status = await api('/api/status');
    const dot = $('statusDot');
    const text = $('statusText');
    if (!status.comfy_up) {
      dot.className = 'dot down';
      text.textContent = 'ComfyUI offline — run ./scripts/comfy.sh wan';
      return;
    }
    dot.className = status.current ? 'dot busy' : 'dot up';
    const bits = [`ComfyUI ${status.comfy_version || 'up'}`];
    if (status.gpu && status.gpu.vram_free != null) {
      bits.push(`${(status.gpu.vram_free / 1024 ** 3).toFixed(1)} GiB VRAM free`);
    }
    if (status.queued) bits.push(`${status.queued} queued`);
    text.textContent = bits.join(' · ');
  } catch {
    $('statusDot').className = 'dot down';
    $('statusText').textContent = 'service unreachable';
  }
}

// ------------------------------------------------------------------- image

function setImage(file) {
  pickedFile = file || null;
  const preview = $('imagePreview');
  const empty = $('dzEmpty');
  const clear = $('clearImage');
  if (!pickedFile) {
    preview.hidden = true;
    preview.removeAttribute('src');
    empty.hidden = false;
    clear.hidden = true;
    return;
  }
  preview.src = URL.createObjectURL(pickedFile);
  preview.hidden = false;
  empty.hidden = true;
  clear.hidden = false;
}

function wireDropzone() {
  const zone = $('dropzone');
  const input = $('imageInput');

  zone.addEventListener('click', (event) => {
    if (event.target.id !== 'clearImage') input.click();
  });
  zone.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); input.click(); }
  });
  input.addEventListener('change', () => setImage(input.files[0]));

  ['dragenter', 'dragover'].forEach((type) =>
    zone.addEventListener(type, (event) => {
      event.preventDefault();
      zone.classList.add('over');
    }));
  ['dragleave', 'drop'].forEach((type) =>
    zone.addEventListener(type, (event) => {
      event.preventDefault();
      zone.classList.remove('over');
    }));
  zone.addEventListener('drop', (event) => {
    const file = event.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) setImage(file);
  });

  $('clearImage').addEventListener('click', (event) => {
    event.stopPropagation();
    input.value = '';
    setImage(null);
  });
}

// ---------------------------------------------------------------- generate

async function generate() {
  const button = $('generate');
  const error = $('formError');
  error.hidden = true;

  const prompt = $('prompt').value.trim();
  if (!prompt) {
    error.textContent = 'Write a prompt first.';
    error.hidden = false;
    return;
  }

  const form = new FormData();
  form.set('prompt', prompt);
  form.set('negative', $('negative').value);
  form.set('preset', $('preset').value);
  form.set('frames', $('frames').value);
  form.set('steps', $('steps').value);
  form.set('cfg', $('cfg').value);
  form.set('fps', $('fps').value);
  form.set('shift', $('shift').value);
  form.set('sampler', $('sampler').value);
  form.set('scheduler', $('scheduler').value);
  form.set('seed', $('seed').value);
  if (pickedFile) form.set('image', pickedFile, pickedFile.name);

  button.disabled = true;
  button.textContent = 'Queueing…';
  try {
    await api('/api/generate', { method: 'POST', body: form });
    await refreshJobs();
  } catch (exc) {
    error.textContent = exc.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = 'Generate video';
  }
}

// ------------------------------------------------------------------- jobs

async function refreshJobs() {
  let payload;
  try {
    payload = await api('/api/jobs?limit=300');
  } catch {
    return;
  }
  JOBS = payload.jobs;
  $('jobCount').textContent = payload.total ? `(${payload.total})` : '';
  renderActive();
  renderGrid();
  if (openJobId) refreshModal();
}

function renderActive() {
  const host = $('active');
  const live = JOBS.filter((j) => j.status === 'running' || j.status === 'queued');
  if (!live.length) { host.innerHTML = ''; return; }

  host.innerHTML = live.map((job) => {
    const running = job.status === 'running';
    const percent = Math.round((job.progress || 0) * 100);
    const elapsed = running && job.started_at
      ? duration(Date.now() / 1000 - job.started_at) : '';
    const where = running
      ? `${percent}% · ${job.steps} steps`
      : (job.queue_position ? `queued · position ${job.queue_position}` : 'queued');
    return `
      <div class="active-card">
        <div class="active-head">
          <strong>${running ? 'Rendering' : 'Waiting'}</strong>
          <button data-cancel="${job.id}">Cancel</button>
        </div>
        <div class="bar"><i style="width:${running ? percent : 0}%"></i></div>
        <div class="active-meta">
          <span>${where}</span>
          <span>${job.width}×${job.height} · ${job.frames}f${elapsed ? ' · ' + elapsed : ''}</span>
        </div>
        <p class="active-prompt">${escapeHtml(job.prompt.slice(0, 160))}</p>
      </div>`;
  }).join('');

  host.querySelectorAll('[data-cancel]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try { await api(`/api/jobs/${button.dataset.cancel}/cancel`, { method: 'POST' }); }
      catch { /* it probably finished on its own */ }
      refreshJobs();
    });
  });
}

function renderGrid() {
  const onlyDone = $('onlyDone').checked;
  const items = JOBS.filter((j) => (onlyDone ? j.status === 'done' : true));
  const grid = $('grid');
  $('empty').hidden = items.length > 0;

  grid.innerHTML = items.map((job) => {
    const thumb = job.has_thumb
      ? `style="background-image:url('/api/jobs/${job.id}/thumb')"` : '';
    const placeholder = job.has_thumb ? '' : ({
      running: 'rendering…', queued: 'queued', error: 'failed', cancelled: 'cancelled',
    }[job.status] || 'no preview');
    return `
      <article class="card" data-open="${job.id}">
        <div class="thumb" ${thumb}>${placeholder}</div>
        <div class="body">
          <div class="line1">${escapeHtml(job.prompt.slice(0, 110))}</div>
          <div class="line2">
            <span class="badge ${job.status}">${job.status}</span>
            <span>${job.width}×${job.height}</span>
            <span>${job.frames}f</span>
            <span>${ago(job.created_at)}</span>
          </div>
        </div>
      </article>`;
  }).join('');

  grid.querySelectorAll('[data-open]').forEach((card) => {
    card.addEventListener('click', () => openModal(card.dataset.open));
  });
}

// ------------------------------------------------------------------ modal

function jobById(id) { return JOBS.find((j) => j.id === id); }

function openModal(id) {
  const job = jobById(id);
  if (!job) return;
  openJobId = id;
  $('modal').hidden = false;
  document.body.style.overflow = 'hidden';
  refreshModal(true);
}

function closeModal() {
  openJobId = null;
  const player = $('player');
  player.pause();
  player.removeAttribute('src');
  player.load();
  $('modal').hidden = true;
  document.body.style.overflow = '';
}

function refreshModal(reload = false) {
  const job = jobById(openJobId);
  if (!job) { closeModal(); return; }

  const player = $('player');
  const source = job.has_video ? `/api/jobs/${job.id}/video` : '';
  if (reload || (source && !player.src.endsWith(source))) {
    if (source) { player.src = source; } else { player.removeAttribute('src'); player.load(); }
  }

  const download = $('btnDownload');
  download.href = `/api/jobs/${job.id}/download`;
  download.style.display = job.has_video ? '' : 'none';
  $('btnFullscreen').style.display = job.has_video ? '' : 'none';

  const rows = [
    ['status', job.status],
    ['size', `${job.width}×${job.height}`],
    ['frames', `${job.frames} (${(job.frames / job.fps).toFixed(1)}s @ ${job.fps}fps)`],
    ['steps', job.steps],
    ['cfg', job.cfg],
    ['sampler', `${job.sampler} / ${job.scheduler}`],
    ['shift', job.shift],
    ['seed', job.seed],
    ['mode', job.mode === 'image' ? 'image-to-video' : 'text-to-video'],
    ['render time', duration(job.duration)],
    ['created', new Date(job.created_at * 1000).toLocaleString()],
  ];
  if (job.error) rows.push(['error', job.error]);

  $('modalParams').innerHTML = rows.map(([key, value]) =>
    `<div><dt>${key}</dt><dd>${escapeHtml(value)}</dd></div>`).join('');
  $('modalPrompt').textContent = job.prompt;
}

function wireModal() {
  document.querySelectorAll('[data-close]').forEach((element) =>
    element.addEventListener('click', closeModal));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !$('modal').hidden) closeModal();
  });

  $('btnFullscreen').addEventListener('click', () => {
    const player = $('player');
    if (player.requestFullscreen) player.requestFullscreen();
    else if (player.webkitEnterFullscreen) player.webkitEnterFullscreen();
  });

  $('btnCopyPrompt').addEventListener('click', async () => {
    const job = jobById(openJobId);
    if (!job) return;
    await navigator.clipboard.writeText(job.prompt);
    $('btnCopyPrompt').textContent = '✓ Copied';
    setTimeout(() => ($('btnCopyPrompt').textContent = '⧉ Copy prompt'), 1200);
  });

  $('btnReuse').addEventListener('click', () => {
    const job = jobById(openJobId);
    if (!job) return;
    $('prompt').value = job.prompt;
    $('negative').value = job.negative;
    $('frames').value = job.frames;
    $('steps').value = job.steps;
    $('cfg').value = job.cfg;
    $('fps').value = job.fps;
    $('shift').value = job.shift;
    $('sampler').value = job.sampler;
    $('scheduler').value = job.scheduler;
    $('seed').value = job.seed;
    const preset = OPTIONS.presets.find((p) => p.width === job.width && p.height === job.height);
    if (preset) $('preset').value = preset.id;
    updateNotes();
    closeModal();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  $('btnDelete').addEventListener('click', async () => {
    const job = jobById(openJobId);
    if (!job) return;
    if (!confirm('Delete this generation and its video file? This cannot be undone.')) return;
    try {
      await api(`/api/jobs/${job.id}`, { method: 'DELETE' });
      closeModal();
      refreshJobs();
    } catch (exc) {
      alert(exc.message);
    }
  });
}

// -------------------------------------------------------------------- boot

(async function main() {
  wireDropzone();
  wireModal();
  $('generate').addEventListener('click', generate);
  $('onlyDone').addEventListener('change', renderGrid);
  $('prompt').addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') generate();
  });

  await loadOptions();
  await refreshStatus();
  await refreshJobs();

  setInterval(refreshStatus, 3000);
  setInterval(refreshJobs, 1500);
})();
