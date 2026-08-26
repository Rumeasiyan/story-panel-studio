# Model choices

Pins, hashes, licences: `config/model-profiles.yaml`. Narration defaults: `config/voice-locks.yaml`.

Status: **live** = wired in · **candidate** = evaluated, not installed · **rejected** = ruled out.

## Images

| Job | Model | Licence | Status |
|---|---|---|---|
| Anime panels | NoobAI-XL v1.1 | Fair AI Public License 1.0-SD ⚠ verify commercial | live |
| Anime, LoRA base | Illustrious-XL v2.0 | CreativeML Open RAIL-M | live |
| Cinematic panels | cinematic-sdxl | CreativeML Open RAIL++-M | live |
| Fast drafts | SDXL Lightning 2/4-step | CreativeML Open RAIL++-M | live |
| Fast text-to-image | Z-Image Turbo | Apache-2.0 ⚠ repo declares none | live |
| Image editing | FLUX.2 klein 4B | Apache-2.0 | live |
| Character consistency | LoRA, trained locally (kohya-ss) | — | live |

## Video

| Job | Model | Licence | Status |
|---|---|---|---|
| Image-to-video, iteration | Wan 2.1 Fun-InP 1.3B | Apache-2.0 | live |
| Text/image-to-video, quality | Wan 2.2 TI2V-5B | Apache-2.0 | live |

## Voice

Locked per language — do not substitute. See `config/voice-locks.yaml`.

| Language | Pipeline | Model | Anchor | Emotion | Licence |
|---|---|---|---|---|---|
| English | `tts-chatterbox` | Chatterbox | `assets/voices/locked/en.wav` | per-beat | MIT |
| Tamil | `tts-omnivoice` | k2-fsa/OmniVoice | `assets/voices/locked/a01-auto.wav` | speed only | Apache-2.0 |
| Sinhala | `tts-omnivoice` | k2-fsa/OmniVoice | `assets/voices/locked/a01-auto.wav` | speed only | Apache-2.0 |

| Rejected | For | Reason |
|---|---|---|
| Indic Parler-TTS | English | not publishable; still registered for Indic |
| IndicF5 | all | will not load — issue #2 |
| omnivoice-studio (GUI wrapper) | all | FSL-1.1-ALv2, no commercial use for 2 years |
| formant-shifting an anchor | all | changes timbre, not speaker identity |

## Speech-to-text

| Job | Model | Status |
|---|---|---|
| Subtitles / timing | Whisper (faster-whisper) | live |

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
| NoobAI-XL licence unresolved for commercial use | — |
| Anchors are synthetic, not a recorded person | #7 |
| Sinhala anchor is Tamil-derived; native candidates untested by ear | — |
