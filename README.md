# ai-video-gen

A local, reproducible AI image/video-generation workspace for an NVIDIA RTX 3050 (8 GB)
workstation running Fedora Linux and Hyprland.

**This repository is a recipe, not a warehouse.** It stores code, configuration,
workflows, prompts and pinned model manifests. Model weights, renders, inputs and
caches are never committed — they are redownloaded from pinned Hugging Face revisions.

Engine: [ComfyUI](https://github.com/Comfy-Org/ComfyUI), pinned as a Git submodule at
`engine/ComfyUI`.

---

## Quick start

```bash
cd ~/external/ai-video-gen
./bootstrap.sh --core-only
./scripts/doctor.sh
./scripts/comfy.sh image
```

Then open:

```text
http://127.0.0.1:8188
```

No model weights are downloaded by `bootstrap.sh`. Until a profile is installed, the
server starts but cannot generate images.

## Install a model profile

```bash
./scripts/modelctl list
./scripts/modelctl show anime-sdxl
./scripts/modelctl install anime-sdxl
./scripts/modelctl set anime-sdxl
./scripts/modelctl verify anime-sdxl          # size check
./scripts/modelctl verify anime-sdxl --hash   # full SHA-256, slow
```

| Profile | Purpose | Download |
|---|---|---|
| `anime-sdxl` | Anime/manhwa stills (Animagine XL 4.0 opt) | 6.94 GB |
| `cinematic-sdxl` | Realistic/cinematic stills (RealVisXL V4.0) | 6.94 GB |
| `wan22-ti2v-5b` | Wan 2.2 TI2V-5B video experiment | 18.14 GB |

`modelctl install` reports the total size, checks free space, and asks for approval
before any single file over 5 GB or any set over 10 GB. Downloads resume, land in
`models/` (never in the submodule), and are size-verified before being moved into place.

## Wan test

```bash
./scripts/modelctl install wan22-ti2v-5b
./scripts/comfy.sh wan
```

Open `workflows/video/wan22/wan2.2_ti2v_5B_official.json` and start at **512x288,
41 frames, batch 1, previews off**. Do not start at 720p on 8 GB. Record every run in
`reports/BENCHMARKS.md`.

Wan 2.2 on this card is an experiment relying on ComfyUI native offloading plus 32 GB
of system RAM. SDXL stills are the production priority.

## Rebuild on another Linux machine

```bash
git clone --recurse-submodules <repository-url>
cd ai-video-gen
./bootstrap.sh --core-only
./scripts/modelctl install <profile>
```

`bootstrap.sh` is idempotent. It verifies the root, initializes Git and the submodule,
installs missing Fedora packages, creates `.venv`, installs CUDA-enabled PyTorch,
regenerates `config/extra_model_paths.yaml` with the new absolute path, runs the doctor,
and performs a ComfyUI smoke test. It never touches the NVIDIA driver, Secure Boot,
kernels, or Hyprland configuration.

## Repository layout

```text
config/     runtime.env, extra_model_paths.yaml, model-profiles.yaml, custom-nodes.yaml
engine/     ComfyUI (pinned Git submodule)
custom_nodes/  pinned third-party node submodules (empty by default)
models/     shared weight store — gitignored
workflows/  committed ComfyUI JSON
prompts/    committed prompt library
characters/ committed character metadata (no weights, no large image sets)
scripts/    doctor, comfy, update, snapshot, repository-check, modelctl, custom-nodectl
reports/    installation report, benchmarks, model licences
input/ output/ temp/ cache/ logs/ user/   local runtime data — gitignored
```

`make help` lists every wrapper target.

## Git policy

Committed:

- scripts, configuration, `Makefile`, `bootstrap.sh`
- workflow JSON and the prompt library
- character metadata and small licensed assets
- reports (installation, benchmarks, licences)
- the ComfyUI submodule **pointer** (an exact commit)

Never committed:

- model weights, LoRAs, VAEs, text encoders (`models/`)
- renders and source media (`output/`, `input/`)
- `.venv`, caches, logs, ComfyUI user state
- secrets, tokens, `.env`

Enforcement: `.gitignore`, a repo-local `pre-commit` hook (`git config core.hooksPath
.githooks`, set by bootstrap — your global Git config is untouched), the manual
`./scripts/repository-check.sh --all`, and a GitHub Actions workflow that rejects
prohibited extensions and oversized files.

Public models are redownloaded from pinned Hugging Face revisions, so nothing is lost by
not committing them. Git LFS is **not** used for public weights. Private character LoRAs
should eventually live in a private model registry, not in Git. No third-party hosting
service offers unlimited free storage — do not plan around that.

## Model switching

`config/model-profiles.yaml` is a manifest: each profile lists artifacts with a
repository, a **pinned commit**, an exact filename, a destination, a size, a SHA-256 and
a licence. Adding a new checkpoint, a Wan version, a quantized variant or a LoRA pack
means appending an entry — not restructuring the repository.

`./scripts/modelctl set <profile>` writes `.active-model-profile` (local, gitignored).
It changes script defaults and download targets.

> **Limitation:** a ComfyUI workflow stores the exact model filename inside its loader
> node. Switching profiles does not rewrite existing workflows. After switching, open
> the workflow and reselect the checkpoint.

## Custom nodes

The core setup works with zero third-party nodes. `config/custom-nodes.yaml` starts
empty. Add nodes one at a time, each pinned to a full commit SHA:

```bash
./scripts/custom-nodectl list
./scripts/custom-nodectl install <id>
./scripts/custom-nodectl verify
```

`custom-nodectl` refuses unpinned entries, backs up `requirements.lock.txt`, and warns
before installing any dependency that would replace `torch`, `torchvision`,
`torchaudio`, `triton`, or `nvidia-*` packages. IP-Adapter, ControlNet helpers and face
tools are a later, explicitly approved stage.

## Updating

```bash
./scripts/update.sh --check   # show upstream commits without changing anything
./scripts/update.sh           # prompts before moving the pin
```

The pin never floats silently. After updating, the submodule pointer change is left
staged for your review and commit.

## Security

ComfyUI binds to `127.0.0.1:8188` only. `scripts/comfy.sh` refuses to start if
`COMFY_HOST` is anything other than a loopback address. Port 8188 is never exposed
publicly and no startup service is installed.

To reach it from another machine, use an SSH tunnel:

```bash
ssh -L 8188:127.0.0.1:8188 USER@FEDORA_PC_LAN_IP
```

then browse to `http://127.0.0.1:8188` on the client. Do not configure public access.

## Health check

```bash
./scripts/doctor.sh
```

Checks project root, Git state, submodule pin, `.venv`, Python version, pip, PyTorch and
its CUDA runtime, `torch.cuda.is_available()`, RTX 3050 detection, VRAM, a live CUDA
tensor operation, FFmpeg, free storage, YAML validity, model directories, the active
profile, accidentally tracked forbidden files, port 8188, and the ComfyUI startup
command. Exits non-zero on critical failures.

## Licences

Model licences and sources are recorded in `reports/MODEL_LICENSES.md`. Both SDXL
checkpoints are CreativeML Open RAIL++-M and require a licence review before commercial
use. Record the licence of every model and LoRA before production use.
