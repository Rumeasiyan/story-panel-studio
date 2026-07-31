# Installation report

- **Date:** 2026-08-01 (local time, Asia/Kolkata as configured on the workstation)
- **Project root:** `/home/sshroot/external/ai-video-gen`
- **Scope:** core setup. No model weights were downloaded.

---

## System

| Item | Value |
|---|---|
| Distribution | Fedora release 43 (Forty Three) |
| Kernel | 7.1.3-101.fc43.x86_64 |
| Session type | Wayland |
| Desktop | Hyprland |
| GPU | NVIDIA GeForce RTX 3050 8GB (GA107, `10de:2582`, MSI board) |
| NVIDIA driver | 580.173.02 |
| Driver CUDA support | 13.0 |
| VRAM | 8192 MiB total (7.65 GiB visible to PyTorch, 7837 MB reported by ComfyUI) |
| RAM | 31 GiB (32 GB) |
| Swap | 47 GiB |
| Free disk (`/home`) | 80 GB at completion (85 GB before setup) |
| Secure Boot | enabled — left untouched |

The NVIDIA driver was **not** modified. `nvidia-smi` worked before setup and reported
the RTX 3050, so per the project safety rules nothing about the driver, kernel,
Secure Boot, or Hyprland configuration was changed.

## Software

| Item | Value |
|---|---|
| Git | 2.55.0 |
| Python (system, selected) | 3.13.14 (`/usr/bin/python3.13`) |
| Python (`.venv`) | 3.13.14 |
| pip | 26.2 |
| PyTorch | 2.13.0+cu130 |
| PyTorch CUDA runtime | 13.0 |
| torchvision / torchaudio | 0.28.0+cu130 / 2.11.0+cu130 |
| FFmpeg | 7.1.5 |
| ComfyUI version | 0.29.0 |
| ComfyUI commit | `6cedd34343ba3214ca9591397bd106e02ef2acf6` |
| ComfyUI subject | `[Partner Nodes] fix(ByteDance): encode stereo reference audio without doubling its duration (#15177)` |
| Packages in `.venv` | 117 (see `requirements.lock.txt`) |

Python 3.13 was chosen over 3.12 and 3.14 following current ComfyUI guidance. Fedora's
system Python was not replaced and no package was installed with `sudo pip`.

PyTorch was installed from `https://download.pytorch.org/whl/cu130` — the stable
CUDA 13.0 wheel line matching the installed driver. No system CUDA Toolkit was
installed, and no nightly build was used.

## Validation

| Check | Result |
|---|---|
| `nvidia-smi` | **PASS** — RTX 3050, driver 580.173.02 |
| `torch.cuda.is_available()` | **PASS** — True |
| Compute capability | 8.6 |
| CUDA tensor operation (2048×2048 matmul) | **PASS** |
| `pip check` | **PASS** — no broken requirements |
| ComfyUI `main.py --help` | **PASS** |
| ComfyUI startup on `127.0.0.1:8188` | **PASS** — `GET /` returned 200 |
| `/system_stats` endpoint | **PASS** — reports ComfyUI 0.29.0, frontend 1.47.11 |
| GPU seen by ComfyUI | **PASS** — `Device: cuda:0 NVIDIA GeForce RTX 3050 : cudaMallocAsync`, DynamicVRAM enabled |
| Smoke-test server shutdown | **PASS** — stopped cleanly, no duplicate processes |
| `scripts/doctor.sh` | **PASS** — all critical checks, 2 WARN |
| Model profiles installed | **none** — pending approval |
| SDXL image generation | **PENDING** — no checkpoint installed |
| Wan 2.2 video generation | **PENDING** — no weights installed |

Doctor warnings (both expected, neither critical):

1. Free storage 80 GB — above the 25 GB minimum and enough for a practical image setup,
   but below the 100 GB recommended for both SDXL profiles *and* Wan 2.2 together.
2. No active model profile — nothing installed yet.

### Issue found and fixed during validation

The first smoke test started successfully but logged:

```text
[ERROR] Failed to initialize database ... (sqlite3.OperationalError) unable to open database file
```

Diagnosis: ComfyUI derives its default database path from its own package directory
(`engine/ComfyUI/user/comfyui.db`, see `comfy/cli_args.py:266`). `--user-directory` does
not override it, and that directory does not exist in this layout because user state is
kept in the project-root `user/`.

Fix: `scripts/comfy.sh` now passes
`--database-url sqlite:///<root>/user/comfyui.db` when the installed ComfyUI supports the
flag. Re-tested: no errors, `user/comfyui.db` created, `GET /` returned 200.

## Repository

### Files created

```text
CLAUDE.md                      README.md                   Makefile
bootstrap.sh                   .gitignore                  .gitattributes
.env.example                   requirements-project.txt    requirements.lock.txt
.githooks/pre-commit
.github/workflows/repository-safety.yml
config/runtime.env             config/extra_model_paths.yaml
config/model-profiles.yaml     config/custom-nodes.yaml
scripts/doctor.sh              scripts/comfy.sh            scripts/update.sh
scripts/snapshot.sh            scripts/repository-check.sh
scripts/modelctl               scripts/custom-nodectl
workflows/README.md
workflows/video/wan22/wan2.2_ti2v_5B_official.json
workflows/image/anime/sdxl_base_template.json
workflows/image/cinematic/sdxl_base_template.json
prompts/README.md + seed fragments (anime, cinematic, negative, templates)
characters/README.md           assets/README.md
reports/INSTALLATION_REPORT.md reports/BENCHMARKS.md
reports/MODEL_LICENSES.md      reports/ENVIRONMENT.md
```

Gitignored runtime directories created: `models/*` (12 subdirectories), `input/`,
`output/`, `temp/`, `cache/`, `logs/`, `user/`, `custom_nodes/`.

### Submodules

| Path | Repository | Pinned commit |
|---|---|---|
| `engine/ComfyUI` | https://github.com/Comfy-Org/ComfyUI.git | `6cedd34343ba3214ca9591397bd106e02ef2acf6` |

No custom-node submodules. `config/custom-nodes.yaml` is intentionally empty.

### Git hook status

`core.hooksPath` is set to `.githooks` **locally only** — the global Git configuration
was not modified. `.githooks/pre-commit` is executable and delegates to
`scripts/repository-check.sh --staged`, which rejects staged model weights, generated
media, secret-like files, files inside ignored data directories, and anything over
50 MB.

### Tracked-file safety scan

`./scripts/repository-check.sh --all` passes: no weights, renders, inputs, caches,
virtual environment files, or secrets are tracked.

### Workflow provenance

All three workflow JSON files were copied from the official ComfyUI built-in template
package `comfyui-workflow-templates` 0.11.23 (pinned by the ComfyUI commit above) on
2026-08-01. No workflow JSON was hand-authored. The Wan template references exactly the
three filenames the `wan22-ti2v-5b` profile installs.

### Initial commit

Local Git identity was already configured (`Rumeasiyan <srumeasiyan@gmail.com>`), so an
initial commit was created on branch `main`. No remote was added.

## Model profiles (registered, not downloaded)

| Profile | Artifacts | Download | Licence |
|---|---|---|---|
| `anime-sdxl` | Animagine XL 4.0 opt | 6.94 GB | CreativeML Open RAIL++-M |
| `cinematic-sdxl` | RealVisXL V4.0 | 6.94 GB | CreativeML Open RAIL++-M |
| `wan22-ti2v-5b` | TI2V-5B fp16 + VAE + UMT5-XXL fp8 | 18.14 GB | Apache-2.0 (via upstream Wan 2.2 card) |

All revisions are pinned to exact Hugging Face commit SHAs with recorded sizes and
SHA-256 hashes. Details in `config/model-profiles.yaml` and `reports/MODEL_LICENSES.md`.

## Outstanding actions

### Required before generating images

- Approve and install at least one profile:
  `./scripts/modelctl install anime-sdxl` (6.94 GB), then
  `./scripts/modelctl set anime-sdxl`.

### Large downloads awaiting approval

| Profile | Size | Notes |
|---|---|---|
| `anime-sdxl` | 6.94 GB | single file > 5 GB → approval prompt |
| `cinematic-sdxl` | 6.94 GB | single file > 5 GB → approval prompt |
| `wan22-ti2v-5b` | 18.14 GB | set > 10 GB and one file = 10.0 GB → approval prompt |
| **All three** | **32.02 GB** | leaves roughly 48 GB free on `/home` |

`modelctl install` additionally requires roughly 2.1× the download size free, because
files land in the Hugging Face cache before being copied into `models/`. For the Wan
profile that means about 38 GB of transient headroom.

### Optional

- Install `wget` and `aria2`: `sudo dnf install -y wget aria2`. These were the only two
  expected Fedora packages missing. Neither is required — `curl` is present and
  `modelctl` downloads through `huggingface_hub`, which resumes interrupted transfers.
  Automated installation was skipped because `sudo` required an interactive password.
- Free additional disk space if both SDXL profiles and Wan 2.2 will be installed at
  once (100 GB recommended; 80 GB currently free).
- After a good render, commit the workflow JSON.

### Unresolved issues

None. The database error described above was diagnosed and fixed, and re-tested clean.

### Explicitly not done (require separate approval)

- No NVIDIA driver, kernel, Secure Boot, or Hyprland changes.
- No custom nodes installed (IP-Adapter, ControlNet, face tools remain a later stage).
- No automatic startup service.
- No public network exposure; ComfyUI binds to `127.0.0.1:8188` only.
- No Git remote configured.
