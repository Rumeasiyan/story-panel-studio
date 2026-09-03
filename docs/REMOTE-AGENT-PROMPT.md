# Remote agent prompt

Paste the block below into Claude Code (or any agent) on a machine that reaches the GPU
host over Tailscale. Replace `<GPU_HOST_IP>` with the output of `tailscale ip -4` on the
GPU host.

It is deliberately self-contained: the remote machine has no copy of this repository, so
everything the agent must not get wrong is stated inline rather than referenced.

---

You drive **story-panel-studio**, a local AI generation service running on another
machine. It generates images, narration, subtitles and image edits over one REST API.

**Base URL:** `http://<GPU_HOST_IP>:8189`

## The boundary

You are a **client**. The GPU host does the work.

- Do **not** install models, download weights, or run ComfyUI locally. Everything
  happens on the host.
- Do **not** try to reach port 8188. That is ComfyUI, it is bound to localhost on the
  host, and it executes arbitrary node graphs. The REST API on 8189 is the entire
  surface you need.
- If the API does not answer, the host is asleep or `./scripts/serve.sh` is not running.
  Say so; do not work around it.

## Start here, every session

```bash
curl -s http://<GPU_HOST_IP>:8189/api/status      # is it up, which version
curl -s http://<GPU_HOST_IP>:8189/api/pipelines   # the live contract
```

**Read `/api/pipelines` rather than hardcoding parameters.** Capabilities change on the
host without the URL changing.

## Locked models — do not substitute

These were chosen by generating candidates and judging the output. Picking a different
model because it looks better on paper silently changes the look or voice of a channel.

| Job | Call |
|---|---|
| Anime panels | `sdxl-text-to-image`, `model=anime` — **booru tags**, not prose: `1boy, solo, black suit, rain, night, neon` |
| Cinematic panels | `sdxl-text-to-image`, `model=cinematic` — prose |
| Establishing shot, no recurring character | `flux2-text-to-image` — prose, faster and better than SDXL here |
| Character consistency | `sdxl-text-to-image` + `lora=<name>.safetensors`, `lora_strength=1.15` |
| Fast drafts | `sdxl-text-to-image`, `lora=sdxl_lightning_4step_lora.safetensors`, `steps=4`, `cfg=1.5`, `sampler=euler`, `scheduler=sgm_uniform` |
| English narration | `tts-chatterbox` |
| Tamil / Sinhala narration | `tts-omnivoice`, `language=Tamil` or `Sinhala` |
| Subtitles | `subtitles`, `model_size=base`, pass `script` |
| Video | **out of scope** — no weights installed, do not ask for it |

`lora_strength` below 1.15 loses character identity outright, not just fine detail.

## Editing — pick by the shape of the change

| Change | Use | Time |
|---|---|---|
| A property everywhere — wardrobe, weather, time of day | `flux2-edit` | ~20–30s |
| One region you can mask — remove, add, replace | `sdxl-inpaint` + `mask` | ~30–50s |
| Combine subjects from **two or more images** | `qwen-image-edit` | **~10 min** |

Reach for `flux2-edit` first. It cannot do targeted removal or identity transfer — that
was measured, not assumed. Escalate only when it genuinely cannot do the job.

`qwen-image-edit` matches or beats the others on every operation and costs 17–25× the
time. **Only multi-image composition justifies it.** Ask the host operator to restart
ComfyUI between Qwen jobs — running them back to back OOM-kills the service.

## Narration

Send the script as `segments`, one entry per beat, so emotion changes between beats
while the voice does not. A whole script in one call comes out flat and long blocks get
truncated.

```bash
curl -X POST http://<GPU_HOST_IP>:8189/api/generate \
  -F pipeline=tts-chatterbox \
  -F 'segments=[{"text":"He arrived early.","exaggeration":0.35,"cfg_weight":0.30,"pause_after":0.5},
                {"text":"They took it in ninety seconds.","exaggeration":0.95,"cfg_weight":0.45}]'
```

- English has real emotion control (`exaggeration` 0–2, `cfg_weight` lower = slower).
- Tamil and Sinhala have **pacing only** (`speed`). OmniVoice has no emotion parameter;
  no setting changes that.
- **Write in spoken register, not written.** Literary Tamil (`வந்தான்`) and written
  Sinhala (`ඔහු … සිටියේය`) read as a news bulletin. Use `வந்துட்டாரு`,
  `එයාට ඔක්කොම නැති වුණා`.

## Assembling video

Assembly is **your** job — the service only generates. Things that will bite:

- Narration is **24 kHz mono**. Resample to **48 kHz stereo** or many players render
  silence with no error.
- Chatterbox and OmniVoice are **not level-matched** — OmniVoice is ~7 dB quieter.
  Normalise, e.g. `loudnorm=I=-16:TP=-1.5:LRA=11`.
- **Do not burn Sinhala subtitles with libass** (`ffmpeg -vf subtitles=`). It mis-shapes
  the script — vowel signs detach. Tamil survives it; Sinhala does not. Shape with
  Pango/PIL+raqm, or ship the `.srt` as a sidecar.
- **Time panels on beat boundaries, not subtitle cues.** Cue counts differ per language
  for the same story. The narration inserts a pause after each beat, so the longest
  silences in the wav *are* the beat boundaries: `silencedetect=noise=-40dB:d=0.28`,
  take the longest `n_beats - 1`.
- The same story runs different lengths per language. Pacing is per-language.
- Panels are 16:9; 9:16 delivery leaves ~half the frame black. Fill or regenerate.

## Job pattern

```bash
JOB=$(curl -s -X POST $SPS/api/generate -H 'Content-Type: application/json' \
      -d '{"pipeline":"...","prompt":"..."}' | jq -r .id)
curl -s $SPS/api/jobs/$JOB | jq -r .status          # queued|running|done|error
curl -s "$SPS/api/jobs/$JOB/output?index=0" -o out.png
```

One serialized worker: jobs queue, they do not run in parallel. Rough timings — SDXL
panel 24s, FLUX.2 18s, Lightning draft 12s, narration ~40s per language, subtitles 3–9s,
Qwen edit 7–10 min.

## Do not

- Substitute models, or "upgrade" to something newer-looking.
- Send prose to `model=anime` or booru tags to `model=cinematic`.
- Write narration in literary/written register.
- Ask for video.
- Commit generated assets to any repository.
