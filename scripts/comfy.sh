#!/usr/bin/env bash
# Launch ComfyUI for story-panel-studio, bound to localhost only.
#
#   ./scripts/comfy.sh image     # normal VRAM mode, ~1 GiB reserved for the desktop
#   ./scripts/comfy.sh lowvram   # low-VRAM mode, previews off
#   ./scripts/comfy.sh wan       # most conservative supported settings (Wan 2.2)
#   ./scripts/comfy.sh help
#
# Extra arguments are forwarded to ComfyUI:
#   ./scripts/comfy.sh image --verbose DEBUG

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

MODE="${1:-}"
[[ $# -gt 0 ]] && shift || true

die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

usage() {
  sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
}

if [[ "$MODE" == "help" || "$MODE" == "-h" || "$MODE" == "--help" ]]; then usage; fi

# ---------------------------------------------------------------- configuration
set -a
# shellcheck disable=SC1091
if [[ -f config/runtime.env ]]; then source config/runtime.env; fi
# shellcheck disable=SC1091
if [[ -f .env ]]; then source .env; fi
set +a

COMFY_HOST="${COMFY_HOST:-127.0.0.1}"
COMFY_PORT="${COMFY_PORT:-8188}"
COMFY_RESERVE_VRAM="${COMFY_RESERVE_VRAM:-1}"
COMFY_PREVIEW_METHOD="${COMFY_PREVIEW_METHOD:-none}"
MODE="${MODE:-${COMFY_DEFAULT_MODE:-image}}"

case "$MODE" in
  image|lowvram|wan) ;;
  *) die "unknown mode '$MODE' (expected: image | lowvram | wan | help)" ;;
esac

# Safety rule: never expose the server beyond localhost.
if [[ "$COMFY_HOST" != "127.0.0.1" && "$COMFY_HOST" != "localhost" && "$COMFY_HOST" != "::1" ]]; then
  die "COMFY_HOST is '$COMFY_HOST'. This project binds to localhost only.
Use an SSH tunnel for remote access: ssh -L 8188:127.0.0.1:8188 user@host"
fi

# ---------------------------------------------------------------- preconditions
[[ -f engine/ComfyUI/main.py ]] || die "engine/ComfyUI is missing. Run: git submodule update --init --recursive"
[[ -x .venv/bin/python ]] || die ".venv is missing. Run: ./bootstrap.sh --core-only"
[[ -f config/extra_model_paths.yaml ]] || die "config/extra_model_paths.yaml is missing. Run: ./bootstrap.sh --repair"

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Verifying CUDA..."
python - <<'PY' || die "CUDA verification failed. Run ./scripts/doctor.sh for a diagnosis."
import sys
try:
    import torch
except Exception as exc:
    print("torch import failed:", exc); sys.exit(1)
if not torch.cuda.is_available():
    print("torch.cuda.is_available() is False"); sys.exit(1)
print(f"  GPU: {torch.cuda.get_device_name(0)}  "
      f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GiB  "
      f"torch {torch.__version__} (CUDA {torch.version.cuda})")
PY

mkdir -p input output temp user logs

if command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$COMFY_PORT" 2>/dev/null | grep -q ":$COMFY_PORT"; then
  die "port $COMFY_PORT is already in use. Another ComfyUI may be running."
fi

# ---------------------------------------------------------------- flag detection
HELP_TEXT="$(python engine/ComfyUI/main.py --help 2>/dev/null || true)"
supports() { [[ "$HELP_TEXT" == *"$1"* ]]; }

ARGS=(
  --listen "$COMFY_HOST"
  --port "$COMFY_PORT"
  --extra-model-paths-config "$ROOT/config/extra_model_paths.yaml"
)

supports "--user-directory"   && ARGS+=(--user-directory   "$ROOT/user") || true
supports "--input-directory"  && ARGS+=(--input-directory  "$ROOT/input") || true
supports "--output-directory" && ARGS+=(--output-directory "$ROOT/output") || true
supports "--temp-directory"   && ARGS+=(--temp-directory   "$ROOT/temp") || true

# ComfyUI derives its default database path from the package directory
# (engine/ComfyUI/user/comfyui.db), which --user-directory does not override and which
# does not exist in this layout. Keep the database with the rest of the local user
# state instead.
supports "--database-url" && ARGS+=(--database-url "sqlite:///$ROOT/user/comfyui.db") || true

add_reserve_vram() {
  if supports "--reserve-vram"; then
    ARGS+=(--reserve-vram "$1")
  fi
}

add_preview_none() {
  if supports "--preview-method"; then
    ARGS+=(--preview-method none)
  fi
}

case "$MODE" in
  image)
    add_reserve_vram "$COMFY_RESERVE_VRAM"
    if [[ "$COMFY_PREVIEW_METHOD" == "none" ]]; then
      add_preview_none
    elif supports "--preview-method"; then
      ARGS+=(--preview-method "$COMFY_PREVIEW_METHOD")
    fi
    ;;
  lowvram)
    supports "--lowvram" && ARGS+=(--lowvram) || true
    add_reserve_vram "$COMFY_RESERVE_VRAM"
    add_preview_none
    ;;
  wan)
    # Most conservative supported settings: aggressive offloading, no previews,
    # extra reserved VRAM for the Hyprland desktop.
    supports "--lowvram" && ARGS+=(--lowvram) || true
    add_reserve_vram "$COMFY_RESERVE_VRAM"
    add_preview_none
    supports "--disable-smart-memory" && ARGS+=(--disable-smart-memory) || true
    supports "--cache-none"           && ARGS+=(--cache-none) || true
    ;;
esac

# Only enable the manager if this pinned ComfyUI commit supports it.
if supports "--enable-manager"; then
  ARGS+=(--enable-manager)
fi

ACTIVE_PROFILE="$(cat .active-model-profile 2>/dev/null || echo '(none set)')"

cat <<EOF

  mode            : $MODE
  active profile  : $ACTIVE_PROFILE
  url             : http://$COMFY_HOST:$COMFY_PORT
  comfyui commit  : $(git -C engine/ComfyUI rev-parse --short HEAD 2>/dev/null || echo unknown)
  args            : ${ARGS[*]}

Reminder: a workflow stores the exact checkpoint filename in its loader node.
Switching the active model profile does not rewrite existing workflows.

EOF

exec python engine/ComfyUI/main.py "${ARGS[@]}" "$@"
