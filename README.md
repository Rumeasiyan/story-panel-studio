# story-panel-studio

**Self-hosted REST API for AI story-video assets — character-consistent panels, narration, and subtitles on a single 8 GB consumer GPU.**

Generate the pieces of a story video locally: illustrated panels with a recurring
character who actually stays the same person, narration in English or Tamil, and
word-timed subtitles. One HTTP API, no per-image cost, no data leaving the machine.

Built and measured on an **NVIDIA RTX 3050 (8 GB)**. Every number below is measured on
that card, not estimated.

```bash
git clone --recurse-submodules https://github.com/Rumeasiyan/story-panel-studio.git
cd story-panel-studio && ./bootstrap.sh --core-only
./scripts/modelctl install anime-sdxl
./scripts/serve.sh                    # → http://127.0.0.1:8189
```

---

## What problem this solves

Making a story video from AI images means solving four things that general-purpose tools
leave to you:

| Problem | What this does |
|---|---|
| **The character changes face between panels** | Trains a character LoRA and holds identity across a sequence. Measured: prompt-only fails, a trained LoRA holds ~17 of 20. |
| **Narration drifts between episodes** | Named voice profiles — register a narrator once, reference it forever. |
| **Subtitles get rewritten by transcription errors** | Pass your script; speech recognition supplies only the timing, never the words. |
| **Everything is a different tool** | One REST API, one queue, one job history. |

It **generates assets**. It does not assemble, schedule or publish — that is deliberate,
so it can sit behind whatever orchestrator you already have.

---

## Capabilities

| Pipeline | Produces |
|---|---|
| `sdxl-text-to-image` | Illustrated panels — anime/manhwa or photoreal |
| `sdxl-image-to-image` | Redraw an existing panel |
| `sdxl-inpaint` | Regenerate a masked region |
| `flux2-text-to-image` | 4-step generation with strong prompt adherence |
| `flux2-edit` | Instruction editing — "change the background to night" |
| `z-image-text-to-image` | Fast few-step generation |
| `tts-indic-parler` | Narration in 21 languages including Tamil |
| `subtitles` | SRT, VTT and word-level JSON, aligned to your script |
| `wan22-video` | Text/image to video (optional, heavy) |

Capabilities are discovered at runtime from `GET /api/pipelines`, so a caller reads the
contract rather than hardcoding it.

## Measured performance (RTX 3050, 8 GB)

| Job | Time |
|---|---|
| Panel 1024×576, 4-step Lightning LoRA, batch of 4 | **5.0 s each** |
| Panel 1024×576, 25 steps, no LoRA | 15.4 s |
| FLUX.2 generate / instruction edit | 18 s / 21 s |
| Narration, any script length | ~68 s |
| Subtitles, script-aligned | ~4 s |
| Character LoRA, end to end | ~1 h, once per character |

480 panels — four 120-panel videos — is about **40 minutes** of GPU time.
Full data in [`reports/BENCHMARKS.md`](reports/BENCHMARKS.md).

---

## Character consistency

The hard part of serialised story video. Prompting the same description every time does
not work: faces drift, and explicitly stated features get dropped.

Measured over 20 panels with an identical character description:

| | Prompt only | Trained LoRA |
|---|---|---|
| Reads as the same person | fails | ~17 of 20 |
| Explicit facial scar rendered | 2 of 20 | 8 of 20 |

```bash
pkill -f 'engine/ComfyUI/main.py'        # training needs the whole GPU
./scripts/train-lora --name kai --images characters/kai/images --base illustrious
```

Tuned to fit SDXL training into 8 GB — gradient checkpointing, cached latents, cached
text-encoder outputs, 8-bit Adam, UNet-only. Evidence in `output/evidence/`.

---

## Design

- **Reproducible, not a model warehouse.** Weights are never committed. Every model is
  pinned to a commit SHA with its size, SHA-256 and licence in
  [`config/model-profiles.yaml`](config/model-profiles.yaml); `modelctl` rebuilds the set.
- **User input never becomes graph structure.** ComfyUI's `/prompt` executes arbitrary
  node graphs, so pipelines fill typed fields into fixed templates. The engine binds to
  loopback and the launcher refuses anything else.
- **Complete deletion.** `forget-generation` removes outputs, uploads, thumbnails, the
  database row, and the SQLite write-ahead log — with `--audit` to prove it.
- **Isolated environments.** Models with conflicting pins (parler-tts, sd-scripts) run in
  their own virtualenvs so they cannot break the image engine.

## Requirements

NVIDIA GPU with 8 GB+ VRAM · 32 GB RAM recommended · Linux · Python 3.13 or 3.12 ·
~50 GB disk for models. Developed on Fedora 43.

## Documentation

| | |
|---|---|
| [`docs/START-HERE.md`](docs/START-HERE.md) | Orientation for an agent or integrator |
| [`service/API.md`](service/API.md) | Full API reference |
| [`AGENTS.md`](AGENTS.md) | Repo conventions and constraints |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Why things are the way they are |
| [`reports/MODEL_LICENSES.md`](reports/MODEL_LICENSES.md) | Licence position per model |

## Licensing

This project is **Apache-2.0** (see [LICENSE](LICENSE)). It talks to ComfyUI over HTTP
and imports none of its code.

**Model weights carry their own licences, and some restrict commercial use.** They are
recorded per model in [`reports/MODEL_LICENSES.md`](reports/MODEL_LICENSES.md). Check
them before publishing generated output commercially.

## Security

The API has **no authentication**. It is built for a trusted local network. Anything that
can reach the port can queue GPU work and read or delete generated files. Do not expose
it to the internet without putting authentication in front of it.
