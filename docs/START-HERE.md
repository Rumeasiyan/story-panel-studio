# START HERE — story-panel-studio, for the goal-repo agent

Single entry point for the agent working `goal-ai-story-video-network`. Read this first;
everything else is linked from here.

**Repo:** `/home/sshroot/external/story-panel-studio` · **version 2.2.0**
**API:** `http://127.0.0.1:8189` (also on LAN and Tailscale)
**Engine:** ComfyUI on `127.0.0.1:8188` — never call it directly, see §7
**Hardware:** one RTX 3050, 8 GB VRAM. **One job at a time.**

---

## 1. The boundary — read before planning anything

This service **generates single assets**. It does not sequence, assemble, publish, or
schedule.

| It does | It does not |
|---|---|
| One image per request | Story ideas, scripts, panel lists |
| One narration file per request | Stitching panels into a video |
| One subtitle set per request | Thumbnails selection, SEO, upload |
| Trains character LoRAs | Any batching or orchestration |

Do not plan a task that expects this repo to loop, assemble or publish. Those belong to
the orchestrator.

---

## 2. Sixty-second start

```bash
# is it up?
curl -s localhost:8189/api/status | python3 -m json.tool

# if not:
cd /home/sshroot/external/story-panel-studio && ./scripts/serve.sh    # Ctrl-C stops both

# what can it do? (read this rather than hardcoding — it is the live contract)
curl -s localhost:8189/api/pipelines

# generate one panel
curl -s -X POST localhost:8189/api/generate -H 'Content-Type: application/json' -d '{
  "pipeline":"sdxl-text-to-image","model":"illustrious",
  "prompt":"1boy, solo, black suit, city street, night, masterpiece",
  "width":1024,"height":576,
  "steps":4,"cfg":1.5,"sampler":"euler","scheduler":"sgm_uniform",
  "lora":"sdxl_lightning_4step_lora.safetensors","batch_size":4}'

# poll until status is done|error|cancelled, then collect
curl -s localhost:8189/api/jobs/<id>
curl -s "localhost:8189/api/jobs/<id>/output?index=0" -o panel.png
```

The generate response echoes the **resolved** parameters including a concrete seed.
Record those, not your request — that is what reproduces the panel exactly.

---

## 3. Where things live

| Need | Go to |
|---|---|
| Full API reference | `service/API.md` |
| Which model to use for what | `docs/MODEL-CHOICES.md` |
| Narration engine and anchor per language — **locked, do not substitute** | `config/generation-locks.yaml` |
| Interactive API docs | `http://localhost:8189/docs` |
| Measured timings — never estimate | `reports/BENCHMARKS.md` |
| Licence position per model | `reports/MODEL_LICENSES.md` |
| Why something is the way it is | `docs/DECISIONS.md` |
| Repo rules, constraints, commands | `AGENTS.md` |
| Evidence for consistency claims | `output/evidence/` |
| Open problems | `gh issue list` in this repo |

---

## 4. Capabilities

| Pipeline | Kind | Required | Files |
|---|---|---|---|
| `sdxl-text-to-image` | image | `prompt` | — |
| `sdxl-image-to-image` | image | `prompt` | `image` |
| `sdxl-inpaint` | image | `prompt` | `image`, `mask` |
| `flux2-text-to-image` | image | `prompt` | — |
| `flux2-edit` | image | `prompt` | `image`, `reference_2..4` |
| `z-image-text-to-image` | image | `prompt` | — |
| `tts-chatterbox` | audio | `text` or `segments` | `reference_audio` — **English** |
| `tts-omnivoice` | audio | `text` or `segments` | `reference_audio` — **Tamil, Sinhala** |
| `tts-indic-parler` | audio | `text` | — · Indic fallback only, not for English |
| `subtitles` | subtitle | — | `audio` |
| `tts-indicf5` | audio | — | **broken, issue #2 — do not plan around it** |
| `wan22-video` | video | — | **weights deleted; 18 GB re-download if ever needed** |

### Checkpoints (`model` parameter on `sdxl-*`)

| `model` | Checkpoint | Prompt style |
|---|---|---|
| `illustrious` | Illustrious-XL v2.0 | **booru tags** |
| `noobai` | NoobAI-XL v1.1 | **booru tags** — see §6 licence flag |
| `anime` | Animagine XL 4.0 | prose |
| `cinematic` | RealVisXL V4.0 | prose |

Booru models want `1boy, solo, short black hair, city street, night`. Prose degrades
them quietly rather than erroring.

---

## 5. Recipes

### Panels for an episode

Use `sdxl-text-to-image` with `batch_size: 4` and the Lightning LoRA:
`steps: 4, cfg: 1.5, sampler: euler, scheduler: sgm_uniform,
lora: sdxl_lightning_4step_lora.safetensors`.

**Landscape 1024×576, not portrait.** Portrait costs 3x and needs cropping for 16:9.

### A recurring character

Prompt-only identity **does not hold** — measured, faces drift and explicit features are
ignored. Every recurring character needs a trained LoRA.

```bash
# 1. generate ~70 candidates at FULL quality (25 steps, no Lightning — Lightning
#    produces malformed faces that the negative prompt does not suppress)
# 2. curate to ~28: same face, varied framing and expression
# 3. stop the engine — 8 GB will not hold ComfyUI and a training run
pkill -f 'engine/ComfyUI/main.py'
./scripts/train-lora --name <char> --images characters/<char>/images --base illustrious
# 4. restart: ./scripts/serve.sh
```

~1 hour of GPU time per character, paid once. Then on every panel:

```json
{"pipeline":"sdxl-text-to-image","model":"illustrious",
 "lora":"<char>.safetensors","lora_strength":0.85,
 "prompt":"<char>, 1boy, solo, short black hair, golden eyes, black suit, <scene>"}
```

**The trigger word alone does nothing.** 8 GB forces UNet-only training, so it has no
text-encoder association. Keep the full character description in every prompt — the LoRA
shifts the face, the prompt carries the identity.

Trained and available now: `kai.safetensors`.

### Narration

Register a voice once, then reference it by name. The description is the only thing
holding narrator identity, so it must be byte-identical across episodes — a profile
enforces that.

The engine and anchor are **locked per language** — see `config/generation-locks.yaml`
and do not substitute:

| Language | Pipeline | Anchor |
|---|---|---|
| English | `tts-chatterbox` | `assets/voices/locked/en.wav` |
| Tamil | `tts-omnivoice` | `assets/voices/locked/a01-auto.wav` |
| Sinhala | `tts-omnivoice` | `assets/voices/locked/a01-auto.wav` |

Send the script as `segments`, one entry per beat, so emotion changes between beats
while the voice does not. A whole script in one call comes out flat, and long blocks
get truncated.

```bash
curl -X POST localhost:8189/api/generate \
  -F pipeline=tts-chatterbox \
  -F reference_audio=@assets/voices/locked/en.wav \
  -F 'segments=[{"text":"He arrived early, the way he had for eleven years.","exaggeration":0.35,"cfg_weight":0.30,"pause_after":0.5},{"text":"They took it from him in ninety seconds.","exaggeration":0.95,"cfg_weight":0.45}]'
```

Tamil and Sinhala use the same shape with `language` and `reference_text`, and `speed`
instead of `exaggeration`/`cfg_weight` — OmniVoice has no emotion control.

**Write in spoken register, not written.** Literary Tamil and written Sinhala read as a
news bulletin. Markers for each are in `config/generation-locks.yaml`.

Plain `text` still works and is chunked on sentence boundaries.

### Subtitles

Always pass `script` with your exact narration text. Whisper is then used **only for
timing**, so transcription errors cannot rewrite your words — this matters most for
Tamil, where ASR is weakest.

```json
{"pipeline":"subtitles","script":"<exact narration>","language":"en","model_size":"small"}
```
with `audio` as a file. Returns `.srt`, `.vtt`, and `.json` with per-word timings.

---

## 6. Costs and limits — use these, do not estimate

| Job | Cost |
|---|---|
| Panel 1024×576, Lightning 4-step, batch 4 | **5.0 s** |
| Panel 832×1216 portrait, same | 15.5 s |
| Panel 1024×576, 25 steps, no LoRA | 15.4 s |
| FLUX.2 generate / edit | 18 s / 21 s |
| Narration (any length) | ~68 s |
| Subtitles | ~4 s |
| Character LoRA, end to end | ~1 h once |

**Daily budget at 4 videos/day, landscape panels with Lightning:**

| Panels/video | 4 videos |
|---|---|
| 60 | 20 min |
| 120 | **40 min** |

Comfortably inside budget. Portrait triples it.

### Constraints

| Constraint | Consequence for planning |
|---|---|
| One job at a time | 4 videos of panels ≈ 40 min serial. Nothing parallelises. |
| Training blocks generation | No panels can be produced while a LoRA trains. |
| Local, zero per-use cost | Satisfies the $50/month opex cap. |
| **NoobAI** — Fair AI Public License, not-for-all-audiences flag | Review before using on a monetised channel. Illustrious is the safer default. |
| SDXL checkpoints — Open RAIL++-M | Use restrictions pass downstream. |
| FLUX.2 — Apache-2.0 throughout | No restriction. Resolved, see `docs/DECISIONS.md`. |
| No authentication, bound to `0.0.0.0` | Anything on the network can queue jobs and delete history. |
| Small facial marks unreliable (~40%) | Distinguish characters by silhouette, hair, wardrobe. Issue #6. |

---

## 7. Operating it

```bash
./scripts/serve.sh              # start engine + API
./scripts/serve.sh --no-engine  # API only
./scripts/doctor.sh             # health check, non-zero on failure
./scripts/modelctl status       # what is installed
./scripts/forget-generation --audit         # residue check
./scripts/forget-generation <job-id>        # erase a generation completely
```

**Never call ComfyUI on :8188 directly.** Its `/prompt` endpoint executes arbitrary node
graphs — that is remote code execution on this workstation, which is why the service
holds fixed templates and substitutes typed fields only.

If jobs fail with "model file not found", the message names the profile:
`./scripts/modelctl install <profile>`.

If the service dies when a terminal closes, it was a child of that shell. Start it
detached: `setsid nohup ./scripts/serve.sh > logs/serve.log 2>&1 &`.

---

## 8. Known open problems

| Issue | Effect |
|---|---|
| #2 IndicF5 broken | No voice cloning. Indic Parler descriptions are the working path. |
| #6 small marks unreliable | Affects character design decisions now, not later. |

Check `gh issue list` for current state — this table goes stale.

---

## 9. What is proven versus assumed

**Proven by measurement:** panel and narration timings; that prompt-only character
consistency fails; that a trained LoRA fixes it (~17 of 20 versus outright failure);
that Tamil and English narration work; that subtitles align to a supplied script.

**Not yet proven:** nothing has run at production cadence for a sustained period. The
per-asset numbers are solid; a full day of four videos end to end has not been executed.
