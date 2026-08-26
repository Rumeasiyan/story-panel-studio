# Locked anchors

The voices pinned in `config/generation-locks.yaml`. "Locked" names the speaker, not the
delivery style — register is a property of the script text, not of these files, and all
three channels are written in spoken register.

**These are not regenerable and must survive any cleanup.** They live here rather than
in `output/` for that reason; `output/` gets wiped.

| File | Used for | Origin |
|---|---|---|
| `en.wav` | English | 8s trim of `_source-en-calm-authoritative.wav`, no formant shift |
| `_source-en-calm-authoritative.wav` | source of record for `en.wav` | Chatterbox stock speaker |
| `a01-auto.wav` | **Tamil + Sinhala** | OmniVoice auto mode — **cannot be regenerated** |
| `a03-auto.wav` | unused candidate | OmniVoice auto mode — cannot be regenerated |
| `m02-young-low.wav` | unused candidate | `instruct="male, young adult, low pitch"` |
| `m03-young-high.wav` | unused candidate | `instruct="male, young adult, high pitch"` |

OmniVoice's auto and design modes invent a new speaker on every call, so for `a01`,
`a03`, `m02` and `m03` the file **is** the voice. Losing one loses that narrator
permanently. Back them up outside the repository — they are gitignored as renders.

Rebuild `en.wav` only:

```bash
ffmpeg -y -i assets/voices/locked/_source-en-calm-authoritative.wav \
  -t 8 -ar 24000 -ac 1 assets/voices/locked/en.wav
```

`ref_text` for the OmniVoice anchors, required when cloning — it must match the clip:

> ஒவ்வொரு புதிய கிளாட் மாடலும் தான் எழுதும் ஒவ்வொரு வார்த்தையிலும் மறைமுக அடையாளம் பதிக்கிறது. ஆனால் நீங்கள் அதை ஒருபோதும் பார்க்க முடியாது.
