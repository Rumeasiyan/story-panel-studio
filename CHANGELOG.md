# Changelog

Notable changes per version. The version lives in `VERSION`; see AGENTS.md for when
each part changes.

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
