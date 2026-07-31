# Workflows

Committed ComfyUI workflow JSON. Weights are not committed; workflows only reference
model **filenames**, which ComfyUI resolves through `config/extra_model_paths.yaml`
against the project-root `models/` store.

```text
workflows/
├── image/
│   ├── anime/       # anime/manhwa SDXL
│   └── cinematic/   # realistic/cinematic SDXL
└── video/
    └── wan22/       # Wan 2.2 TI2V-5B
```

## Provenance

| File | Source | Retrieved |
|---|---|---|
| `video/wan22/wan2.2_ti2v_5B_official.json` | Official ComfyUI built-in template `video_wan2_2_5B_ti2v` (`comfyui-workflow-templates` 0.11.23, pinned by `engine/ComfyUI/requirements.txt`) | 2026-08-01 |
| `image/anime/sdxl_base_template.json` | Official ComfyUI built-in template `sdxl_simple_example` (same package) | 2026-08-01 |
| `image/cinematic/sdxl_base_template.json` | Official ComfyUI built-in template `sdxl_simple_example` (same package) | 2026-08-01 |

No workflow JSON in this repository was hand-authored or invented.

## Rules

- Do not overwrite a workflow you have edited. Save variants under a new filename.
- A workflow stores the **exact** checkpoint filename in its loader node. Switching the
  active model profile does not rewrite workflows — reselect the checkpoint by hand.
- Commit a workflow once it has produced a good render, and note the profile it needs.

## Using them

1. Install the matching model profile:
   `./scripts/modelctl install anime-sdxl`
2. Start ComfyUI: `./scripts/comfy.sh image` (or `wan` for Wan 2.2).
3. Open <http://127.0.0.1:8188>, use **Workflow → Open** and pick the JSON.
4. Fix any red loader node by selecting the checkpoint you actually installed.

### SDXL templates

`sdxl_base_template.json` is the stock base+refiner example. The installed profiles
ship a single all-in-one checkpoint, so on first open:

- set the base loader to `animagine-xl-4.0-opt.safetensors` (anime) or
  `RealVisXL_V4.0.safetensors` (cinematic);
- either delete the refiner branch or point it at the same checkpoint.

### Wan 2.2 TI2V-5B

The official template already references exactly the three files installed by the
`wan22-ti2v-5b` profile:

```text
wan2.2_ti2v_5B_fp16.safetensors        -> models/diffusion_models/
wan2.2_vae.safetensors                 -> models/vae/
umt5_xxl_fp8_e4m3fn_scaled.safetensors -> models/text_encoders/
```

On 8 GB VRAM, launch with `./scripts/comfy.sh wan` and start at **512x288, 41 frames,
batch 1, previews off**. Do not start at 720p. Record results in
`reports/BENCHMARKS.md`.
