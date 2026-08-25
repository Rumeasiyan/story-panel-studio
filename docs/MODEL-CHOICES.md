# Model choices — at a glance

What is picked for each job, and why. Full pins, hashes and licences live in
`config/model-profiles.yaml`; licence detail in `reports/MODEL_LICENSES.md`.

Status: **live** = wired into the API · **local** = installed, not yet a pipeline ·
**candidate** = evaluated, not installed · **rejected** = tried, ruled out.

## Images

| Job | Model | Why | Licence | Status |
|---|---|---|---|---|
| Anime / manhwa panels | **NoobAI-XL v1.1** (`noobai-xl`) | Best anime adherence of the SDXL checkpoints tried | Fair AI Public License 1.0-SD — **verify before commercial use** | live |
| Anime, alt base | Illustrious-XL v2.0 (`illustrious-xl`) | LoRA training base; broader style range | CreativeML Open RAIL-M | live |
| Cinematic / realistic panels | **cinematic-sdxl** | Realistic channel look | CreativeML Open RAIL++-M | live |
| Fast drafts | **SDXL Lightning** 2/4-step LoRA | 5.0s vs 14.1s per image — iteration, not finals | CreativeML Open RAIL++-M | live |
| Fast text-to-image | Z-Image Turbo (`z-image-turbo`) | Few-step distilled alternative | Apache-2.0 (repackaged repo declares none) | live |
| Image editing / instruction edits | **FLUX.2 klein 4B** (`flux2-klein-4b`) | Edit an existing panel without regenerating it | Apache-2.0 | live |
| Character consistency | **LoRA, trained locally** (kohya-ss) | Prompting alone does not hold a face across panels. UNet-only — 8 GB forces it | n/a | live |

## Video

| Job | Model | Why | Licence | Status |
|---|---|---|---|---|
| Image-to-video, iteration | **Wan 2.1 Fun-InP 1.3B** | Small enough to iterate on 8 GB | Apache-2.0 | live |
| Text/image-to-video, quality | Wan 2.2 TI2V-5B | Better output, much slower | Apache-2.0 | live |

## Voice

| Job | Model | Why | Licence | Status |
|---|---|---|---|---|
| **English narration** | **Chatterbox** (Resemble AI) | The one that sounded human. Zero-shot cloning from ~5s; `exaggeration` + `cfg_weight` give per-beat emotion | MIT | **live** — `tts-chatterbox` |
| Tamil narration | **k2-fsa/OmniVoice** | 423h Tamil training data; cross-lingual cloning | Apache-2.0 | **live** — `tts-omnivoice` |
| Sinhala narration | *unsolved* | See below | — | — |
| Tamil / Indic, current fallback | Indic Parler-TTS | Only local Tamil option found; 21 languages, 12 emotions | Apache-2.0 | live — **English quality rejected** |
| Multilingual candidate | **k2-fsa/OmniVoice** | 646 languages incl. Tamil (423h) and Sinhala (12h); zero-shot cloning | Apache-2.0 | **live** — `tts-omnivoice` |
| — its GUI wrapper | ~~omnivoice-studio~~ | **Do not use.** FSL-1.1-ALv2 forbids commercial use for 2 years | FSL-1.1-ALv2 | rejected |
| Indic, unavailable | IndicF5 | Will not load; upstream-blocked (issue #2) | — | rejected |

### English voice — what was actually chosen

**Voice identity comes only from the reference clip.** No parameter changes age or
timbre; `exaggeration`/`cfg_weight` only change delivery.

| | Choice |
|---|---|
| Anchor | `assets/voices/reel-narrator-v1.wav` |
| Built from | Chatterbox stock speaker, formants shifted **+4%** |
| Picked over | +8% and +12% — both audibly thin. Stock alone read as generic AI narrator |
| Why formants | Resampling shifts pitch *and* formants; formants track vocal-tract length, which is what carries perceived age. Pitch-only sounds like a filter |
| Rebuild recipe | `assets/voices/README.md` |

Two levers moved the voice off "generic AI", not one: the +4% anchor, **and** rewriting
scripts in casual register — contractions, fragments, discourse markers. Narrator register
("Here is the part…", "It cannot prove…") reads as AI regardless of voice.

Per-beat emotion presets that worked for reels:

| Beat | exaggeration | cfg_weight |
|---|---|---|
| hook | 0.70 | 0.45 |
| explainer | 0.40 | 0.35 |
| turn | 0.65 | 0.38 |
| peak | 0.85 | 0.42 |
| close | 0.60 | 0.42 |

Next: replacing the anchor with a **real recorded human voice** — the stock-speaker
derivative is a stopgap. See issue #7.

## Speech-to-text

| Job | Model | Why | Status |
|---|---|---|---|
| Subtitles / timing | **Whisper** | Standard; `service/pipelines/subtitles.py` | live |

## Environments

Split because their pins conflict — installing any of them into `.venv` breaks the
image engine.

| Venv | Holds | Pinned because |
|---|---|---|
| `.venv` | ComfyUI + API | needs `transformers>=4.50.3` |
| `.venv-chatterbox` | Chatterbox | torch 2.6.0+cu124 |
| `.venv-parler` | Indic Parler | pins `transformers==4.46.1` |
| `.venv-trainer` | kohya-ss sd-scripts | pins `transformers==4.54.1` |

## Open licence questions

- **NoobAI-XL** — Fair AI Public License 1.0-SD. Unresolved for commercial use; it is
  the main anime checkpoint, so this is the one that matters.
- **Z-Image / Qwen3 repackages** — upstream is Apache-2.0, the repackaged repos declare
  nothing.
