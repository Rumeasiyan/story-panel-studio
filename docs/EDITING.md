# Editing images

**Pick the tool by the shape of the change, not by which model looks best.** Every
option here was tested; the failures below are recorded so they are not retried.

| You want to | Use | Preserves |
|---|---|---|
| Change a property everywhere — wardrobe, weather, time of day, palette | `flux2-edit` | composition, roughly |
| Change one **region** — remove, add or replace something | `sdxl-inpaint` + mask | everything outside the mask, **pixel-exact** |
| Put a known character in a new scene | `sdxl-text-to-image` + character LoRA | the character's identity |
| Composite two finished images into one | *not achievable locally* — use a LoRA | — |

## Global restyle — `flux2-edit`

Instruction editing. No spatial targeting: it rewrites the whole frame toward the
instruction.

```bash
curl -X POST localhost:8189/api/generate \
  -F pipeline=flux2-edit \
  -F 'prompt=change his black suit to a grey turtleneck, keep the face and pose exactly the same' \
  -F image=@panel.png
```

| Param | Use |
|---|---|
| `steps` | 4 is the design point for klein. Compositional asks do not improve much above ~20. |
| `denoise` | 1.0 regenerates from the instruction and keeps nothing structurally. Lower values keep more of the source. Below 1.0 the source latent is used and `width`/`height` are ignored. |

**What it cannot do**, verified across denoise 0.5 / 0.65 / 0.8 / 1.0:

- **Targeted removal.** "Remove the three people on the left, keep the man at the head
  of the table" either changed nothing (≤0.8, output 1.4% different from source) or
  regenerated the whole room (1.0). There is no setting in between.
- **Identity transfer between images.** `reference_2..4` chain extra `ReferenceLatent`
  conditioning — style and context, not identity. Every merge attempt returned the
  second image essentially unchanged regardless of denoise, step count, phrasing, or
  which slot each image was in.

## Regional edit — `sdxl-inpaint`

Masked. White in the mask is repainted; black is untouched and comes back bit-identical.
This is the only local tool that edits a *region*.

```bash
curl -X POST localhost:8189/api/generate \
  -F pipeline=sdxl-inpaint \
  -F 'prompt=empty office chairs beside a table, no people, natural window light' \
  -F model=cinematic -F steps=30 -F grow_mask_by=24 \
  -F image=@panel.png -F mask=@mask.png
```

- The prompt describes **what should be there afterwards**, not what to remove. To delete
  a person, prompt the empty background.
- `grow_mask_by` feathers the seam. At 6 a leftover arm survived at the mask edge; 24
  fixed it. Raise it before shrinking the mask.
- Mask generously. A mask that stops at the subject's outline leaves fragments.
- `model` picks the checkpoint, so match the panel — `anime` for anime panels,
  `cinematic` for photoreal.

## Identity in a new scene — character LoRA

Do not try to composite a character portrait into a background. Train the character
once and generate them directly into whatever scene is needed.

```bash
./scripts/train-lora --name <char> --images characters/<char>/images --base illustrious
```

Then pass `lora` and `lora_strength` on any `sdxl-*` call. `lora_strength: 1.15` is
locked — 0.85 lost hair colour and eye colour outright, not just fine detail.

## Why there is no single compositional editor here

The models that do targeted editing in one shot need far more VRAM than this machine
has: Qwen-Image-Edit is 20B, FLUX.1 Kontext 12B, FLUX.2-dev 32B, against 8 GB. FLUX.2
klein-4B is the largest that fits, and it is an instruction model, not a compositional
one. So the local answer is the right tool per operation, which this repo already has.

Reference output: `output/edit-guide/SHEET-editing.png` — one row per operation, source
and mask alongside the result.
