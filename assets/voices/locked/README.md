# Locked anchors

The voices pinned in `config/generation-locks.yaml`. "Locked" means the speaker, not the
delivery style — register is a property of the script text, not of these files, and
all three channels are written in spoken register.

Shared across languages, which is why this is not called `tamil/`. `a01-auto.wav`
anchors both the Tamil and the Sinhala channel so both are the same narrator.

**Caveat on Sinhala.** `a01-auto.wav` was generated with `language="Tamil"`, so it is a
voice speaking Tamil. Cloning it into Sinhala is cross-lingual and works, but may carry
Tamil phonetic colouring. Sinhala-native alternatives are in
`output/voice-sinhala-native/` alongside a direct A/B against this one — unresolved
until judged by ear.

Chosen by ear from `output/voice-tamil-voices/`.

**Why these are files and not settings.** `a01` and `a03` came from OmniVoice's
*auto* mode, which invents a new speaker on every call — nothing reproduces them.
Capturing the clip and cloning from it is the only way to use the same voice twice.
`m02`/`m03` came from *design* mode and are nominally reproducible from their
`instruct` tags, but design mode still varies between calls, so they are pinned the
same way.

Regenerating these from scratch is not possible. Do not delete them.

| File | Origin |
|---|---|
| `a01-auto.wav` | auto mode, unrepeatable |
| `a03-auto.wav` | auto mode, unrepeatable |
| `m02-young-low.wav` | `instruct="male, young adult, low pitch"` |
| `m03-young-high.wav` | `instruct="male, young adult, high pitch"` |

`ref_text` for all four is the sentence they were generated from:

> ஒவ்வொரு புதிய கிளாட் மாடலும் தான் எழுதும் ஒவ்வொரு வார்த்தையிலும் மறைமுக அடையாளம் பதிக்கிறது. ஆனால் நீங்கள் அதை ஒருபோதும் பார்க்க முடியாது.

## en.wav

English narrator. 8s trim of `output/voice-samples-chatterbox/en-calm-authoritative.wav`,
no formant shift. Driven per-beat by Chatterbox `exaggeration` / `cfg_weight`.

```bash
ffmpeg -y -i output/voice-samples-chatterbox/en-calm-authoritative.wav \
  -t 8 -ar 24000 -ac 1 assets/voices/locked/en.wav
```
