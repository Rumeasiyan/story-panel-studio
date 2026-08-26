# Model choices

**Locked. Do not substitute.** Machine-readable: `config/generation-locks.yaml`.
Pins and hashes: `config/model-profiles.yaml`. Reference output: `output/compare/`,
`output/voice-lock/`.

## Images

| Job | Use | Prompting | Licence |
|---|---|---|---|
| Anime panels | `sdxl-text-to-image` `model=anime` — Illustrious-XL v2.0 | booru tags | CreativeML Open RAIL-M |
| Cinematic panels | `sdxl-text-to-image` `model=cinematic` — RealVisXL V4 | prose | CreativeML Open RAIL++-M |
| Character consistency | LoRA, `./scripts/train-lora --base illustrious` | — | — |
| Fast drafts | `lora=sdxl_lightning_4step_lora.safetensors`, 4 steps, cfg 1.5, euler/sgm_uniform | — | CreativeML Open RAIL++-M |
| Establishing shots, no recurring character | `flux2-text-to-image` — FLUX.2 klein 4B | prose | Apache-2.0 |
| Image editing | `flux2-edit` — FLUX.2 klein 4B | prose | Apache-2.0 |

## Video

| | |
|---|---|
| Status | **Out of scope.** No weights installed. Do not download. |
| Why | Still-panel product; generation time did not justify the result. Motion belongs to the orchestrator. |

## Voice

| Language | Pipeline | Anchor | Emotion | Licence |
|---|---|---|---|---|
| English | `tts-chatterbox` | `assets/voices/locked/en.wav` | per-beat | MIT |
| Tamil | `tts-omnivoice` | `assets/voices/locked/a01-auto.wav` | speed only | Apache-2.0 |
| Sinhala | `tts-omnivoice` | `assets/voices/locked/a01-auto.wav` | speed only | Apache-2.0 |

Write scripts in **spoken** register, not written. Send beats as `segments`.

## Speech-to-text

| Job | Use |
|---|---|
| Subtitles / timing | `subtitles` — faster-whisper |

## Rejected

| Model | For | Reason |
|---|---|---|
| Animagine XL 4.0 | anime | ignored "heavy rain" in both test prompts |
| NoobAI-XL v1.1 | anime | Fair AI Public License 1.0-SD unresolved for commercial |
| Z-Image Turbo | fast drafts | CLIP loader type `z_image` unsupported by ComfyUI 0.34.0 |
| SDXL Lightning 2-step | fast drafts | quality too low |
| Wan 2.1 / 2.2 | video | out of scope |
| Indic Parler-TTS | English | not publishable; registered for Indic only |
| IndicF5 | all | will not load — issue #2, closed obsolete |
| omnivoice-studio (GUI) | all | FSL-1.1-ALv2, no commercial use for 2 years |
| formant-shifting an anchor | voice | changes timbre, not speaker identity |

## Environments

| Venv | Holds | Pinned for |
|---|---|---|
| `.venv` | ComfyUI + API | `transformers>=4.50.3` |
| `.venv-chatterbox` | Chatterbox | torch 2.13.0+cu130, `setuptools<81` |
| `.venv-omnivoice` | OmniVoice | torch 2.9.1+cu128 |
| `.venv-parler` | Indic Parler | `transformers==4.46.1` |
| `.venv-trainer` | kohya-ss sd-scripts | `transformers==4.54.1` |

Rebuild: `config/venv-locks/`.

## Open

| Item | Issue |
|---|---|
| Anchors are synthetic, not a recorded person | #7 |
| `kai.safetensors` training base was never recorded; verified working on illustrious | — |
