# Decision log

Append-only, newest first. One entry per decision a competent person would later ask
"why is it like this?" about: architecture, dependencies, resolved open questions,
reversals. **Not** routine implementation choices.

The **Why** should be longer than the **Decision**. What was built is visible in the
code; why it was built that way, and what was rejected, is not.

Template:

```markdown
## YYYY-MM-DD — Title

**Decision.** What was decided, in one or two sentences.

**Why.** The reasoning. What alternatives were considered and why they lost. What
trade-off was accepted.

**Consequences.** What this makes easy, what it makes hard, what now has to be
maintained.

**Refs.** Commits, files, issues, external sources.
```

---

## 2026-08-04 — Renamed to story-panel-studio and published under Apache-2.0

**Decision.** Renamed from `ai-video-gen` on disk and on GitHub, licensed Apache-2.0,
made public.

**Why.** The old name described a category, not this project, and returned nothing
useful in search. `story-panel-studio` names what it makes. Apache-2.0 rather than MIT
for the explicit patent grant, and rather than a copyleft licence because the goal is
adoption; it is also consistent with most of the pinned model weights. The copyleft in
ComfyUI does not reach this repository — the service talks to it over HTTP and imports
none of its code, which was verified before choosing.

**Consequences.** Anything referring to the old path breaks, including the consuming
goal repo, which was updated. **Python virtualenvs do not survive a directory rename**:
`bin/activate`, `pyvenv.cfg` and every console-script shebang embed the absolute path, so
all three venvs needed patching. `scripts/doctor.sh` did not catch it because it invokes
`.venv/bin/python` by absolute path, while `scripts/comfy.sh` sources `activate` and got
system Python with no torch. A rebuild via `./bootstrap.sh --repair` is the alternative
to patching.

**Refs.** `10a5b89`, `README.md`, `LICENSE`.

## 2026-08-04 — Character identity comes from a trained LoRA, not from prompting

**Decision.** Recurring characters get a trained LoRA per character, produced by
`scripts/train-lora`. Prompt-only consistency is not used for serialised protagonists.

**Why.** Measured both. Twenty panels with an identical character tag block and a fixed
seed produced faces that read as different people, and an explicit `scar on left cheek`
tag was ignored in 18 of 20 panels. The same twenty scenes with a LoRA trained on 28
curated images held the face across roughly 17 of 20 and raised the scar to 8 of 20.
The alternatives were reference-based conditioning through `flux2-edit`, which pays an
encoding cost on every panel and was untested at length, or accepting drift, which for
a serialised protagonist means viewers see a different actor each episode. A LoRA costs
about an hour of GPU time once and nothing at inference.

**Consequences.** Every recurring character needs a character sheet and a training run
before it can appear in a series. Fitting SDXL training into 8 GB forces
`--cache_text_encoder_outputs`, which forces UNet-only training, which means the trigger
word has no text-encoder association: prompts must still describe the character in full.
The LoRA shifts the face; the prompt still carries the identity. The scar remains
unreliable at roughly 40%, so small distinguishing marks should not be load-bearing in a
character design without further curation.

**Refs.** Issue #1, `scripts/train-lora`, `output/evidence/`, `reports/BENCHMARKS.md`.

## 2026-08-03 — Deleted the Wan video models from this machine

**Decision.** Removed Wan 2.2 TI2V-5B and Wan 2.1 Fun-InP weights (22.79 GB), keeping
their profiles in `config/model-profiles.yaml`.

**Why.** The consuming venture produces **still-panel** story videos — a sequence of
images with narration, not generated motion. Wan was installed before that was clear.
Measured, a 5-second 720p clip costs 26 min 48 s, against 5 s for a panel with the
Lightning LoRA; video is roughly 100x the cost of the thing actually needed. Ken Burns
pan/zoom over stills is an ffmpeg filter and free. Disk was the binding constraint —
three requested image models needed 19.9 GB against 20 GB free — and the video weights
were the largest reclaimable thing. Keeping the manifest entries means the decision is
reversible with one command and no loss of fidelity, which is the whole point of a
recipe repository.

**Consequences.** `wan22-video` remains a registered pipeline and fails with a clear
"model file not found". Restoring costs an 18 GB download. If the format ever moves to
real motion, this needs revisiting.

**Refs.** `dbadf3e`, `config/model-profiles.yaml`, `reports/BENCHMARKS.md`.

## 2026-08-03 — Z-Image Turbo via int8 safetensors, not GGUF

**Decision.** Installed `Comfy-Org/z_image_turbo`'s int8 variant instead of the
requested `unsloth/Z-Image-Turbo-GGUF`.

**Why.** The pinned ComfyUI has no GGUF loader node; GGUF would require
`city96/ComfyUI-GGUF` as the repository's first third-party custom node. This project
deliberately adds nodes one at a time, pinned, after inspecting their dependency
changes, because node packs can replace torch and CUDA packages — a risk already
realised once here via plain `pip`. ComfyUI ships `image_z_image_turbo_int8` natively,
and the int8 build reuses the `qwen_3_4b` encoder already installed for FLUX.2, so the
native path costs 6.54 GB new against 5.02 GB plus a node dependency. The nvfp4 variant
is smaller still but requires a Blackwell GPU; this is Ampere.

**Consequences.** No custom nodes are installed, so the "core setup works with zero
third-party nodes" property holds. If GGUF is wanted later — for quantised builds of
other models — the node still has to be added deliberately.

**Refs.** `dbadf3e`, `service/pipelines/z_image.py`.

## 2026-08-01 — parler-tts isolated in its own virtualenv

**Decision.** `parler-tts` lives in `.venv-parler` and runs as a subprocess speaking
JSON over stdin/stdout, rather than being installed into `.venv`.

**Why.** `parler-tts` hard-pins `transformers==4.46.1`; ComfyUI requires `>=4.50.3`.
Installing it into the main environment silently downgraded transformers from 5.14.1 and
left the image engine one restart from breaking — discovered only because `pip check`
was run afterwards. Restoring transformers broke parler in turn (`ImportError:
isin_mps_friendly`), confirming the two genuinely cannot share an environment. The
alternatives were dropping Tamil narration, or letting a TTS model dictate the image
engine's dependencies. Isolation costs 6.2 GB of duplicated torch and a process
boundary; both are cheaper than an unreliable engine.

**Consequences.** TTS has a second environment to maintain and rebuild.
`pipelines/tts.py` must marshal requests rather than call the model directly. Any future
model with hard pins should follow the same pattern instead of negotiating with `.venv`.

**Refs.** `0c6cf50`, `service/pipelines/parler_worker.py`, `service/README.md`.

## 2026-08-01 — IndicF5 documented as unavailable rather than removed

**Decision.** The `tts-indicf5` pipeline stays registered and raises an explanation
naming the cause and the alternative, instead of being deleted.

**Why.** IndicF5 is the better fit for this project — true voice cloning from a
reference clip, which is what holds one narrator identical across hundreds of episodes,
and MIT licensed. Only its packaging is broken: the bundled remote code targets an older
f5-tts and an older transformers. On transformers 5.x it fails constructing the model on
a meta device; pinning to 4.46.1 exposes a `load_model()` signature mismatch against
every published f5-tts release; and its dependencies conflict with parler-tts. Deleting
the pipeline would lose that analysis and invite someone to repeat it. A registered
pipeline that explains itself becomes a working path again with no API change if
upstream fixes packaging.

**Consequences.** A pipeline exists that always fails. The error text carries the
reasoning, so this is a documented state rather than a bug.

**Refs.** `0c6cf50`, `service/pipelines/tts.py` (`INDICF5_UNAVAILABLE`).

## 2026-08-01 — Pipelines are registered modules, not routes

**Decision.** Each capability is a module under `service/pipelines/` declaring its own
typed parameters; `app.py` stays generic and adds no route per capability.

**Why.** The service began as a single-purpose Wan video UI. Adding images, editing,
narration and subtitles as more endpoints would have meant duplicated validation and a
form that drifts from what callers actually see. With a registry, `GET /api/pipelines`
returns the parameter contract, so the external orchestrator discovers capabilities
instead of hardcoding them, and the built-in console builds its form from the same
source and cannot diverge. The cost is one indirection between a request and the graph
it builds.

**Consequences.** Adding a capability means adding a module and importing it — no route
changes. Job rows are pipeline-agnostic (`params`, `files`, `outputs` as JSON), so the
schema does not change per capability.

**Refs.** `5cf93dd`, `service/pipelines/base.py`, `service/API.md`.

## 2026-08-01 — Deletion clears the write-ahead log, not just the row

**Decision.** `delete_job` runs `PRAGMA wal_checkpoint(TRUNCATE)` alongside `VACUUM`,
and `--audit` scans `app.db`, `-wal` and `-shm`.

**Why.** The requirement was that deleting a generation leaves no trace. `VACUUM`
reclaims free pages in the main database but does nothing about `app.db-wal`, so a
deleted prompt and seed stayed readable in the sidecar. Found by planting a canary row,
deleting it through the real endpoint, then grepping the files — the audit tool had
reported clean because it only read the main database. Reasoning about SQLite's
behaviour would not have caught it; executing the delete and searching the bytes did.

**Consequences.** Deletion is slower (a checkpoint per delete). `--audit` is meaningful
as proof rather than a formality, and the same canary test is worth repeating if the
storage layer changes.

**Refs.** `48b271c`, `service/jobs.py` (`purge_database`).

## 2026-08-01 — The UI binds beyond loopback; ComfyUI never does

**Decision.** `UI_HOST=0.0.0.0` is supported and currently set. `scripts/comfy.sh`
refuses any non-loopback host.

**Why.** The operator asked for LAN access after being shown that the UI has no
authentication, that Fedora Workstation's firewall zone already permits 1025-65535/tcp
so nothing else would block it, and that Tailscale and SSH tunnelling were available
alternatives. That is their call to make. The engine is different in kind: ComfyUI's
`/prompt` executes arbitrary node graphs, so exposing it is remote code execution rather
than a privacy question, and no operator preference changes that.

**Consequences.** Anything reachable on the network can queue GPU work and read or
delete every job. The launcher prints every reachable URL and the absence of auth on any
non-loopback bind. Reverting is one setting in `config/runtime.env`.

**Refs.** `a17635e`, `scripts/serve.sh`, `service/config.py`.

## 2026-08-01 — Downloads go through aria2, not huggingface_hub

**Decision.** `modelctl install` fetches with `aria2c` using 8 parallel connections,
writing straight into `models/`.

**Why.** The default `hf-xet` transport stalled outright — 2.26 GB of network traffic to
write 320 MB, then zero bytes per minute with concurrency pinned to 1 and "connection
struggling" in its logs. Plain single-stream HTTPS worked but sustained only 0.7 MB/s
against 2.0 MB/s with 8 parallel ranges, and 3.7 MB/s once authenticated. Writing
directly into `models/` also drops the free-space requirement from 2.1x the download
size to 1.05x, since nothing is staged in the Hugging Face cache first.

**Consequences.** `aria2c` is a runtime dependency for installs, with a documented
`--no-aria2` fallback. Interrupted downloads resume from the `.aria2` control file.

**Refs.** `65f9e14`, `scripts/modelctl`.

## 2026-08-01 — CUDA 13 torch, with whisper falling back to CPU

**Decision.** The main environment runs `torch 2.13.0+cu130`. `faster-whisper` probes
for `libcublas.so.12` and runs on CPU when it is absent.

**Why.** The driver reports CUDA 13.0, so cu130 wheels are the matching stable line.
`faster-whisper` runs on CTranslate2, which links the CUDA 12 runtime, and it fails only
on the first transcribe rather than at construction — so a naive try/except around model
loading does not catch it. Downgrading torch to suit subtitle alignment would trade the
image engine's performance for a task that takes 4.4 seconds on CPU.

**Consequences.** Subtitle alignment is CPU-bound and unaffected in practice. If
CTranslate2 ships CUDA 13 support, deleting the probe is enough.

**Refs.** `5cf93dd`, `service/pipelines/subtitles.py` (`_has_cuda12_runtime`).

## 2026-08-01 — Weights outside the submodule, reached by config

**Decision.** All weights live under the root `models/`, exposed to ComfyUI via
`config/extra_model_paths.yaml` passed at startup.

**Why.** The obvious alternative — copying or symlinking into
`engine/ComfyUI/models` — dirties a pinned submodule, makes updates conflict, and ties
a 50 GB model store to one engine. An absolute `base_path` regenerated by
`bootstrap.sh --repair` keeps the repository portable to another machine.

**Consequences.** ComfyUI must always be started through `scripts/comfy.sh`, which
passes the config. Launching `main.py` directly finds no models.

**Refs.** `bea8245`, `config/extra_model_paths.yaml`, `scripts/comfy.sh`.

## Narration is segmented, not one call per script

**Decision.** `tts-chatterbox` and `tts-omnivoice` accept a `segments` array and make one
generation call per beat, joined with per-beat pauses, rather than generating a script in
a single call.

**Why.** Two separate failures pushed the same way. Emotionally, a whole script at one
setting comes out flat — a beat that should be angry and one that should be grief-stricken
cannot share a delivery parameter, and flatness is the single thing that makes synthetic
narration sound synthetic. Mechanically, long blocks were being truncated: sampling stopped
around 518 of 1000 steps and produced audio at ~257 wpm against a natural 150–160, i.e. the
tail was being dropped silently. Short segments fixed both, and are also faster — 3–4s per
beat against ~16s for one long block.

**Why it is still generation, not orchestration.** One request produces one audio file.
Deciding what the beats are belongs to the caller, which is where script writing already
lives.

**Consequence.** The voice must be pinned by an anchor clip, because separate calls
otherwise invent a new speaker each time.

## Chatterbox for English, OmniVoice for everything else

**Decision.** English narration uses Chatterbox; Tamil and other languages use OmniVoice.
Indic Parler stays registered but is no longer the English path.

**Why.** Indic Parler is an Indic research model. It was chosen when it was the only local
Tamil option and then over-applied to English, where it does not sound publishable — that
was a judgement made on language coverage, not on listening. Chatterbox is MIT, sounds
human, and has a real emotion control (`exaggeration`). It has no Tamil, which is why both
exist.

**Known gap.** OmniVoice exposes no emotion parameter at all; `speed` is the only prosody
lever. Tamil beats are therefore paced rather than acted, and this is weaker than the
English path. Unresolved.

**Licence note.** The k2-fsa/OmniVoice *model* is Apache-2.0 and fine commercially. The
`omnivoice-studio` GUI wrapper is FSL-1.1-ALv2 and forbids commercial use for two years —
different project, do not install it.
