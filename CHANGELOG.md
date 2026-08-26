# Changelog

Notable changes per version. The version lives in `VERSION`; see AGENTS.md for when
each part changes.

## 2.4.1 — 2026-08-26

### Fixed
- `forget-generation` crashed with `IndexError` on any job that had a history row. It
  read `row["prompt"]`, but the `jobs` table has no such column — the caller's
  parameters live in `params` as JSON, under `prompt` for image work and `text` or
  `segments` for narration. The tool therefore only ever ran to completion for jobs
  already missing from the database, which is the opposite of what a deletion tool
  should do. Found by running it, not by reading it.

### Changed
- `docs/START-HERE.md` narration guidance was stale and actively misleading: it listed
  neither new pipeline and its recipe told the orchestrator to narrate with
  `tts-indic-parler`, the engine rejected for English. It now carries the locked
  per-language table, the `segments` shape, and the spoken-register rule.
- `docs/MODEL-CHOICES.md` reduced to tables. Its reader is an agent.
- Voice anchors moved to `assets/voices/locked/`; "narrator" named the wrong axis and
  misled twice, since register is a property of the script, not the anchor.

## 2.4.0 — 2026-08-26

### Added
- Two narration pipelines, `tts-chatterbox` and `tts-omnivoice`, both reachable through
  `POST /api/generate` like every other capability. Each runs as a subprocess worker in
  its own virtualenv (`chatterbox_worker.py`, `omnivoice_worker.py`) because their torch
  pins conflict with ComfyUI's and with each other.
- **Segmented narration.** Both pipelines accept a `segments` JSON array; each beat is a
  separate generation call with its own emotion, joined with per-beat pauses. This exists
  because a whole script generated in one call comes out flat — every sentence at one
  emotional setting — and long blocks were also being silently truncated when they
  overran the sampler's step budget. Plain `text` still works and is chunked on sentence
  boundaries.
- `voices.py` now covers `chatterbox` and `omnivoice` alongside the Indic engines, with
  the validation each needs: Chatterbox clones without a transcript, OmniVoice needs one
  when cloning and accepts `instruct` tags otherwise.
- `config/venv-locks/` — pip freezes plus rebuild instructions for the hand-built
  virtualenvs, which previously had no rebuild path at all.
- `docs/MODEL-CHOICES.md` — one table per job saying which model is used and why.

### Changed
- English narration is Chatterbox, not Indic Parler. Indic Parler is an Indic research
  model; it was chosen when it was the only local Tamil option and then over-applied to
  English, where it does not sound publishable. It stays registered for Tamil.

### Notes
- `instruct` is validated against OmniVoice's fixed tag vocabulary at request time, so a
  bad tag fails with the list of valid ones instead of inside the worker.
- OmniVoice exposes no emotion parameter. `speed` is the only prosody lever, so Tamil
  beats are paced rather than acted — weaker than the English path, and unresolved.

## 2.3.0 — 2026-08-04

### Changed
- Renamed from `ai-video-gen` to **story-panel-studio**, on disk and on GitHub. The old
  name described a category, not this project, and was invisible in search.
- Published under **Apache-2.0**. The service talks to ComfyUI over HTTP and imports none
  of its GPL code, so a permissive licence applies to this repository.
- README rewritten for people arriving cold: what problem it solves, measured numbers
  rather than claims, and the licensing and security caveats stated plainly.
- The original bootstrap prompt moved to `docs/history/original-brief.md`; it is a record
  of how the project started, not a description of what it is.

## 2.2.0 — 2026-08-04

### Added
- First trained character LoRA (`models/loras/kai.safetensors`) and the workflow that
  produced it: generate candidates, curate, train, verify against the prompt-only
  baseline. Character identity now holds across a panel sequence where it previously
  did not.
- Evidence sheets under `output/evidence/` comparing baseline and LoRA output.

### Fixed
- `train-lora` OOMed twice before running. It now refuses to start while another process
  holds GPU memory, and caches text encoder outputs so SDXL fits in 8 GB.

## 2.1.0 — 2026-08-04

### Added
- `scripts/train-lora` — trains a character LoRA on 8 GB, using kohya-ss sd-scripts
  pinned as a submodule at `tools/sd-scripts` and isolated in `.venv-trainer` (it pins
  transformers 4.54.1 against the main venv's 5.14.1). Closes the gap where the service
  could use a LoRA but not produce one, which blocked the only method shown to hold
  character identity across a panel run.

### Changed
- Replaced both voice profiles. `narrator-en-cinematic` was registered against the
  broken IndicF5 engine with an empty description and could never have run;
  `narrator-tamil-anime` was Tamil. Now `c1-en-anime-male` and
  `c3-en-cinematic-female`, both on Indic Parler and both verified generating audio.

## 2.0.3 — 2026-08-04

### Fixed
- FLUX.2 decoded through the VAE in `Comfy-Org/flux2-dev`, which carries the FLUX
  non-commercial licence. Because the VAE decodes every image, that licence would have
  governed the output despite klein's own weights being Apache-2.0. Switched to klein's
  own Apache-2.0 VAE (168 MB, the same VAE at different precision) and deleted the
  non-commercial file. The whole FLUX.2 path is now Apache-2.0. (#3)

## 2.0.2 — 2026-08-03

### Fixed
- The Hugging Face token was passed to aria2 as a command-line argument, making it
  readable by any local process through `/proc` for the whole duration of a download.
  It now goes in a mode-600 config file passed with `--conf-path`, removed in a
  `finally`. (#5)

## 2.0.1 — 2026-08-03

### Fixed
- Large model downloads aborted with HTTP 403 partway through. Hugging Face redirects
  to a CDN URL presigned with an expiry; aria2 resolved that redirect once and reused
  the signatures for the whole transfer, so any file big enough to outlive them failed.
  `aria2_download` now retries the whole invocation, which re-resolves the redirect for
  fresh signatures while `--continue` resumes from the partial file. (#4)

## 2.0.0 — 2026-08-03

First versioned release. The service was rewritten from a single-purpose Wan video UI
into a pipeline-registry generation API, which is the breaking change this version
records.

### Added
- Generation API with nine pipelines: SDXL text-to-image, image-to-image and inpaint;
  FLUX.2 klein generation and instruction editing; Z-Image Turbo; Wan 2.2 video;
  two narration engines; whisper subtitle alignment.
- Voice profiles (`/api/voices`) so a channel's narrator stays identical across episodes.
- Long-form narration chunked on sentence boundaries, including the Devanagari danda.
- `scripts/forget-generation` — erases every local trace of a generation, with `--audit`
  as proof.
- `scripts/fetch-tts`, `scripts/workflow-to-api`, SDXL Lightning LoRAs.
- Measured benchmarks for this machine in `reports/BENCHMARKS.md`.

### Changed
- Downloads use aria2 with 8 connections after the default transport stalled.
- Wan video weights removed from disk to make room for image models; profiles retained.

### Fixed
- Deleted prompts survived in the SQLite write-ahead log.
- Uploads were silently discarded by an `isinstance` check against FastAPI's
  `UploadFile` subclass rather than Starlette's.
- `hidden` attributes were overridden by CSS `display` rules, leaving the viewer modal
  permanently open.
