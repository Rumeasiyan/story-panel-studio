#!/usr/bin/env bash
# Health check for story-panel-studio. Exits non-zero when a critical check FAILs.
#
#   ./scripts/doctor.sh

set -uo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

EXPECTED_ROOT="$HOME/external/story-panel-studio"

RED=$'\033[0;31m'; YEL=$'\033[0;33m'; GRN=$'\033[0;32m'; BLD=$'\033[1m'; NC=$'\033[0m'
[[ -t 1 ]] || { RED=""; YEL=""; GRN=""; BLD=""; NC=""; }

FAILURES=0
WARNINGS=0

pass() { printf '  %sPASS%s %-34s %s\n' "$GRN" "$NC" "$1" "${2:-}"; }
warn() { printf '  %sWARN%s %-34s %s\n' "$YEL" "$NC" "$1" "${2:-}"; WARNINGS=$((WARNINGS+1)); }
fail() { printf '  %sFAIL%s %-34s %s\n' "$RED" "$NC" "$1" "${2:-}"; FAILURES=$((FAILURES+1)); }
section() { printf '\n%s%s%s\n' "$BLD" "$1" "$NC"; }

# ------------------------------------------------------------------ repository
section "Repository"

if [[ "$ROOT" == "$EXPECTED_ROOT" ]]; then
  pass "project root" "$ROOT"
else
  warn "project root" "$ROOT (expected $EXPECTED_ROOT)"
fi

if git rev-parse --git-dir >/dev/null 2>&1; then
  pass "git repository" "branch $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '-')"
else
  fail "git repository" "not a git repository"
fi

if [[ "$(git config --local --get core.hooksPath 2>/dev/null)" == ".githooks" ]]; then
  pass "git hooks path" ".githooks"
else
  warn "git hooks path" "run: git config core.hooksPath .githooks"
fi

if [[ -x .githooks/pre-commit ]]; then
  pass "pre-commit hook" "executable"
else
  warn "pre-commit hook" "missing or not executable"
fi

if [[ -f engine/ComfyUI/main.py ]]; then
  pass "ComfyUI submodule" "initialized"
  COMFY_COMMIT="$(git -C engine/ComfyUI rev-parse HEAD 2>/dev/null || echo unknown)"
  pass "ComfyUI pinned commit" "$COMFY_COMMIT"
else
  fail "ComfyUI submodule" "run: git submodule update --init --recursive"
fi

if bash scripts/repository-check.sh --tracked >/dev/null 2>&1; then
  pass "tracked-file safety scan" "no prohibited files tracked"
else
  fail "tracked-file safety scan" "run: ./scripts/repository-check.sh --tracked"
fi

# ---------------------------------------------------------------- environment
section "Python environment"

if [[ -x .venv/bin/python ]]; then
  pass "virtual environment" ".venv"
else
  fail "virtual environment" "missing; run ./bootstrap.sh --core-only"
fi

if [[ -x .venv/bin/python ]]; then
  PYVER="$(.venv/bin/python -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])' 2>/dev/null)"
  PYMINOR="$(.venv/bin/python -c 'import sys;print(sys.version_info[1])' 2>/dev/null)"
  case "$PYMINOR" in
    13|12) pass "python version" "$PYVER" ;;
    14)    warn "python version" "$PYVER (custom nodes may not support 3.14)" ;;
    *)     warn "python version" "$PYVER (expected 3.13 or 3.12)" ;;
  esac

  if .venv/bin/python -m pip --version >/dev/null 2>&1; then
    pass "pip" "$(.venv/bin/python -m pip --version 2>/dev/null | awk '{print $2}')"
  else
    fail "pip" "not usable inside .venv"
  fi

  if [[ -d .venv/lib*/python*/site-packages ]] || true; then :; fi
fi

# ---------------------------------------------------------------------- torch
section "GPU and PyTorch"

if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  pass "nvidia-smi" "$(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1)"
else
  fail "nvidia-smi" "NVIDIA driver not usable"
fi

if [[ -x .venv/bin/python ]]; then
  TORCH_OUT="$(.venv/bin/python - <<'PY' 2>&1
import json
report = {}
try:
    import torch
except Exception as exc:
    print(json.dumps({"error": f"import failed: {exc}"})); raise SystemExit
report["torch"] = torch.__version__
report["cuda_runtime"] = torch.version.cuda
report["available"] = torch.cuda.is_available()
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    report["gpu"] = torch.cuda.get_device_name(0)
    report["vram_gib"] = round(p.total_memory / 1024**3, 2)
    try:
        x = torch.randn((1024, 1024), device="cuda")
        (x @ x).sum().item()
        torch.cuda.synchronize()
        report["tensor_test"] = True
    except Exception as exc:
        report["tensor_test"] = False
        report["tensor_error"] = str(exc)
print(json.dumps(report))
PY
)"
  # shellcheck disable=SC2016
  read_json() { printf '%s' "$TORCH_OUT" | tail -1 | .venv/bin/python -c \
    "import json,sys; print(json.load(sys.stdin).get('$1',''))" 2>/dev/null; }

  if [[ -n "$(read_json error)" ]]; then
    fail "pytorch" "$(read_json error)"
  else
    pass "pytorch version" "$(read_json torch)"
    pass "pytorch CUDA runtime" "$(read_json cuda_runtime)"
    if [[ "$(read_json available)" == "True" ]]; then
      pass "torch.cuda.is_available()" "True"
      GPU_NAME="$(read_json gpu)"
      if [[ "$GPU_NAME" == *"3050"* ]]; then
        pass "GPU detected" "$GPU_NAME"
      else
        warn "GPU detected" "$GPU_NAME (expected RTX 3050)"
      fi
      VRAM="$(read_json vram_gib)"
      if awk "BEGIN{exit !($VRAM >= 7.0)}" 2>/dev/null; then
        pass "VRAM" "${VRAM} GiB"
      else
        warn "VRAM" "${VRAM} GiB (low)"
      fi
      if [[ "$(read_json tensor_test)" == "True" ]]; then
        pass "CUDA tensor operation" "matmul on device 0"
      else
        fail "CUDA tensor operation" "$(read_json tensor_error)"
      fi
    else
      fail "torch.cuda.is_available()" "False"
    fi
  fi
fi

# ----------------------------------------------------------------- toolchain
section "Toolchain and storage"

if command -v ffmpeg >/dev/null 2>&1; then
  pass "ffmpeg" "$(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}')"
else
  fail "ffmpeg" "not installed"
fi

FREE_GB="$(df -BG --output=avail "$ROOT" 2>/dev/null | tail -1 | tr -dc '0-9')"
if [[ -n "$FREE_GB" ]]; then
  if (( FREE_GB >= 100 )); then
    pass "free storage" "${FREE_GB} GB"
  elif (( FREE_GB >= 25 )); then
    warn "free storage" "${FREE_GB} GB (100 GB recommended for SDXL + Wan 2.2)"
  else
    fail "free storage" "${FREE_GB} GB (need at least 25 GB)"
  fi
else
  warn "free storage" "could not determine"
fi

# -------------------------------------------------------------------- config
section "Configuration"

if [[ -f config/extra_model_paths.yaml ]]; then
  if [[ -x .venv/bin/python ]] && .venv/bin/python -c \
      "import yaml,sys; yaml.safe_load(open('config/extra_model_paths.yaml'))" 2>/dev/null; then
    BASE="$(.venv/bin/python -c \
      "import yaml;d=yaml.safe_load(open('config/extra_model_paths.yaml'));print(d['ai_video_gen']['base_path'])" 2>/dev/null)"
    if [[ "$BASE" == "$ROOT" ]]; then
      pass "extra_model_paths.yaml" "valid, base_path matches root"
    else
      fail "extra_model_paths.yaml" "base_path '$BASE' != '$ROOT'; run ./bootstrap.sh --repair"
    fi
  else
    fail "extra_model_paths.yaml" "invalid YAML or PyYAML missing"
  fi
else
  fail "extra_model_paths.yaml" "missing"
fi

if [[ -f config/model-profiles.yaml ]]; then
  if [[ -x .venv/bin/python ]] && .venv/bin/python -c \
      "import yaml;yaml.safe_load(open('config/model-profiles.yaml'))" 2>/dev/null; then
    pass "model-profiles.yaml" "valid YAML"
  else
    fail "model-profiles.yaml" "invalid YAML"
  fi
else
  fail "model-profiles.yaml" "missing"
fi

MISSING_DIRS=()
for d in checkpoints diffusion_models text_encoders clip clip_vision vae loras \
         controlnet ipadapter embeddings upscale_models private; do
  [[ -d "models/$d" ]] || MISSING_DIRS+=("$d")
done
if [[ ${#MISSING_DIRS[@]} -eq 0 ]]; then
  pass "model directories" "all present under models/"
else
  warn "model directories" "missing: ${MISSING_DIRS[*]}"
fi

if [[ -d engine/ComfyUI/models ]] && \
   find engine/ComfyUI/models -type f \( -name '*.safetensors' -o -name '*.ckpt' \) \
        -print -quit 2>/dev/null | grep -q .; then
  warn "submodule model dir" "weights found inside engine/ComfyUI/models (should live in models/)"
else
  pass "submodule model dir" "no duplicated weights"
fi

if [[ -f .active-model-profile ]]; then
  ACTIVE="$(tr -d '\n' < .active-model-profile)"
  if [[ -x .venv/bin/python ]] && .venv/bin/python -c \
      "import yaml,sys; d=yaml.safe_load(open('config/model-profiles.yaml')); \
       sys.exit(0 if '$ACTIVE' in (d.get('profiles') or {}) else 1)" 2>/dev/null; then
    pass "active model profile" "$ACTIVE"
  else
    warn "active model profile" "'$ACTIVE' is not defined in config/model-profiles.yaml"
  fi
else
  warn "active model profile" "none set (./scripts/modelctl set <profile>)"
fi

# -------------------------------------------------------------------- runtime
section "Runtime"

if command -v ss >/dev/null 2>&1; then
  if ss -ltn "sport = :8188" 2>/dev/null | grep -q 8188; then
    warn "port 8188" "already in use (ComfyUI may already be running)"
  else
    pass "port 8188" "free"
  fi
else
  warn "port 8188" "ss not available; not checked"
fi

if [[ -x scripts/comfy.sh ]]; then
  if bash -n scripts/comfy.sh 2>/dev/null; then
    pass "comfy.sh" "executable, syntax valid"
  else
    fail "comfy.sh" "syntax error"
  fi
else
  fail "comfy.sh" "missing or not executable"
fi

if [[ -f engine/ComfyUI/main.py && -x .venv/bin/python ]]; then
  if .venv/bin/python engine/ComfyUI/main.py --help >/dev/null 2>&1; then
    pass "ComfyUI startup command" "main.py --help succeeds"
  else
    fail "ComfyUI startup command" "main.py --help failed"
  fi
fi

# -------------------------------------------------------------------- summary
printf '\n%sSummary%s: ' "$BLD" "$NC"
if (( FAILURES > 0 )); then
  printf '%s%d FAIL%s, %d WARN\n' "$RED" "$FAILURES" "$NC" "$WARNINGS"
  exit 1
fi
if (( WARNINGS > 0 )); then
  printf '%sall critical checks passed%s, %d WARN\n' "$GRN" "$NC" "$WARNINGS"
else
  printf '%sall checks passed%s\n' "$GRN" "$NC"
fi
exit 0
