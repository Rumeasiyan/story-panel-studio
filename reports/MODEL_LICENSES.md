# Model licences and sources

Every model and LoRA must be recorded here **before production use**. Do not claim
commercial permission unless the model card and licence support it.

Resolved from the Hugging Face API on **2026-08-01**. Revisions are pinned in
`config/model-profiles.yaml`.

## anime-sdxl

| Field | Value |
|---|---|
| Artifact | `animagine-xl-4.0-opt.safetensors` |
| Repository | [cagliostrolab/animagine-xl-4.0](https://huggingface.co/cagliostrolab/animagine-xl-4.0) |
| Pinned revision | `2b7c1b397761bf5bd3cc42e5b39ec99314a75a96` |
| Size | 6,938,350,040 B (6.94 GB) |
| SHA-256 | `6327eca98bfb6538dd7a4edce22484a1bbc57a8cff6b11d075d40da1afb847ac` |
| Licence | CreativeML Open RAIL++-M (`openrail++`) |
| Destination | `models/checkpoints/` |
| Commercial use | **Review required.** Open RAIL++-M permits commercial use but imposes use-based restrictions that must be passed downstream. Read the licence and the model card's own terms before publishing commercially. |

## cinematic-sdxl

| Field | Value |
|---|---|
| Artifact | `RealVisXL_V4.0.safetensors` |
| Repository | [SG161222/RealVisXL_V4.0](https://huggingface.co/SG161222/RealVisXL_V4.0) |
| Pinned revision | `26dfe44930964cd70d0a817b6d1cc945c130e38d` |
| Size | 6,938,040,706 B (6.94 GB) |
| SHA-256 | `912c9dc74f5855175c31a7993f863a043ac8dcc31732b324cd05d75cd7e16844` |
| Licence | CreativeML Open RAIL++-M (`openrail++`) |
| Destination | `models/checkpoints/` |
| Commercial use | **Review required.** Same Open RAIL++-M considerations as above; also check the author's model card for additional conditions. |

## wan22-ti2v-5b

All three artifacts come from
[Comfy-Org/Wan_2.2_ComfyUI_Repackaged](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged)
at pinned revision `fb1388adc906ab39ffc26ee40e96b22886b56bc4`.

The repackaged repository does not declare a licence in its metadata. The upstream
source model, [Wan-AI/Wan2.2-TI2V-5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B),
declares **Apache-2.0**, which is what is recorded here. Re-verify the upstream model
card before any commercial release.

| Artifact | Path in repo | Size | SHA-256 | Destination |
|---|---|---|---|---|
| `wan2.2_ti2v_5B_fp16.safetensors` | `split_files/diffusion_models/…` | 9,999,658,848 B (10.0 GB) | `456f901338bd9eadbded3828b819109a9b68e8a525ca5cf8d0049a69fcfeca1e` | `models/diffusion_models/` |
| `wan2.2_vae.safetensors` | `split_files/vae/…` | 1,409,400,960 B (1.41 GB) | `e40321bd36b9709991dae2530eb4ac303dd168276980d3e9bc4b6e2b75fed156` | `models/vae/` |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `split_files/text_encoders/…` | 6,735,906,897 B (6.74 GB) | `c3355d30191f1f066b26d93fba017ae9809dce6c627dda5f6a66eaa651204f68` | `models/text_encoders/` |

The UMT5-XXL text encoder derives from Google's UMT5 (Apache-2.0) as redistributed by
the Wan project. Recorded as Apache-2.0 via the upstream Wan 2.2 model card; verify
independently before commercial use.

## LoRAs and custom assets

None installed. When adding one, append a row with: filename, source URL, pinned
revision, size, SHA-256, licence, and whether commercial use is permitted. Private
character LoRAs go in `models/private/` (gitignored) and must never be committed.

## wan21-fun-inp-1.3b

Fast image-to-video drafting model. All files from
[Comfy-Org/Wan_2.1_ComfyUI_repackaged](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged)
at pinned revision `06e001fc51048fb03433a6fb25334de7836704a5`. Resolved 2026-08-01.

The repackaged repository declares no licence in its metadata. The upstream sources do:
[alibaba-pai/Wan2.1-Fun-1.3B-InP](https://huggingface.co/alibaba-pai/Wan2.1-Fun-1.3B-InP)
and [Wan-AI/Wan2.1-T2V-1.3B](https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B) are both
**Apache-2.0**, which is what is recorded here. Re-verify before commercial release.

| Artifact | Size | SHA-256 | Destination |
|---|---|---|---|
| `wan2.1_fun_inp_1.3B_bf16.safetensors` | 3,128,957,992 B (3.13 GB) | `8495d2b1673ffb18abb548a64ff3b0e4bd367734f653096f7a8a3ad46954d511` | `models/diffusion_models/` |
| `wan_2.1_vae.safetensors` | 253,815,318 B (0.25 GB) | `2fc39d31359a4b0a64f55876d8ff7fa8d780956ae2cb13463b0223e15148976b` | `models/vae/` |
| `clip_vision_h.safetensors` | 1,264,219,396 B (1.26 GB) | `64a7ef761bfccbadbaa3da77366aac4185a6c58fa5de5f589b42a65bcc21f161` | `models/clip_vision/` |

The umt5 text encoder is shared with `wan22-ti2v-5b` and is not downloaded twice.
