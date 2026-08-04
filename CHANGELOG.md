# Changelog

Notable changes per version. The version lives in `VERSION`; see AGENTS.md for when
each part changes.

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
