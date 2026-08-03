# Benchmarks

Append one entry per measured run. Measured results are below.

## How to measure

While a render is running, in a second terminal:

```bash
# Peak VRAM (MiB), sampled every second
nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 1 | tee logs/vram.txt

# RAM and swap
free -m -s 1 | tee logs/ram.txt
```

Wall-clock time is printed by ComfyUI in the terminal running `./scripts/comfy.sh`.

## Entry template

Copy this block for each run.

```markdown
### <date> — <profile> — <short label>

| Field | Value |
|---|---|
| Profile | |
| Model revision(s) | |
| Workflow file | |
| Mode | text-to-image / image-to-video |
| Input image | |
| Prompt | |
| Negative prompt | |
| Resolution | |
| Frames | |
| Steps | |
| Sampler / scheduler | |
| CFG | |
| Seed | |
| Launch mode | `./scripts/comfy.sh <mode>` |
| Wall-clock time | |
| Peak VRAM | |
| Peak RAM | |
| Swap used | |
| Output path | |
| Observed artifacts | |
```

## Measured on this machine

RTX 3050 8 GB, driver 580.173.02, torch 2.13.0+cu130, ComfyUI 0.29.0.
All figures are wall-clock from job submission to output on disk.

### SDXL images (1024x576, 25 steps, euler/normal)

| batch_size | total | per image |
|---|---|---|
| 1 | 24.2 s | 24.2 s |
| 2 | 34.5 s | 17.3 s |
| **4** | **56.5 s** | **14.1 s** |
| 6 | 83.6 s | 13.9 s |

Batching amortises model load and sampler setup. Returns flatten past 4, so
**batch_size 4 is the sweet spot** — 1.7x the throughput of single images for no
quality change. 1024x1024 measured separately at 35.2 s single.

`sdxl-image-to-image` costs the same as text-to-image at equal size and steps
(24.8 s measured at 1024x576, denoise 0.45).

### Panel volume, using 14.1 s per image

| panels per video | one video | four videos |
|---|---|---|
| 60 | 14 min | 56 min |
| 90 | 21 min | 1.4 h |
| 120 | 28 min | 1.9 h |

### SDXL Lightning LoRA (measured, batch_size 4, 1024x576)

| steps | LoRA | cfg | per image | speedup |
|---|---|---|---|---|
| 25 | none | 6.0 | 15.4 s | 1.0x |
| **4** | **lightning 4step** | **1.5** | **5.0 s** | **3.1x** |
| 2 | lightning 2step | 1.0 | 3.8 s | 4.1x |

Use `euler` / `sgm_uniform` and low cfg with Lightning; the usual cfg 6 washes out at
these step counts. Detail is softer than 25 steps, so the practical pattern is drafting
at 2-4 steps and re-rendering keepers at 25.

Panel volume with the 4-step LoRA:

| panels per video | one video | four videos |
|---|---|---|
| 60 | 5 min | 20 min |
| 120 | 10 min | 40 min |

### Subtitles

| model | audio | time |
|---|---|---|
| whisper base, script-aligned | 9 s of speech | 4.4 s |

Runs on CPU: faster-whisper links the CUDA 12 runtime and this project runs CUDA 13
torch, so the GPU path is unavailable. Cheap enough that it does not matter.

### Wan 2.2 video

| resolution | frames | steps | sampling | total |
|---|---|---|---|---|
| 512x288 | 41 | 20 | - | 65.1 s (cold, incl. ~18 GB weight load) |
| 1280x704 | 121 | 20 | 21 min 4 s (63.2 s/it) | 26 min 48 s |

The 720p run hit an out-of-memory during single-pass VAE decode and ComfyUI
recovered automatically with tiled decoding. Sampling itself was stable throughout
at 55-66 s/it, so the decode ceiling — not the sampler — is the real 720p limit on
8 GB. Shorter clips decode in one pass and avoid the fallback.

Derived rate: **0.58 s per megapixel-frame per step**. Cost of any other setting is
`width x height x frames x steps x 0.58 / 1e6` seconds.

### What this means for a still-panel story pipeline

Video generation is roughly 100x the cost of an image and is not needed for the
reference format, which is still panels over narration. Ken Burns motion in ffmpeg
is free. Budget the GPU for images.

## Planned first runs

### SDXL still image (production priority)

| Field | Value |
|---|---|
| Profile | `anime-sdxl` |
| Resolution | 1024x1024 |
| Steps | 28 |
| Launch mode | `./scripts/comfy.sh image` |

### Wan 2.2 TI2V-5B — safe first test

| Field | Value |
|---|---|
| Profile | `wan22-ti2v-5b` |
| Mode | image-to-video |
| Resolution | 512x288 |
| Frames | 41 |
| Batch size | 1 |
| Preview | disabled |
| Launch mode | `./scripts/comfy.sh wan` |

Only after that run is stable:

| Field | Value |
|---|---|
| Resolution | 640x360 |
| Frames | 49 |
| Batch size | 1 |

Do not start at 720p on this 8 GB card.
