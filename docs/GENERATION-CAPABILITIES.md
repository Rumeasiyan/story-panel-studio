# Generation capabilities — brief for the goal-repo planning agent

Hand this to the agent working `goal-ai-story-video-network`. It describes what the
local generation service can and cannot do, with measured costs, so plans are built on
facts rather than assumptions.

**Service:** `ai-video-gen` at `/home/sshroot/external/ai-video-gen`, version 2.0.3.
**API:** `http://127.0.0.1:8189` — reachable on the LAN and Tailscale too (`0.0.0.0`).
**Reference:** `service/API.md` in that repo. Live contract: `GET /api/pipelines`.
**Hardware:** one RTX 3050, 8 GB VRAM. Jobs run **strictly one at a time**.

---

## 1. What this service does and does not do

**Does:** images, image editing, narration audio, subtitles, video.

**Does not:** story ideas, scripts, panel lists, assembly, thumbnails selection, SEO,
scheduling, upload. Those belong to the orchestrator. Do not plan work that expects this
service to sequence or assemble anything — it generates one asset per request and
returns a file.

---

## 2. Capabilities

| Pipeline | Kind | Required | Files accepted |
|---|---|---|---|
| `sdxl-text-to-image` | image | `prompt` | — |
| `sdxl-image-to-image` | image | `prompt` | `image` |
| `sdxl-inpaint` | image | `prompt` | `image`, `mask` |
| `flux2-text-to-image` | image | `prompt` | — |
| `flux2-edit` | image | `prompt` | `image`, `reference_2..4` |
| `z-image-text-to-image` | image | `prompt` | — |
| `tts-indic-parler` | audio | `text` | — |
| `tts-indicf5` | audio | `text` | `reference_audio` — **broken, do not plan around it** |
| `subtitles` | subtitle | — | `audio` |
| `wan22-video` | video | `prompt` | `image` — **weights deleted, would need an 18 GB re-download** |

### Image checkpoints

`sdxl-*` pipelines take a `model` parameter:

| `model` | Checkpoint | Prompt style | Suits |
|---|---|---|---|
| `anime` | Animagine XL 4.0 | prose | anime channels |
| `noobai` | NoobAI-XL v1.1 | **booru tags** | anime channels |
| `illustrious` | Illustrious-XL v2.0 | **booru tags** | anime channels |
| `cinematic` | RealVisXL V4.0 | prose | cinematic channels |

Booru-tag models want `1boy, solo, short black hair, city street, night`, not sentences.
Getting this wrong quietly degrades output rather than erroring.

Three anime checkpoints and three cinematic-capable generators exist, which matters for
the constraint that the four channels must look differentiated.

---

## 3. Measured costs — use these for planning, do not estimate

All measured on this machine, batch of 4, SDXL Lightning 4-step LoRA unless stated.

| Job | Cost |
|---|---|
| Panel, 1024×576 landscape | **5.0 s** |
| Panel, 832×1216 portrait | **15.5 s** |
| Panel, 1024×576, 25 steps, no LoRA | 15.4 s |
| FLUX.2 generate / instruction-edit | 18 s / 21 s |
| Narration, Indic Parler | ~68 s per job regardless of length |
| Subtitles, script-aligned | ~4 s |
| Video, 720p 5 s (if reinstalled) | ~27 min |

### Daily budget at 4 videos/day

| Panels/video | Landscape | Portrait |
|---|---|---|
| 60 | 20 min | 62 min |
| 120 | **40 min** | **2.1 h** |

**Portrait panels cost 3x landscape.** For 16:9 YouTube output, landscape is both cheaper
and needs no cropping. Decide aspect ratio deliberately; it is the single biggest lever
on daily GPU time.

Video generation is ~100x the cost of a panel and is not needed for a still-panel
format. Ken Burns motion in ffmpeg is free and belongs in the orchestrator.

---

## 4. Character consistency — tested, and the result constrains the plan

**Prompt-only consistency does not hold.** Tested 20 panels, NoobAI, identical character
tag block, only the scene varying, fixed seed (the favourable case):

- Style, wardrobe, hair colour and eye colour held across all 20.
- **Facial structure drifted enough to read as different people** in several panels.
- **An explicit `scar on left cheek` tag was ignored in ~18 of 20 panels.**
- 2 of 20 were unusable (one rendered no head), a 10% hard reject rate.

Adequate for one video; **not adequate for a serialised protagonist**. Plan for a
**trained character LoRA per recurring character**: roughly 25 curated images, trained
once, then free at inference via the `lora` parameter on any SDXL pipeline.

Precursor task: generate a character sheet — one character, multiple angles and
expressions — which doubles as the LoRA training set.

Evidence in issue #1 of the ai-video-gen repo.

---

## 5. Narration

Working: **Indic Parler-TTS**, Tamil and English, Apache-2.0, local, no per-use cost.

**Voice consistency works like character consistency.** Register a voice profile once and
reference it by name; the description is the only thing holding narrator identity, so it
must be byte-identical across episodes. Profiles enforce that.

```
POST /api/voices    {"name": "...", "engine": "indic-parler",
                     "language": "ta", "voice_description": "..."}
```

Two are already registered: `narrator-en-cinematic`, `narrator-tamil-anime`. Four
channels need four profiles.

Long text is chunked on sentence boundaries — including the Devanagari danda — and
concatenated with identical conditioning, so scripts of any length are one request.

**IndicF5 (true voice cloning) does not work.** Upstream packaging conflict, documented
in issue #2. Do not plan around it. If cloning becomes essential, that is a blocker to
raise, not a task to schedule.

---

## 6. Subtitles

Pass the original script as `script` and whisper is used **only for timing** — your
words are preserved exactly and cannot be rewritten by transcription error. Important
for Tamil, where ASR is weaker.

Outputs SRT, VTT, and JSON with per-word timings (usable for karaoke-style rendering).

---

## 7. Constraints the plan must respect

| Constraint | Consequence |
|---|---|
| One GPU, one job at a time | Queue depth is real. 4 videos/day of panels is ~40 min serial; nothing runs in parallel. |
| Local only, £0 per-use | Satisfies the $50/month opex cap. No hosted image API is needed or used. |
| FLUX.2 path is Apache-2.0 | Resolved. The VAE shipped in the ComfyUI template was non-commercial; klein's own Apache-2.0 VAE is used instead. No restriction on FLUX.2 output. |
| **NoobAI licence is "other"** (Fair AI Public License 1.0-SD) and the repo carries a not-for-all-audiences flag | Review before a monetised channel. The model can produce explicit output. |
| SDXL checkpoints are Open RAIL++-M | Use-based restrictions must be passed downstream. |
| Service has **no authentication** and is bound to `0.0.0.0` | Anything on the network can queue jobs and read or delete history. Fine on a trusted LAN; do not expose further. |
| Deleting a generation is complete and audited | `forget-generation` removes outputs, inputs, thumbnails, DB row, WAL. Useful if a channel needs content purged. |

---

## 8. How to call it

```bash
# discover the contract rather than hardcoding it
curl localhost:8189/api/pipelines

# queue a panel
curl -X POST localhost:8189/api/generate -H 'Content-Type: application/json' -d '{
  "pipeline": "sdxl-text-to-image", "model": "noobai",
  "prompt": "1boy, solo, black suit, city street, night, masterpiece",
  "width": 1024, "height": 576,
  "steps": 4, "cfg": 1.5, "sampler": "euler", "scheduler": "sgm_uniform",
  "lora": "sdxl_lightning_4step_lora.safetensors", "batch_size": 4 }'

# poll, then collect
curl localhost:8189/api/jobs/<id>
curl localhost:8189/api/jobs/<id>/output?index=0 -o panel.png
```

The response echoes the **resolved** parameters including a concrete seed — record those,
not the request, so any panel can be regenerated exactly.

---

## 9. Open items that affect planning

| Issue | Effect on the plan |
|---|---|
| #1 character LoRA needed | Blocks serialised characters. Schedule the character-sheet + training task before channel launch. |
| #2 IndicF5 broken | No voice cloning. Parler descriptions are the working path. |
| ~~#3 FLUX.2 VAE licence~~ | **Closed.** FLUX.2 output is Apache-2.0 and carries no commercial restriction. |
