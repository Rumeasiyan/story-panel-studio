# Editing images

**Pick the tool by the shape of the change, not by which model looks best.** Every
option here was tested; the failures below are recorded so they are not retried.

| You want to | Use | Preserves |
|---|---|---|
| Change a property everywhere — wardrobe, weather, time of day, palette | `flux2-edit` | composition, roughly |
| Change one **region** — remove, add or replace something | `sdxl-inpaint` + mask | everything outside the mask, **pixel-exact** |
| Put a known character in a new scene | `sdxl-text-to-image` + character LoRA | the character's identity |
| Put **specific people from photos** into a new scene, pose or interaction, no mask | `qwen-image-edit` | the subjects' faces |

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

## Compositional editing — `qwen-image-edit`

Takes up to three reference images and composes their subjects into a new scene without
a mask. This is the one that can do "the man from image 1 and the woman from image 2
embracing on a beach, both faces intact".

```bash
curl -X POST localhost:8189/api/generate \
  -F pipeline=qwen-image-edit \
  -F 'prompt=the man from image 1 and the woman from image 2 embracing on a beach at sunset, keep both faces exactly' \
  -F image=@person_a.png -F reference_2=@person_b.png
```

**It is slow.** 20B on an 8 GB card, run as a GGUF quant streamed from system RAM —
minutes per image, not seconds. It is a hero-shot tool. Panels stay on the locked SDXL
and FLUX.2 paths.

Needs the pinned `comfyui-gguf` node and the `qwen-image-edit-2511` profile
(~19.6 GB). Apache-2.0, which is why it is viable at all: FLUX.2-dev (32B) and
HunyuanImage-3.0 (80B) are both larger *and* non-commercial.

## Why the other big editors are not here

FLUX.1 Kontext is 12B and FLUX.2-dev 32B against 8 GB of VRAM, and both are
non-commercial. Qwen-Image-Edit is the only one of that class that both quantises down
to something this machine can stream and carries a licence that suits monetized
channels.

Reference output: `output/edit-guide/SHEET-editing.png` — one row per operation, source
and mask alongside the result.
