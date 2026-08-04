# Generation service

A local REST API for generating story-video assets: images, image edits, narration,
subtitles and video. It **generates only** — an external app queues jobs, polls them,
collects the files, and does assembly, thumbnails, SEO and upload.

**[API.md](API.md) is the reference for callers.** Interactive docs at `/docs`.
**[../docs/START-HERE.md](../docs/START-HERE.md)** is the orientation doc for the
consuming project: capabilities, recipes, measured costs and constraints in one place.

A small web console is served at `/`, built from the same API, for eyeballing results
and trying parameters by hand.

```bash
./scripts/serve.sh        # starts ComfyUI (wan mode) if needed, then the UI
```

Open <http://127.0.0.1:8189>. Ctrl-C stops both.

```bash
./scripts/serve.sh --no-engine     # UI only, ComfyUI already running
./scripts/serve.sh --mode image    # run the engine in image mode instead
make serve                         # same as ./scripts/serve.sh
```

## Security

**No authentication.** It binds to `127.0.0.1` and is a single-user local tool. Do not
put it on a network as-is — it would let anyone queue GPU work on this machine.

The important boundary: user input never becomes graph structure. The backend loads a
fixed API-format workflow from `workflows/api/` and substitutes only typed fields
(prompt, seed, size, frames, steps). ComfyUI's `/prompt` executes whatever graph it is
handed, so accepting a caller-supplied graph would be arbitrary execution on this
workstation. Uploaded images are re-encoded to PNG with Pillow rather than passed
through.

## Layout

| File | Role |
|---|---|
| `app.py` | FastAPI routes, parameter validation, range-aware file serving |
| `jobs.py` | SQLite history + the single serialized worker |
| `comfy_client.py` | ComfyUI HTTP/WebSocket client, progress, error translation |
| `pipelines/` | one module per capability; each declares its own typed parameters |
| `config.py` | paths and defaults |
| `static/` | the console: `index.html`, `app.js`, `style.css` — no build step, no CDN |
| `data/` | SQLite database, uploads, thumbnails — gitignored |

Adding a capability means adding a module under `pipelines/` and importing it in
`pipelines/__init__.py`. The API layer is generic and needs no change.

## Where files go

| Thing | Location |
|---|---|
| Rendered video | `output/video/<job-id>_00001_.mp4` |
| Start image (normalised) | `service/data/uploads/<job-id>.png` |
| Start image (as ComfyUI saw it) | `input/` |
| Thumbnail | `service/data/thumbs/<job-id>.jpg` |
| History | `service/data/app.db` |

## Two virtualenvs, on purpose

| venv | holds | why |
|---|---|---|
| `.venv` | ComfyUI, torch, FastAPI, whisper | the main environment |
| `.venv-parler` | parler-tts, its own torch | parler-tts pins `transformers==4.46.1`; ComfyUI needs `>=4.50.3` |

Installing parler-tts into the main environment silently downgrades transformers and
puts the image engine at risk. It runs as a subprocess instead
(`pipelines/parler_worker.py`), talking JSON over stdin/stdout. Any future model with
hard version pins should follow the same pattern rather than negotiating with the shared
environment.

Rebuild the TTS venv with:

```bash
python3.13 -m venv .venv-parler
.venv-parler/bin/pip install torch --index-url https://download.pytorch.org/whl/cu130
.venv-parler/bin/pip install git+https://github.com/huggingface/parler-tts.git soundfile
```

## Deleting a generation completely

One generation leaves data in seven places, two of them non-obvious: the **mp4 embeds
the full prompt, negative prompt and seed** in its metadata, and **ComfyUI keeps its own
copy** of the start image in `input/` plus the prompt in its in-memory history.

The UI's delete button and `scripts/forget-generation` both clear all seven:

| # | Location | Holds |
|---|---|---|
| 1 | `output/video/<id>_*.mp4` | the render, and the prompt in its metadata |
| 2 | `service/data/uploads/<id>.png` | the normalised start image |
| 3 | `service/data/thumbs/<id>.jpg` | the thumbnail |
| 4 | `input/<id>.png` | ComfyUI's own copy of the start image |
| 5 | `service/data/app.db` | history row: prompt, seed, every parameter |
| 6 | ComfyUI in-memory history | the prompt again |
| 7 | free pages in `app.db`, and `app.db-wal` | deleted rows, until `VACUUM` **and** a WAL checkpoint |

```bash
./scripts/forget-generation <job-id>          # one generation
./scripts/forget-generation --all             # everything, ever
./scripts/forget-generation <job-id> --shred  # overwrite bytes before unlinking
./scripts/forget-generation --audit           # report residue, delete nothing
```

`--audit` is the proof: it re-scans every location, including raw bytes of the database,
and exits non-zero if anything remains.

Unlinking a file does not erase its bytes from the disk, and `--shred` is weaker than
it sounds:

- On **copy-on-write filesystems (btrfs, ZFS, bcachefs)** an in-place overwrite is
  written to *new* blocks, leaving the original content untouched. `--shred` cannot do
  what its name implies. It warns when it detects one.
- On **SSDs**, wear levelling keeps old copies in cells the OS cannot address.
- **Snapshots** retain everything regardless. Check with `sudo btrfs subvolume list /`.

What actually protects remnants is full-disk encryption: on a LUKS volume they are
unreadable once the machine is powered off.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/options` | presets, frame choices, samplers, defaults |
| `GET` | `/api/status` | ComfyUI reachability, VRAM, queue depth |
| `POST` | `/api/generate` | multipart: prompt, negative, preset, frames, …, image |
| `GET` | `/api/jobs` | history, newest first |
| `GET` | `/api/jobs/{id}` | one job |
| `POST` | `/api/jobs/{id}/cancel` | interrupt a running job or drop a queued one |
| `DELETE` | `/api/jobs/{id}` | delete job, video and thumbnail |
| `GET` | `/api/jobs/{id}/video` | stream with Range support (seeking, fullscreen) |
| `GET` | `/api/jobs/{id}/download` | download as `<job-id>.mp4` |
| `GET` | `/api/jobs/{id}/thumb` | first-frame JPEG |
| `GET` | `/api/jobs/{id}/source` | the start image, if there was one |

## Regenerating the workflow template

`workflows/api/wan22_ti2v_5b.json` is generated from the committed UI workflow. If the
UI workflow changes, or ComfyUI's node schemas do:

```bash
./scripts/comfy.sh wan                       # in one terminal
./scripts/workflow-to-api \
  workflows/video/wan22/wan2.2_ti2v_5B_official.json \
  -o workflows/api/wan22_ti2v_5b.json
```

If node ids shift, update the `NODE_*` constants in `config.py`.

## Notes

- Resolution and frame count are not capped to this GPU. The only enforced rules are
  the model's own: dimensions snap to multiples of 16, frame count to 4n + 1. The form
  shows the cost of a setting, rescaled against whatever GPU is detected, and warns —
  but never refuses. Raise `UI_MAX_DIM` / `UI_MAX_FRAMES` in `config/runtime.env` if the
  sanity bounds (4096 px, 1001 frames) get in your way on a bigger machine.
- One render at a time. Extra requests queue; the UI shows queue position.
- The first render of a session loads ~18 GB of weights and is much slower than later
  ones.
- Progress comes from ComfyUI's WebSocket, so the bar tracks real sampler steps.
- If the service restarts mid-render, that job is marked failed — it cannot be resumed.
