'use strict';

// A thin client over the same REST API an external orchestrator uses. The form is built
// from each pipeline's declared parameters, so adding a capability server-side needs no
// change here.

const $ = (id) => document.getElementById(id);

let PIPELINES = [];
let JOBS = [];
let openJobId = null;
const fileInputs = new Map();   // param name -> <input type=file>

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
    const accept = key.includes('audio') ? 'audio/*' : 'image/*';
    parts.push(`
      <label class="field">
        <span>${key} <em class="hint">(file)</em></span>
        <input type="file" id="f_${key}" accept="${accept}">
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
  }
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
