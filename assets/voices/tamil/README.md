# Tamil voice anchors

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
