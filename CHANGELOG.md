# Changelog

Notable changes per version. The version lives in `VERSION`; see AGENTS.md for when
each part changes.

## 3.0.2 — 2026-08-26

### Fixed
- `faster-whisper` was missing from `requirements-project.txt`, so a clean
  `bootstrap.sh` produced a `subtitles` pipeline that accepted jobs and then failed with
  `ModuleNotFoundError`. It only ever worked because the original `.venv` had it
  installed by hand. Surfaced by wiping the environment and rebuilding. `soundfile` added
  for the same reason.

## 3.0.1 — 2026-08-26

### Fixed
- `flux2-edit` was locked as the image-editing choice without ever being run — "the only
  option" is not the same as "works", as Z-Image had just demonstrated. Verified: a
  wardrobe swap held face, pose, background and rain exactly, and a night-to-day edit
  held the character. Samples in `output/compare/`.
- `wan22-video` now says OUT OF SCOPE in its own description, so an agent reading
  `/api/pipelines` does not plan around it. It stays registered as an escape hatch and
  fails with an actionable message naming the install command.

### Changed
- `flux2-text-to-image` given a defined job: cinematic establishing shots with no
  recurring character. It beat RealVis on the same prompt (18s vs 24s) and is
  Apache-2.0, but it has no LoRA support and character consistency runs on LoRAs, so
  character work stays on SDXL. Previously it was registered but unlocked, which is the
  state that caused models to be picked at random in the first place.

## 3.0.0 — 2026-08-26

### Breaking
- `sdxl-*` `model` accepts only `anime` and `cinematic`. `noobai` and `illustrious` are
  gone as separate ids — `anime` now resolves to Illustrious-XL v2.0, which means
  **`model=anime` produces a different look than before and expects booru tags rather
  than prose**. Callers sending `noobai` or `illustrious` get a 400 naming the valid set.
- `z-image-text-to-image` deregistered. Its pipeline asks ComfyUI for CLIP loader type
  `z_image`, which ComfyUI 0.34.0 does not offer — it could not run at all.

### Changed
- Every generation choice is locked in `config/generation-locks.yaml` (renamed from
  `voice-locks.yaml`, now covering images and video too). One file an agent reads
  before generating anything.
- Video is out of scope. No Wan weights installed and none should be downloaded; motion
  belongs to the orchestrator, over still panels.
- `docs/MODEL-CHOICES.md` is the locked decision table, with a `Rejected` section so a
  ruled-out model is not re-proposed.

### Removed
- Animagine XL 4.0, NoobAI-XL v1.1, Z-Image Turbo, SDXL Lightning 2-step — 19.4 GB.
  Chosen by rendering the same two scenes through every candidate at a fixed seed
  (`output/compare/`) and judging the images. Animagine ignored "heavy rain" in both
  prompts; NoobAI produced the best face in the set but its Fair AI Public License
  1.0-SD is unresolved for commercial use and the channels are monetized.

### Notes
- `kai.safetensors` was verified to work on Illustrious before NoobAI was deleted; its
  training base had never been recorded, which is now listed as an open item.
- The Lightning 3.1x speedup in BENCHMARKS.md is batch-4. At batch 1 it is 24s -> 12s
  with a real quality cost, so it is for candidate batches, not finals.

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
