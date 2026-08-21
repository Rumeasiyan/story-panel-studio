#!/usr/bin/env bash
# Idempotent setup for story-panel-studio. Safe to re-run.
#
#   ./bootstrap.sh                      # full core setup (no large model downloads)
#   ./bootstrap.sh --core-only          # identical, but never prepares model manifests
#   ./bootstrap.sh --skip-system-packages
#   ./bootstrap.sh --repair             # regenerate configs/dirs, reinstall requirements
#   ./bootstrap.sh --help
#
# This script NEVER downloads model weights. Use ./scripts/modelctl install <profile>.
# It never touches the NVIDIA driver, Secure Boot, kernels, or Hyprland configuration.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT"

EXPECTED_ROOT="$HOME/external/story-panel-studio"
COMFY_REPO="https://github.com/Comfy-Org/ComfyUI.git"

CORE_ONLY=0
SKIP_SYSTEM=0
REPAIR=0

BLD=$'\033[1m'; GRN=$'\033[0;32m'; YEL=$'\033[0;33m'; RED=$'\033[0;31m'; NC=$'\033[0m'
[[ -t 1 ]] || { BLD=""; GRN=""; YEL=""; RED=""; NC=""; }

step() { printf '\n%s==> %s%s\n' "$BLD" "$1" "$NC"; }
info() { printf '    %s\n' "$1"; }
ok()   { printf '    %s%s%s\n' "$GRN" "$1" "$NC"; }
warn() { printf '    %s%s%s\n' "$YEL" "$1" "$NC"; }
die()  { printf '%sERROR: %s%s\n' "$RED" "$1" "$NC" >&2; exit 1; }

usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

for arg in "$@"; do
  case "$arg" in
    --core-only)           CORE_ONLY=1 ;;
    --skip-system-packages) SKIP_SYSTEM=1 ;;
    --repair)              REPAIR=1 ;;
    -h|--help)             usage ;;
    *) die "unknown option '$arg' (see --help)" ;;
  esac
done

backup() {
  # Back up an existing file before replacing it (CLAUDE.md rule 16).
  [[ -f "$1" ]] || return 0
  local stamp; stamp="$(date +%Y%m%d-%H%M%S)"
  cp -p "$1" "$1.bak.$stamp"
  info "backed up $1 -> $1.bak.$stamp"
}

# ------------------------------------------------------------- 1. project root
step "Verifying project root"
info "root: $ROOT"
if [[ "$ROOT" != "$EXPECTED_ROOT" ]]; then
  warn "expected $EXPECTED_ROOT; continuing with $ROOT"
fi

# ------------------------------------------------------------------- 2. git
step "Git repository"
if [[ -d .git ]]; then
  ok "already a git repository (branch $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '-'))"
else
  git init -q
  ok "git init"
fi

git config core.hooksPath .githooks
[[ -f .githooks/pre-commit ]] && chmod +x .githooks/pre-commit
ok "local core.hooksPath = .githooks (global git config untouched)"

# ------------------------------------------------------------ 3. directories
step "Creating directory structure"
mkdir -p \
  .githooks .github/workflows config engine custom_nodes \
  models/{checkpoints,diffusion_models,text_encoders,clip,clip_vision,vae,loras,controlnet,ipadapter,embeddings,upscale_models,private} \
  workflows/image/{anime,cinematic} workflows/video/wan22 \
  prompts/{anime,cinematic,negative,templates} \
  characters/{bibles,manifests} assets/brand \
  input output temp cache logs user reports scripts
ok "directories present"

# -------------------------------------------------------- 4. system packages
step "System packages"
if (( SKIP_SYSTEM )); then
  warn "skipped (--skip-system-packages)"
else
  REQUIRED=(git python3 python3-pip python3-devel gcc gcc-c++ make ffmpeg curl wget aria2 pciutils mokutil)
  MISSING=()
  for pkg in "${REQUIRED[@]}"; do
    rpm -q "$pkg" >/dev/null 2>&1 || MISSING+=("$pkg")
  done
  if [[ ${#MISSING[@]} -eq 0 ]]; then
    ok "all expected packages present"
  else
    info "missing: ${MISSING[*]}"
    AVAILABLE=()
    for pkg in "${MISSING[@]}"; do
      if dnf -q info "$pkg" >/dev/null 2>&1; then AVAILABLE+=("$pkg"); else warn "no such package: $pkg"; fi
    done
    if [[ ${#AVAILABLE[@]} -gt 0 ]]; then
      info "running: sudo dnf install -y ${AVAILABLE[*]}"
      if sudo dnf install -y "${AVAILABLE[@]}"; then
        ok "installed ${AVAILABLE[*]}"
      else
        warn "package installation failed or was declined; continuing"
        warn "install manually: sudo dnf install -y ${AVAILABLE[*]}"
      fi
    fi
  fi
fi

# ------------------------------------------------------------ 5. NVIDIA gate
step "NVIDIA check"
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  ok "$(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | head -1)"
  info "driver is working; not modifying it"
else
  cat >&2 <<'EOF'
    nvidia-smi is not working. This script will NOT change the driver.
    Diagnose first:
      lsmod | grep -E '^(nvidia|nouveau)'
      rpm -qa | grep -Ei 'nvidia|akmod|kmod' | sort
      journalctl -b -k | grep -Ei 'nvidia|nouveau|secure boot|NVRM' | tail -n 200
      mokutil --sb-state
    Then follow current guidance at https://rpmfusion.org/Howto/NVIDIA
EOF
  die "cannot continue to PyTorch validation without a working NVIDIA driver"
fi

# ---------------------------------------------------------- 6. ComfyUI module
step "ComfyUI submodule"
if [[ -f engine/ComfyUI/main.py ]]; then
  ok "present at pinned commit $(git -C engine/ComfyUI rev-parse --short HEAD 2>/dev/null || echo unknown)"
elif [[ -e engine/ComfyUI ]]; then
  info "engine/ComfyUI exists but is not initialized; initializing"
  git submodule update --init --recursive
  ok "initialized at $(git -C engine/ComfyUI rev-parse --short HEAD)"
else
  info "adding submodule from $COMFY_REPO"
  git submodule add "$COMFY_REPO" engine/ComfyUI
  git submodule update --init --recursive
  ok "added at $(git -C engine/ComfyUI rev-parse --short HEAD)"
fi
git -C engine/ComfyUI log -1 --oneline | sed 's/^/    /'

# --------------------------------------------------------- 7. virtualenv
step "Python virtual environment"
if [[ -x .venv/bin/python ]] && (( ! REPAIR )); then
  ok "reusing .venv ($(.venv/bin/python --version 2>&1))"
else
  if [[ -x .venv/bin/python ]]; then
    info "--repair: reusing existing .venv, reinstalling requirements"
  else
    PYBIN=""
    for cand in python3.13 python3.12 python3.14; do
      command -v "$cand" >/dev/null 2>&1 && { PYBIN="$cand"; break; }
    done
    [[ -n "$PYBIN" ]] || die "no suitable Python found (need 3.13, 3.12, or 3.14)"
    [[ "$PYBIN" == "python3.14" ]] && warn "using Python 3.14; some custom nodes may not support it"
    info "creating .venv with $PYBIN"
    "$PYBIN" -m venv .venv
    ok "created .venv ($(.venv/bin/python --version 2>&1))"
  fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate
[[ "$(command -v python)" == "$ROOT/.venv/bin/python" ]] || die "python did not resolve inside .venv"
[[ "$(command -v pip)"    == "$ROOT/.venv/bin/pip"    ]] || die "pip did not resolve inside .venv"
python -m pip install --upgrade --quiet pip setuptools wheel
ok "pip $(pip --version | awk '{print $2}') inside $(command -v python)"

# ------------------------------------------------------------- 8. PyTorch
step "PyTorch (CUDA-enabled)"
TORCH_INDEX="https://download.pytorch.org/whl/cu130"
if python -c 'import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)' 2>/dev/null; then
  ok "already installed: $(python -c 'import torch;print(torch.__version__)') (CUDA $(python -c 'import torch;print(torch.version.cuda)'))"
else
  info "installing torch/torchvision/torchaudio from $TORCH_INDEX"
  info "(driver reports CUDA $(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1) capable; using stable cu130 wheels)"
  pip install torch torchvision torchaudio --index-url "$TORCH_INDEX"
fi

step "Validating CUDA"
python - <<'PY'
import sys
import torch

print("    Python:", sys.version.split()[0])
print("    PyTorch:", torch.__version__)
print("    PyTorch CUDA runtime:", torch.version.cuda)
print("    CUDA available:", torch.cuda.is_available())

if not torch.cuda.is_available():
    raise SystemExit("ERROR: PyTorch cannot access CUDA")

props = torch.cuda.get_device_properties(0)
print("    GPU:", torch.cuda.get_device_name(0))
print("    Compute capability:", f"{props.major}.{props.minor}")
print("    VRAM GiB:", round(props.total_memory / 1024**3, 2))

x = torch.randn((2048, 2048), device="cuda")
y = x @ x
torch.cuda.synchronize()
print("    CUDA tensor test: PASS", tuple(y.shape))
PY
ok "CUDA validated"

# -------------------------------------------------------- 9. requirements
step "ComfyUI and project requirements"
pip install -q -r engine/ComfyUI/requirements.txt
ok "engine/ComfyUI/requirements.txt"
if [[ -f engine/ComfyUI/manager_requirements.txt ]]; then
  pip install -q -r engine/ComfyUI/manager_requirements.txt
  ok "engine/ComfyUI/manager_requirements.txt"
fi
pip install -q -r requirements-project.txt
ok "requirements-project.txt"

if pip check; then
  ok "pip check clean"
else
  warn "pip check reported issues (see above)"
fi

backup requirements.lock.txt
pip freeze > requirements.lock.txt
ok "requirements.lock.txt updated ($(wc -l < requirements.lock.txt) packages)"

# ------------------------------------------------- 10. external model paths
step "External model paths"
NEEDS_WRITE=1
if [[ -f config/extra_model_paths.yaml ]]; then
  CURRENT_BASE="$(python -c "
import yaml
d = yaml.safe_load(open('config/extra_model_paths.yaml')) or {}
print((d.get('ai_video_gen') or {}).get('base_path', ''))
" 2>/dev/null || true)"
  if [[ "$CURRENT_BASE" == "$ROOT" ]] && (( ! REPAIR )); then
    NEEDS_WRITE=0
    ok "config/extra_model_paths.yaml already correct (base_path=$ROOT)"
  else
    backup config/extra_model_paths.yaml
  fi
fi

if (( NEEDS_WRITE )); then
  cat > config/extra_model_paths.yaml <<EOF
# External model paths for story-panel-studio.
#
# Weights live ONCE under the project-root models/ directory. Nothing is copied or
# symlinked into engine/ComfyUI/models, so the submodule stays clean and other engines
# can share the same store.
#
# Passed explicitly at startup by scripts/comfy.sh:
#   --extra-model-paths-config config/extra_model_paths.yaml
#
# Key names follow engine/ComfyUI/extra_model_paths.yaml.example. Regenerate this file
# with ./bootstrap.sh --repair if the project is moved to a different absolute path.

ai_video_gen:
  base_path: $ROOT
  is_default: true

  checkpoints: models/checkpoints/
  diffusion_models: models/diffusion_models/
  text_encoders: |
    models/text_encoders/
    models/clip/
  clip_vision: models/clip_vision/
  vae: models/vae/
  loras: models/loras/
  controlnet: models/controlnet/
  embeddings: models/embeddings/
  upscale_models: models/upscale_models/
  style_models: models/style_models/
  # Folder name expected by IP-Adapter custom nodes (added later, one at a time).
  ipadapter: models/ipadapter/
  custom_nodes: custom_nodes/
EOF
  ok "wrote config/extra_model_paths.yaml (base_path=$ROOT)"
fi

python -c "import yaml; yaml.safe_load(open('config/extra_model_paths.yaml'))" \
  || die "config/extra_model_paths.yaml is not valid YAML"

# --------------------------------------------------------- 11. permissions
step "Script permissions"
chmod +x bootstrap.sh scripts/*.sh scripts/modelctl scripts/custom-nodectl .githooks/pre-commit 2>/dev/null || true
ok "scripts executable"

# -------------------------------------------------------------- 12. doctor
step "Running doctor"
set +e
./scripts/doctor.sh
DOCTOR_RC=$?
set -e
(( DOCTOR_RC == 0 )) || die "doctor reported critical failures; fix them before continuing"

# --------------------------------------------------------- 13. smoke test
step "ComfyUI smoke test"
mkdir -p logs
LOG="logs/smoke-$(date +%Y%m%d-%H%M%S).log"
info "starting ComfyUI on 127.0.0.1:8188 (log: $LOG)"

./scripts/comfy.sh image > "$LOG" 2>&1 &
SMOKE_PID=$!
SMOKE_OK=0
for _ in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:8188/" >/dev/null 2>&1; then SMOKE_OK=1; break; fi
  kill -0 "$SMOKE_PID" 2>/dev/null || break
  sleep 1
done

if (( SMOKE_OK )); then
  ok "ComfyUI responded on http://127.0.0.1:8188/"
else
  warn "ComfyUI did not respond within 90s; see $LOG"
fi

# Stop the smoke-test server and its children cleanly; leave no duplicates.
if kill -0 "$SMOKE_PID" 2>/dev/null; then
  pkill -TERM -P "$SMOKE_PID" 2>/dev/null || true
  kill -TERM "$SMOKE_PID" 2>/dev/null || true
  for _ in $(seq 1 15); do kill -0 "$SMOKE_PID" 2>/dev/null || break; sleep 1; done
  kill -0 "$SMOKE_PID" 2>/dev/null && kill -KILL "$SMOKE_PID" 2>/dev/null || true
fi
wait "$SMOKE_PID" 2>/dev/null || true
ok "smoke-test server stopped"

(( SMOKE_OK )) || warn "smoke test inconclusive; start manually with ./scripts/comfy.sh image"

# ------------------------------------------------------------ 14. reporting
step "Model profiles"
if (( CORE_ONLY )); then
  info "--core-only: skipping model manifest summary"
else
  ./scripts/modelctl list || warn "modelctl list failed"
  warn "no weights were downloaded. Approve and run: ./scripts/modelctl install <profile>"
fi

step "Snapshot"
./scripts/snapshot.sh >/dev/null 2>&1 && ok "environment snapshot written under reports/" \
  || warn "snapshot.sh failed"

cat <<EOF

${GRN}${BLD}Bootstrap complete.${NC}

Next steps:
  ./scripts/doctor.sh
  ./scripts/comfy.sh image          then open http://127.0.0.1:8188
  ./scripts/modelctl list
  ./scripts/modelctl install anime-sdxl   # requires approval, ~6.94 GB

No model weights were downloaded by this script.
EOF
