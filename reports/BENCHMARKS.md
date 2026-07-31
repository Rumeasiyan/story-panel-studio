# Benchmarks

Append one entry per measured run. No benchmarks recorded yet — no model weights are
installed.

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
