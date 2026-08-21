# Paste This Entire Prompt into Claude Code

You are Claude Code running interactively on my Fedora Linux workstation.

Do not merely explain how to perform this setup. Inspect the machine, create the project files, execute the safe installation steps, test the installation, and leave me with a reproducible Git repository.

The intended project root is fixed:

```text
~/external/story-panel-studio
```

I may have already run:

```bash
mkdir -p ~/external/story-panel-studio
cd ~/external/story-panel-studio
git init
claude
```

This prompt must work whether or not `git init` has already been run.

---

# 1. Mission

Build a local, reproducible AI image/video-generation workspace for an NVIDIA RTX 3050 workstation running Fedora Linux and Hyprland.

The workspace must support:

1. ComfyUI
2. SDXL anime/manhwa image generation
3. SDXL realistic/cinematic image generation
4. Wan 2.2 TI2V-5B experimentation
5. Image-to-video workflows
6. Future character-consistency tools such as IP-Adapter, ControlNet, and LoRAs
7. API-driven and batch generation later
8. Easy switching between model profiles without restructuring the repository
9. English and Tamil AI-story-video production later
10. Rebuilding the setup on another compatible Linux machine

Treat this Git repository as a **recipe and workflow store**, not a warehouse for model weights or generated media.

---

# 2. Execute, Do Not Only Advise

Work in phases and perform the work directly.

At the beginning:

1. Resolve the current working directory with `pwd -P`.
2. Confirm that the intended root is exactly:

   ```text
   $HOME/external/story-panel-studio
   ```

3. When running elsewhere, do not scatter project files into the wrong folder. Change to or create the intended root.
4. Initialize Git locally when `.git/` is absent.
5. Create the persistent `CLAUDE.md` described in this prompt before doing the larger installation.
6. Show a concise preflight summary before making system-level changes.
7. Continue automatically through safe, non-destructive user-level steps.
8. System package installation may invoke `sudo`; let the terminal request my password normally.
9. Ask for approval before:
   - modifying or replacing the NVIDIA driver
   - downloading any individual model file larger than 5 GB
   - downloading a set of models larger than 10 GB
   - enabling an automatic startup service
   - exposing ComfyUI beyond localhost
10. Do not repeatedly ask questions whose answer can be discovered from the machine.

Do not stop after writing a plan. Create the files, run the setup, and validate it.

---

# 3. Known Environment

Expected machine:

- Fedora Linux
- Hyprland on Wayland
- NVIDIA GeForce RTX 3050
- Approximately 8 GB VRAM
- Approximately 32 GB system RAM
- This is also a gaming computer
- NVIDIA may already be configured correctly

Do not change Hyprland configuration, HyprPM configuration, monitor configuration, gaming packages, Steam, Proton, kernels, bootloader settings, or desktop appearance unless a confirmed problem directly requires a change.

Do not reinstall Fedora or replace it with Ubuntu.

---

# 4. Non-Negotiable Safety Rules

Follow these rules throughout this task and persist them in `CLAUDE.md`.

1. Inspect before changing.
2. When `nvidia-smi` works and reports the RTX 3050, do not reinstall the NVIDIA driver.
3. Never use `sudo pip`.
4. Never install project packages into Fedora's system Python.
5. Use a project-local virtual environment at:

   ```text
   ~/external/story-panel-studio/.venv
   ```

6. Do not install the full system CUDA Toolkit merely because PyTorch needs CUDA. Prefer official CUDA-enabled PyTorch wheels.
7. Do not disable Secure Boot.
8. Do not remove kernels or NVIDIA packages.
9. Do not run destructive Git commands such as `git reset --hard`, `git clean -fdx`, or forced checkout without explicit approval.
10. Do not bind ComfyUI to `0.0.0.0` by default.
11. ComfyUI must listen only on:

    ```text
    127.0.0.1:8188
    ```

12. Do not expose port 8188 publicly.
13. Do not commit secrets, tokens, `.env`, model weights, source media, generated media, caches, logs, virtual environments, or user databases.
14. Do not use Git LFS for publicly available model weights.
15. Do not duplicate model files inside `engine/ComfyUI/models`.
16. Store model weights once under the project-root `models/` directory.
17. Make ComfyUI discover root-level models through `extra_model_paths.yaml`.
18. Keep ComfyUI itself pinned as a Git submodule.
19. Add third-party custom nodes one at a time and pin their Git commits.
20. Do not bulk-install unknown custom-node packs.
21. Back up an existing file before replacing it.
22. Keep installation scripts idempotent.
23. Record installed versions and validation results.
24. A failed phase must produce a diagnosis; do not make unrelated changes in response.
25. Never commit an asset whose licence does not allow the intended use.
26. Record the licence and source of every model and LoRA before production use.

---

# 5. Required Repository Architecture

Create and maintain this structure:

```text
~/external/story-panel-studio/
├── .git/
├── .githooks/
│   └── pre-commit
├── .github/
│   └── workflows/
│       └── repository-safety.yml
├── .gitignore
├── .gitattributes
├── .gitmodules
├── CLAUDE.md
├── README.md
├── Makefile
├── bootstrap.sh
├── requirements-project.txt
├── requirements.lock.txt
├── .env.example
├── config/
│   ├── runtime.env
│   ├── extra_model_paths.yaml
│   ├── model-profiles.yaml
│   └── custom-nodes.yaml
├── engine/
│   └── ComfyUI/                 # Git submodule
├── custom_nodes/                # future pinned node submodules
├── models/                      # fully gitignored
│   ├── checkpoints/
│   ├── diffusion_models/
│   ├── text_encoders/
│   ├── clip/
│   ├── clip_vision/
│   ├── vae/
│   ├── loras/
│   ├── controlnet/
│   ├── ipadapter/
│   ├── embeddings/
│   ├── upscale_models/
│   └── private/
├── workflows/                   # committed
│   ├── image/
│   │   ├── anime/
│   │   └── cinematic/
│   └── video/
│       └── wan22/
├── prompts/                     # committed
│   ├── anime/
│   ├── cinematic/
│   ├── negative/
│   └── templates/
├── characters/                  # committed metadata, not huge source sets
│   ├── bibles/
│   └── manifests/
├── assets/                      # only small, licensed, reusable assets
│   └── brand/
├── input/                       # gitignored
├── output/                      # gitignored
├── temp/                        # gitignored
├── cache/                       # gitignored
├── logs/                        # logs gitignored; reports may be committed
├── user/                        # ComfyUI local user state, gitignored
├── reports/
│   ├── INSTALLATION_REPORT.md
│   ├── BENCHMARKS.md
│   └── MODEL_LICENSES.md
└── scripts/
    ├── doctor.sh
    ├── comfy.sh
    ├── update.sh
    ├── snapshot.sh
    ├── repository-check.sh
    ├── modelctl
    └── custom-nodectl
```

Do not create placeholder binary media just to populate ignored directories.

---

# 6. Create `CLAUDE.md` First

Create a concise but complete `CLAUDE.md` at the project root before continuing.

It must persist these project rules:

## Project identity

- Project root: `~/external/story-panel-studio`
- Fedora + Hyprland
- RTX 3050, expected 8 GB VRAM
- Repository is a reproducible recipe, not a model/output warehouse
- Primary engine: ComfyUI
- ComfyUI location: `engine/ComfyUI`
- Python environment: `.venv`
- Shared models: root `models/`
- Model registry: `config/model-profiles.yaml`
- Local active profile state: `.active-model-profile`
- Generated content: `output/`
- ComfyUI user data: `user/`

## Persistent rules

- Never commit weights or renders
- Never use `sudo pip`
- Never modify a working NVIDIA installation without approval
- Never expose ComfyUI publicly
- Use external model paths instead of copying weights into the submodule
- Pin ComfyUI and custom nodes by Git commit
- Update deliberately, test after updating, and commit submodule pointer changes
- Ask before large downloads
- Store model licences in `reports/MODEL_LICENSES.md`
- Keep workflows and prompt libraries committed
- Run `./scripts/doctor.sh` after environment changes
- Run `./scripts/repository-check.sh` before commits
- Do not destroy local changes

## Standard commands

Document:

```bash
./bootstrap.sh
./scripts/doctor.sh
./scripts/comfy.sh image
./scripts/comfy.sh lowvram
./scripts/modelctl list
./scripts/modelctl status
./scripts/modelctl install <profile>
./scripts/modelctl set <profile>
./scripts/modelctl verify <profile>
./scripts/update.sh
```

Also note clearly:

> Selecting a model profile controls downloads and script defaults. A ComfyUI workflow still stores the exact model filename it loads; switching profiles does not magically rewrite every workflow.

---

# 7. Preflight Inspection

Before installing packages, run and summarize:

```bash
set -o pipefail

echo "=== Working directory ==="
pwd -P

echo "=== Fedora ==="
cat /etc/fedora-release 2>/dev/null || cat /etc/os-release

echo "=== Kernel ==="
uname -a

echo "=== Session ==="
printf 'XDG_SESSION_TYPE=%s\n' "${XDG_SESSION_TYPE:-unknown}"
printf 'XDG_CURRENT_DESKTOP=%s\n' "${XDG_CURRENT_DESKTOP:-unknown}"
printf 'HYPRLAND_INSTANCE_SIGNATURE=%s\n' "${HYPRLAND_INSTANCE_SIGNATURE:-not-set}"

echo "=== GPU ==="
lspci -nnk | grep -A4 -Ei 'VGA|3D|Display' || true
nvidia-smi || true

echo "=== NVIDIA packages ==="
rpm -qa | grep -Ei '(^|-)nvidia|akmod|kmod' | sort || true

echo "=== Python ==="
for cmd in python3.13 python3.12 python3; do
  if command -v "$cmd" >/dev/null 2>&1; then
    "$cmd" --version
    command -v "$cmd"
  fi
done

echo "=== Memory ==="
free -h

echo "=== Storage ==="
df -h "$HOME"
df -h "$HOME/external" 2>/dev/null || true

echo "=== Secure Boot ==="
mokutil --sb-state 2>/dev/null || true

echo "=== Git ==="
git --version || true
git status --short --branch 2>/dev/null || true
```

Report:

- Fedora release
- kernel
- Wayland/Hyprland status
- GPU model
- VRAM
- NVIDIA driver version
- whether `nvidia-smi` works
- Python options
- RAM
- free disk space
- Secure Boot state
- Git repository state

Recommend at least:

- 25 GB free for core ComfyUI plus one SDXL checkpoint
- 60 GB free for a practical image setup
- 100 GB or more when installing the SDXL profiles and Wan 2.2 assets together

Do not guess available storage.

---

# 8. NVIDIA Decision Gate

## When `nvidia-smi` works

Do not change the driver.

Continue to project setup.

## When `nvidia-smi` fails

Do not immediately reinstall anything.

Inspect:

```bash
lsmod | grep -E '^(nvidia|nouveau)' || true
rpm -qa | grep -Ei 'nvidia|akmod|kmod' | sort || true
journalctl -b -k \
  | grep -Ei 'nvidia|nouveau|secure boot|module verification|NVRM' \
  | tail -n 200 || true
mokutil --sb-state 2>/dev/null || true
```

Diagnose whether the problem is:

- missing RPM Fusion driver
- akmod not built for the current kernel
- module-signing/Secure Boot issue
- nouveau conflict
- driver/kernel mismatch
- GPU unavailable for another reason

Explain the diagnosis and request approval before a driver change.

Use current RPM Fusion guidance for the detected Fedora release rather than hard-coding an old Fedora release:

```text
https://rpmfusion.org/Howto/NVIDIA
```

Do not continue to PyTorch validation until `nvidia-smi` works.

---

# 9. Git Safety Setup

Create a strong `.gitignore`.

It must ignore at least:

```gitignore
# Secrets and local state
.env
.env.*
!.env.example
.active-model-profile
*.token
*.key
*.pem

# Python
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Models and ML weights
models/
engine/ComfyUI/models/
*.safetensors
*.ckpt
*.pt
*.pth
*.bin
*.onnx
*.gguf
*.engine

# Inputs, outputs, caches and local UI state
input/
output/
temp/
cache/
user/
logs/*.log
logs/*.txt

# Generated media
*.mp4
*.mov
*.mkv
*.webm
*.avi
*.wav
*.flac
*.mp3
*.aac

# Large source media and transient images
*.psd
*.xcf
*.blend
*.exr

# Editors and OS
.DS_Store
Thumbs.db
.idea/
.vscode/
```

Do not globally ignore all PNG, JPEG, JSON, YAML, or Markdown files. Small workflow previews, diagrams, logos, prompt assets, and configuration files may need to be committed intentionally.

Create `.gitattributes` with sensible LF normalization for:

- shell scripts
- Python
- YAML
- JSON
- Markdown
- environment examples

Create a committed `.githooks/pre-commit` and set this repository only:

```bash
git config core.hooksPath .githooks
```

The hook must reject:

- staged files larger than 50 MB
- model-weight extensions
- generated-video/audio extensions
- `.env` and obvious secret files
- anything under ignored model/output/input directories that was force-added

Do not modify my global Git configuration.

Create `scripts/repository-check.sh` to perform the same checks manually.

Create a lightweight GitHub Actions workflow that checks committed files for prohibited extensions and files above GitHub-safe size limits. It must not require secrets or execute GPU code.

---

# 10. Add ComfyUI as a Pinned Submodule

Use:

```text
engine/ComfyUI
```

When absent:

```bash
git submodule add https://github.com/Comfy-Org/ComfyUI.git engine/ComfyUI
git submodule update --init --recursive
```

When already present, inspect rather than overwrite.

Record:

```bash
git -C engine/ComfyUI rev-parse HEAD
git -C engine/ComfyUI log -1 --oneline
```

The root repository will pin the exact ComfyUI commit through the submodule pointer.

Do not clone a second ComfyUI copy elsewhere.

Do not store the virtual environment inside the submodule.

---

# 11. Operating-System Dependencies

Install only missing packages.

Use current Fedora package names and verify availability before installation.

Expected dependencies include:

```text
git
python3
python3-pip
python3-devel
gcc
gcc-c++
make
ffmpeg
curl
wget
aria2
pciutils
mokutil
```

Do not install Git LFS unless a future non-model use actually requires it.

Do not install Docker for this setup.

Do not install Conda unless the Fedora Python versions are genuinely unusable.

---

# 12. Python Selection

Preferred order:

1. Python 3.13
2. Python 3.12
3. Python 3.14 only when the above are unavailable

Current ComfyUI documentation recommends Python 3.13 and describes 3.12 as a good fallback. Python 3.14 may work but can have custom-node compatibility issues.

Do not replace Fedora's default Python.

Select an available interpreter and create:

```bash
pythonX.Y -m venv "$HOME/external/story-panel-studio/.venv"
```

Then:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

Verify that `python` and `pip` resolve inside the project `.venv`.

---

# 13. PyTorch and CUDA

Before installing PyTorch, check the current official ComfyUI system requirements and PyTorch selector.

Current official references:

```text
https://docs.comfy.org/installation/system_requirements
https://docs.comfy.org/installation/manual_install
https://pytorch.org/get-started/locally/
```

At the time this prompt was prepared, the official ComfyUI NVIDIA command was:

```bash
pip install torch torchvision torchaudio \
  --extra-index-url https://download.pytorch.org/whl/cu130
```

Verify that this remains current before executing it.

Install a stable CUDA-enabled build, not CPU-only PyTorch.

Do not install nightly PyTorch unless stable cannot support a required feature and the reason is documented.

Validate with:

```bash
python - <<'PY'
import sys
import torch

print("Python:", sys.version)
print("PyTorch:", torch.__version__)
print("PyTorch CUDA runtime:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())

if not torch.cuda.is_available():
    raise SystemExit("ERROR: PyTorch cannot access CUDA")

props = torch.cuda.get_device_properties(0)
print("GPU:", torch.cuda.get_device_name(0))
print("Compute capability:", f"{props.major}.{props.minor}")
print("VRAM GiB:", round(props.total_memory / 1024**3, 2))

x = torch.randn((2048, 2048), device="cuda")
y = x @ x
torch.cuda.synchronize()

print("CUDA tensor test: PASS")
print("Result:", tuple(y.shape))
PY
```

Do not proceed to model installation unless this passes.

When it fails:

- capture the exact output
- inspect the installed wheel
- compare driver support and PyTorch CUDA runtime
- do not randomly install CUDA packages

---

# 14. Install ComfyUI Requirements

With the root `.venv` active:

```bash
pip install -r engine/ComfyUI/requirements.txt
```

When the current ComfyUI commit has `manager_requirements.txt`, install it too:

```bash
if [[ -f engine/ComfyUI/manager_requirements.txt ]]; then
  pip install -r engine/ComfyUI/manager_requirements.txt
fi
```

Create `requirements-project.txt` containing only project-level utilities not already controlled by ComfyUI, such as:

```text
huggingface_hub[cli]
PyYAML
requests
rich
```

Install it.

After the successful setup:

```bash
pip check
pip freeze > requirements.lock.txt
```

Do not treat `requirements.lock.txt` as a blind replacement for ComfyUI's own requirements during updates. It is an environment snapshot.

---

# 15. External Model and Custom-Node Paths

Do not symlink or copy model weights into `engine/ComfyUI/models`.

Create:

```text
config/extra_model_paths.yaml
```

Use an absolute `base_path` resolved from the actual project root.

The configuration must expose root-level folders, including:

```yaml
ai_video_gen:
  base_path: /absolute/path/to/story-panel-studio
  checkpoints: models/checkpoints
  diffusion_models: models/diffusion_models
  text_encoders: models/text_encoders
  clip: models/clip
  clip_vision: models/clip_vision
  vae: models/vae
  loras: models/loras
  controlnet: models/controlnet
  embeddings: models/embeddings
  upscale_models: models/upscale_models
  custom_nodes: custom_nodes
```

Validate that the keys match those supported by the current ComfyUI `extra_model_paths.yaml.example`. Adjust to the current upstream format when necessary.

Pass this file explicitly at startup with:

```text
--extra-model-paths-config <project>/config/extra_model_paths.yaml
```

This keeps the ComfyUI submodule clean and allows future engines to share the same model store.

---

# 16. Runtime Configuration

Create `config/runtime.env` with non-secret defaults:

```bash
COMFY_HOST=127.0.0.1
COMFY_PORT=8188
COMFY_RESERVE_VRAM=1
COMFY_PREVIEW_METHOD=none
COMFY_DEFAULT_MODE=image
```

Create `.env.example` for optional local overrides, but do not create or commit actual secrets.

The launch scripts may load a local `.env` when present.

---

# 17. ComfyUI Launcher

Create `scripts/comfy.sh` with these modes:

```bash
./scripts/comfy.sh image
./scripts/comfy.sh lowvram
./scripts/comfy.sh wan
./scripts/comfy.sh help
```

It must:

1. Resolve the repository root from the script location.
2. Activate `.venv`.
3. verify the ComfyUI submodule exists
4. verify CUDA before launch
5. create runtime directories
6. pass:
   - `--listen 127.0.0.1`
   - `--port 8188`
   - project `user/`
   - project `input/`
   - project `output/`
   - project `temp/`
   - `config/extra_model_paths.yaml`
7. detect optional flags by checking:

   ```bash
   python engine/ComfyUI/main.py --help
   ```

8. only add `--enable-manager` if the current version supports it
9. never expose the server publicly

Suggested behavior:

## `image`

Use normal VRAM mode with approximately 1 GB reserved for Hyprland and the desktop.

## `lowvram`

Use:

- low-VRAM mode
- previews disabled
- reserved desktop VRAM

## `wan`

Use the most conservative supported settings:

- low-VRAM mode
- previews disabled
- reserved VRAM
- local-only server

Do not invent unsupported flags. Detect them from the installed ComfyUI commit.

---

# 18. Bootstrap Script

Create an idempotent root-level `bootstrap.sh`.

It must support:

```bash
./bootstrap.sh
./bootstrap.sh --core-only
./bootstrap.sh --skip-system-packages
./bootstrap.sh --repair
```

Core responsibilities:

1. verify project root
2. initialize Git when needed
3. create directories
4. configure local Git hooks
5. inspect system
6. install missing Fedora packages when allowed
7. add/update the ComfyUI submodule safely
8. create/reuse `.venv`
9. install correct CUDA-enabled PyTorch
10. install ComfyUI and project requirements
11. generate external model-path configuration
12. run `scripts/doctor.sh`
13. start a short ComfyUI smoke test or instruct me how to run it when an interactive server cannot remain running
14. write/update the installation report

Do not download large AI models during `--core-only`.

A normal `./bootstrap.sh` may prepare model manifests but must still request approval before large downloads.

---

# 19. Doctor Script

Create `scripts/doctor.sh`.

It must check and clearly mark PASS/WARN/FAIL for:

- correct project root
- Git repository
- ComfyUI submodule initialized
- ComfyUI pinned commit
- Python virtual environment
- Python version
- pip
- PyTorch version
- PyTorch CUDA runtime
- `torch.cuda.is_available()`
- RTX 3050 detection
- VRAM
- CUDA tensor operation
- FFmpeg
- free storage
- external-model-path YAML syntax
- expected model directories
- active model profile
- forbidden files accidentally tracked by Git
- port 8188 conflict
- ComfyUI startup command validity

It must exit non-zero on critical failures.

---

# 20. Model Profiles and Future Switching

Create:

```text
config/model-profiles.yaml
```

The model system must be manifest-driven so new models can be added later without redesigning the repository.

Each profile should include fields similar to:

```yaml
profiles:
  anime-sdxl:
    description: Anime/manhwa still-image generation
    engine: comfyui
    workflow_family: sdxl
    artifacts:
      - id: animagine-xl-4-opt
        repository: cagliostrolab/animagine-xl-4.0
        revision: PINNED_HF_COMMIT
        filename: animagine-xl-4.0-opt.safetensors
        destination: models/checkpoints
        licence: CreativeML Open RAIL++-M
        commercial_review_required: true

  cinematic-sdxl:
    description: Realistic/cinematic still-image generation
    engine: comfyui
    workflow_family: sdxl
    artifacts:
      - id: realvisxl-v4
        repository: SG161222/RealVisXL_V4.0
        revision: PINNED_HF_COMMIT
        filename: RESOLVE_EXACT_CURRENT_CHECKPOINT_FILENAME
        destination: models/checkpoints
        licence: RESOLVE_FROM_MODEL_CARD
        commercial_review_required: true

  wan22-ti2v-5b:
    description: Wan 2.2 text/image-to-video experiment for 8 GB VRAM via ComfyUI offloading
    engine: comfyui
    workflow_family: wan22-ti2v
    artifacts:
      - id: wan22-ti2v-5b
        repository: Comfy-Org/Wan_2.2_ComfyUI_Repackaged
        revision: PINNED_HF_COMMIT
        filename: split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors
        destination: models/diffusion_models
        licence: Apache-2.0
      - id: wan22-vae
        repository: Comfy-Org/Wan_2.2_ComfyUI_Repackaged
        revision: PINNED_HF_COMMIT
        filename: split_files/vae/wan2.2_vae.safetensors
        destination: models/vae
        licence: Apache-2.0
      - id: umt5-encoder
        repository: Comfy-Org/Wan_2.2_ComfyUI_Repackaged
        revision: PINNED_HF_COMMIT
        filename: split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
        destination: models/text_encoders
        licence: VERIFY_AND_RECORD
```

Before writing final resolved entries:

1. Query the current Hugging Face repository metadata.
2. Resolve exact filenames.
3. Pin a specific revision/commit rather than floating `main`.
4. Record model file sizes.
5. Record licence information.
6. Do not claim commercial permission unless the model card/licence supports it.
7. Add source links to `reports/MODEL_LICENSES.md`.

The profiles above are the initial registry, not a permanent restriction.

The design must allow future profiles such as:

- newer anime SDXL checkpoints
- newer cinematic checkpoints
- Wan 2.1
- later Wan versions
- quantized alternatives
- LoRA packs
- local/private character LoRAs
- API-only providers

Do not install or download future profiles until requested.

---

# 21. `modelctl` Command

Create an executable:

```text
scripts/modelctl
```

Python or Bash is acceptable; Python with PyYAML and Hugging Face Hub is preferred.

It must support:

```bash
./scripts/modelctl list
./scripts/modelctl show anime-sdxl
./scripts/modelctl status
./scripts/modelctl set anime-sdxl
./scripts/modelctl install anime-sdxl
./scripts/modelctl install cinematic-sdxl
./scripts/modelctl install wan22-ti2v-5b
./scripts/modelctl verify anime-sdxl
./scripts/modelctl verify wan22-ti2v-5b
./scripts/modelctl disk
```

Required behavior:

## `list`

Show profile name, purpose, installed state, expected download size, and licence.

## `show`

Show exact repositories, revisions, filenames, destinations, sizes, and licences.

## `set`

Write the selected profile to:

```text
.active-model-profile
```

This file is local and gitignored.

Also state clearly that ComfyUI workflows still choose model filenames inside loader nodes.

## `install`

- calculate the total download size first
- check free space
- show planned files
- ask approval for large downloads
- resume interrupted downloads
- download exact pinned revisions
- place files directly into the root `models/` destinations
- never download into the submodule
- never overwrite a valid existing file unnecessarily
- use temporary partial files safely
- verify expected file size
- record installation state

## `verify`

Verify files by repository metadata size and SHA-256 when practical. Do not hash all huge files on every normal launch; make full hashing an explicit verification operation.

## `status`

Show active profile, installed profiles, missing artifacts, disk consumption, and free space.

## `disk`

Show sizes for models, inputs, outputs, cache, logs, and total project usage.

---

# 22. Model Download Policy

Initial recommended model profiles:

1. `anime-sdxl`
2. `cinematic-sdxl`
3. `wan22-ti2v-5b`

Do not automatically download all three without a combined size report and approval.

For this 8 GB RTX 3050:

- SDXL still-image profiles are the production priority.
- Wan 2.2 TI2V-5B is an experiment and should use ComfyUI native offloading.
- Do not make full-resolution Wan rendering the foundation of a four-videos-per-day pipeline.
- Begin Wan tests at low resolution and short frame counts.
- Do not install 14B Wan models by default.

When I approve downloads, download the selected profiles using `modelctl`.

---

# 23. Initial Workflow Policy

Do not invent unverified or malformed ComfyUI JSON.

Create workflow directories and README files.

For official or available workflows:

1. Prefer current built-in ComfyUI templates.
2. Download the official Wan 2.2 TI2V-5B workflow JSON from the current ComfyUI documentation when available.
3. Save it under:

   ```text
   workflows/video/wan22/
   ```

4. Record its source and retrieval date.
5. Do not overwrite a user-edited workflow.
6. For SDXL, either copy a valid current built-in template or instruct me to open the template and save it into:
   - `workflows/image/anime/`
   - `workflows/image/cinematic/`

After a good render, workflow JSONs should be committed.

---

# 24. Wan 2.2 Validation

Use current official ComfyUI guidance.

The current official guide says the ComfyUI-repackaged Wan 2.2 TI2V-5B workflow can fit on 8 GB VRAM through native offloading.

Required files are expected to include:

```text
wan2.2_ti2v_5B_fp16.safetensors
wan2.2_vae.safetensors
umt5_xxl_fp8_e4m3fn_scaled.safetensors
```

Use the official ComfyUI-repackaged model repository and official workflow rather than installing the complete standalone Wan repository for the first test.

Safe first test:

```text
Mode: image-to-video
Width: 512
Height: 288
Frames: 41
Batch size: 1
Preview: disabled
```

Then, only when stable:

```text
Width: 640
Height: 360
Frames: 49
Batch size: 1
```

Do not start at 720p.

During the first benchmark, record:

- profile and exact model revisions
- prompt
- input image
- resolution
- frames
- steps
- sampler/scheduler
- seed
- wall-clock time
- peak VRAM
- peak RAM
- swap use
- output path
- observed artifacts

Append results to:

```text
reports/BENCHMARKS.md
```

---

# 25. Custom Nodes

Create:

```text
config/custom-nodes.yaml
```

Initially keep it empty except for schema and comments.

Create `scripts/custom-nodectl` supporting:

```bash
./scripts/custom-nodectl list
./scripts/custom-nodectl install <id>
./scripts/custom-nodectl verify
./scripts/custom-nodectl update <id>
```

Custom nodes must be added under root:

```text
custom_nodes/
```

Prefer adding each node as a Git submodule pinned to a commit.

Before installing:

- inspect maintenance status
- inspect licence
- inspect install instructions
- inspect Python dependency changes
- warn when it can replace PyTorch or CUDA packages
- back up `requirements.lock.txt`

Initial core setup must work without third-party nodes.

Do not install IP-Adapter, ControlNet helper packs, face tools, or node bundles during core setup unless I explicitly approve the next stage.

---

# 26. Update and Snapshot Scripts

Create `scripts/update.sh`.

It must:

1. require a clean or explicitly acknowledged root working tree
2. show current ComfyUI commit
3. fetch changes
4. show available upstream change
5. request approval before changing the pinned submodule
6. install updated requirements in `.venv`
7. run `pip check`
8. run `scripts/doctor.sh`
9. leave the root repository showing the submodule pointer change for review and commit

Never float silently to the latest ComfyUI commit.

Create `scripts/snapshot.sh` to record:

- Fedora release
- kernel
- NVIDIA driver
- GPU
- Python
- PyTorch
- CUDA runtime
- ComfyUI commit
- custom-node commits
- installed model profiles and revisions
- `pip freeze`
- disk usage

Write timestamped reports under `reports/` or `logs/`, with durable summaries kept in `reports/`.

---

# 27. Makefile

Create useful targets:

```makefile
help
bootstrap
doctor
run
run-lowvram
run-wan
models
model-status
repo-check
snapshot
update
```

Targets must call the scripts rather than duplicate complex logic.

---

# 28. README

Create a user-focused `README.md` containing:

## Quick start

```bash
cd ~/external/story-panel-studio
./bootstrap.sh --core-only
./scripts/doctor.sh
./scripts/comfy.sh image
```

Open:

```text
http://127.0.0.1:8188
```

## Install a model profile

```bash
./scripts/modelctl list
./scripts/modelctl show anime-sdxl
./scripts/modelctl install anime-sdxl
./scripts/modelctl set anime-sdxl
```

## Wan test

```bash
./scripts/modelctl install wan22-ti2v-5b
./scripts/comfy.sh wan
```

## Rebuild on another Linux machine

```bash
git clone --recurse-submodules <repository-url>
cd story-panel-studio
./bootstrap.sh --core-only
./scripts/modelctl install <profile>
```

## Git policy

Explain:

- code/configs/workflows/prompts are committed
- models/input/output are not
- public models are redownloaded from pinned Hugging Face revisions
- private LoRAs should eventually live in a private model registry, not in Git
- no claim should be made that a third-party hosting service offers unlimited free storage
- the repository is a recipe, not a warehouse

## Model switching

Explain the manifest/profile system and the limitation that workflow loader nodes retain exact filenames.

## Security

Explain local binding and secure SSH tunnelling from the Mac when needed:

```bash
ssh -L 8188:127.0.0.1:8188 USER@FEDORA_PC_LAN_IP
```

Do not configure public access.

---

# 29. Installation Report

Create/update:

```text
reports/INSTALLATION_REPORT.md
```

Include:

## System

- installation date and timezone
- Fedora version
- kernel
- session type
- GPU
- driver
- VRAM
- RAM
- free disk
- Secure Boot

## Software

- Git
- Python
- pip
- PyTorch
- PyTorch CUDA runtime
- FFmpeg
- ComfyUI commit

## Validation

- `nvidia-smi`
- CUDA availability
- CUDA tensor operation
- ComfyUI import/startup
- local HTTP response
- model profiles installed
- SDXL test status
- Wan test status

## Repository

- files created
- submodules
- Git hook status
- tracked-file safety scan
- initial commit status

## Outstanding actions

Separate:

- required
- optional
- large downloads awaiting approval
- unresolved issues

---

# 30. Smoke Test

After core installation:

1. Run `scripts/doctor.sh`.
2. Start ComfyUI locally.
3. Capture logs under `logs/`.
4. Wait for the server to become reachable.
5. Test:

   ```bash
   curl -fsS http://127.0.0.1:8188/ >/dev/null
   ```

6. Stop the smoke-test server cleanly if it was launched in the background.
7. Do not leave duplicate ComfyUI processes.

When no checkpoint is installed yet, server startup is still a valid core smoke test. Clearly mark image generation as pending.

---

# 31. Initial Git Commit

After core files pass the repository safety check:

1. Show `git status`.
2. Run the pre-commit checks.
3. Do not commit models or generated files.
4. If local Git user name and email are already configured, create an initial commit with an appropriate message.
5. If identity is not configured, do not modify global Git identity. Leave the changes ready and show me the exact local-only commands I may use.

Do not add a GitHub remote unless I explicitly provide one.

---

# 32. Definition of Done

Core setup is complete when:

1. Project root is `~/external/story-panel-studio`.
2. `CLAUDE.md` exists.
3. Repository safety rules exist and work.
4. ComfyUI is a pinned submodule.
5. `.venv` exists outside the submodule.
6. CUDA-enabled PyTorch detects the RTX 3050.
7. A CUDA tensor operation passes.
8. Root-level shared model directories exist.
9. ComfyUI uses the external-model-path configuration.
10. ComfyUI starts at `127.0.0.1:8188`.
11. `bootstrap.sh`, `doctor.sh`, `comfy.sh`, `modelctl`, and update tools exist.
12. Model profiles support later switching and additions.
13. No weights, renders, inputs, secrets, caches, or virtual environments are tracked.
14. The installation report is complete.
15. The repository passes its safety checks.
16. Any large model download still requiring approval is clearly presented as the next action.

---

# 33. Begin Now

Start by:

1. verifying or entering `~/external/story-panel-studio`
2. initializing Git if needed
3. creating `CLAUDE.md`
4. performing the preflight inspection
5. showing the concise inspection summary
6. continuing with the safe core setup

Do not install large model files until you have shown their individual and combined sizes and received approval.

Do not only return a guide. Execute the setup.
