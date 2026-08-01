# Generation API

This service generates assets. It does not orchestrate, assemble, or publish — an
external app queues jobs, polls them, and collects the files.

Base URL: `http://127.0.0.1:8189` (set `UI_HOST=0.0.0.0` in `config/runtime.env` to
reach it from another machine). Interactive reference: `/docs`.

**No authentication.** Anything that can reach the port can queue GPU work and read or
delete every job.

---

## Model

One job = one generation. Jobs are queued and executed **strictly one at a time**,
because there is one GPU. Submitting 200 panel requests is fine — they run in order.

```
POST /api/generate      → {"id": "...", "status": "queued"}
GET  /api/jobs/{id}     → poll until status is done|error|cancelled
GET  /api/jobs/{id}/output?index=N   → the produced file
```

Job status values: `queued`, `running`, `done`, `error`, `cancelled`.

---

## Discovering capabilities

```http
GET /api/pipelines
GET /api/pipelines/{id}
```

Returns every pipeline with its typed parameters, defaults, ranges and accepted files.
**Read this at startup rather than hardcoding** — capabilities are added server-side
without changing routes.

```json
{
  "id": "sdxl-text-to-image",
  "kind": "image",
  "accepts_files": [],
  "params": [
    {"name": "prompt", "type": "str", "required": true},
    {"name": "steps", "type": "int", "default": 25, "min": 1, "max": 100}
  ]
}
```

### Available pipelines

| id | kind | files it accepts |
|---|---|---|
| `sdxl-text-to-image` | image | — |
| `sdxl-image-to-image` | image | `image` |
| `sdxl-inpaint` | image | `image`, `mask` |
| `flux2-text-to-image` | image | — |
| `flux2-edit` | image | `image`, `reference_2..4` |
| `wan22-video` | video | `image` |
| `tts-indicf5` | audio | `reference_audio` |
| `tts-indic-parler` | audio | — |
| `subtitles` | subtitle | `audio` |

---

## Submitting

JSON when there are no files:

```bash
curl -X POST http://127.0.0.1:8189/api/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "pipeline": "sdxl-text-to-image",
    "prompt": "manhwa style, a young man in a worn suit in the rain at night",
    "model": "anime",
    "width": 1024, "height": 576,
    "steps": 25, "seed": 777
  }'
```

Multipart when sending files:

```bash
curl -X POST http://127.0.0.1:8189/api/generate \
  -F pipeline=sdxl-image-to-image \
  -F 'prompt=the same man, now in a noodle shop' \
  -F denoise=0.45 \
  -F image=@panel_01.png
```

Unknown parameters are ignored. Out-of-range numbers are clamped rather than rejected.
Dimensions snap to what the model requires (multiples of 8 for SDXL, 16 for Wan and
FLUX.2); frame counts snap to 4n+1. **The response echoes the resolved `params`** — use
that, not your request, as the record of what ran.

If `seed` is omitted or `-1`, a concrete random seed is chosen and returned, so any job
can be reproduced exactly.

---

## Polling

```bash
curl http://127.0.0.1:8189/api/jobs/{id}
```

```json
{
  "id": "288eadb818a6",
  "status": "running",
  "progress": 0.45,
  "stage": "sampling",
  "pipeline": "sdxl-text-to-image",
  "kind": "image",
  "params": {"...": "resolved values"},
  "outputs": [],
  "queue_position": 0,
  "duration": null,
  "error": null
}
```

`progress` is 0–1 and tracks real sampler steps for GPU jobs. `queue_position` is 0 when
running, otherwise its place in line. Poll about once a second; there is no webhook.

List with filters:

```
GET /api/jobs?limit=100&offset=0&kind=image&status=done
```

---

## Collecting output

```
GET /api/jobs/{id}/outputs                    list, with sizes
GET /api/jobs/{id}/output?index=0             the file (Range supported)
GET /api/jobs/{id}/output?index=0&download=true
GET /api/jobs/{id}/thumb                      JPEG preview
GET /api/jobs/{id}/input?key=image            the file you uploaded
```

A job can produce several files: `batch_size > 1` yields multiple images, and
`subtitles` always yields three (`.srt`, `.vtt`, `.json` — in that order).

---

## Cancelling and deleting

```
POST   /api/jobs/{id}/cancel
DELETE /api/jobs/{id}
```

Delete removes the outputs, thumbnail, uploaded inputs (including ComfyUI's copy), the
history row holding the prompt, and the database free pages and write-ahead log. It is
irreversible.

---

## Voice profiles

Voice consistency is the narration equivalent of character consistency: a channel needs
ONE narrator who never drifts across hundreds of episodes. Register the voice once, then
refer to it by name — passing a reference clip on every request means one wrong file
changes your narrator mid-series.

```http
GET    /api/voices                 list registered voices
POST   /api/voices                 register or replace
GET    /api/voices/{name}          one profile
GET    /api/voices/{name}/reference  the stored clip
DELETE /api/voices/{name}
```

Cloned voice (IndicF5) — needs a clip and its exact transcript:

```bash
curl -X POST http://127.0.0.1:8189/api/voices \
  -F name=narrator-en-cinematic \
  -F engine=indicf5 -F language=en \
  -F 'reference_text=This is the narrator voice for the channel, speaking clearly.' \
  -F reference_audio=@narrator.wav
```

Described voice (Indic Parler) — no clip:

```bash
curl -X POST http://127.0.0.1:8189/api/voices \
  -H 'Content-Type: application/json' \
  -d '{"name": "narrator-tamil-anime", "engine": "indic-parler", "language": "ta",
       "voice_description": "A calm middle-aged male narrator, measured pace, very high recording quality."}'
```

Then every episode just names it:

```bash
curl -X POST http://127.0.0.1:8189/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"pipeline": "tts-indicf5", "voice": "narrator-en-cinematic", "text": "..."}'
```

Profiles live in `service/data/voices/` and survive restarts. Four channels means four
profiles — one per art-style/language pair.

### Long narration

`text` of any length is accepted. It is split on sentence boundaries (including the
Devanagari danda used by Indic scripts) into chunks of ~300 characters, synthesised with
identical voice conditioning, and concatenated with `gap_seconds` of silence between
sentences. Both models degrade on very long inputs, so this is done for you rather than
left to the caller.

---

## Notes that matter in practice

**Character consistency.** Three tools, weakest to strongest:

1. `sdxl-image-to-image` at `denoise` 0.3–0.5 — preserves composition, drifts on new
   poses.
2. `flux2-edit` with reference images — pass a character sheet as `reference_2..4`.
3. A trained character LoRA — `lora` and `lora_strength` on any SDXL pipeline. Files go
   in `models/loras/`; list them with `GET /api/loras`. This is the reliable option for
   hundreds of panels.

**Subtitles.** Pass `script` with the exact narration text and whisper is used only for
timing, so transcription errors cannot rewrite your words. Strongly recommended for
Tamil, where ASR is weaker. Omit `script` to transcribe instead. The `.json` output
carries per-word timings for karaoke-style rendering.

**Narration.** Register a voice profile and pass `voice`; see above. Inline
`reference_audio`/`voice_description` still work for one-offs and A/B tests.

**Timing on an RTX 3050 8 GB**, measured:

| Job | Time |
|---|---|
| SDXL 1024×576, 25 steps | ~24 s (14.1 s each at `batch_size` 4) |
| SDXL img2img, same size | ~25 s |
| FLUX.2 klein text-to-image, 4 steps | ~18 s |
| FLUX.2 klein instruction edit | ~21 s |
| Subtitles, script-aligned, base model | ~4 s |
| Wan 2.2 video 720p 5s, 20 steps | ~27 min |

Video is far more expensive than everything else. For still-panel story videos you
likely do not need it at all.

**Errors** come back as `{"detail": "..."}` with a 4xx, or land on the job as
`status: "error"` with a human-readable `error`. A missing model file names the profile
to install.
