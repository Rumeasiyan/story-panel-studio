#!/usr/bin/env bash
# Start the local web UI, and ComfyUI behind it if it is not already running.
#
#   ./scripts/serve.sh              # start ComfyUI (wan mode) if needed, then the UI
#   ./scripts/serve.sh --no-engine  # UI only; assumes ComfyUI is already up
#   ./scripts/serve.sh --mode image # run the engine in image mode instead
#
# The UI binds to 127.0.0.1 and has NO authentication. Do not expose it.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

START_ENGINE=1
ENGINE_MODE="wan"
for arg in "$@"; do
  case "$arg" in
    --no-engine) START_ENGINE=0 ;;
    --mode) shift; ENGINE_MODE="${1:-wan}" ;;
    --mode=*) ENGINE_MODE="${arg#*=}" ;;
    -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  esac
done

BLD=$'\033[1m'; GRN=$'\033[0;32m'; YEL=$'\033[0;33m'; RED=$'\033[0;31m'; NC=$'\033[0m'
[[ -t 1 ]] || { BLD=""; GRN=""; YEL=""; RED=""; NC=""; }
info() { printf '%s==>%s %s\n' "$BLD" "$NC" "$1"; }
die()  { printf '%sERROR: %s%s\n' "$RED" "$1" "$NC" >&2; exit 1; }

set -a
if [[ -f config/runtime.env ]]; then source config/runtime.env; fi
if [[ -f .env ]]; then source .env; fi
set +a

COMFY_PORT="${COMFY_PORT:-8188}"
UI_PORT="${UI_PORT:-8189}"

[[ -x .venv/bin/python ]] || die ".venv missing. Run ./bootstrap.sh --core-only"
[[ -f workflows/api/wan22_ti2v_5b.json ]] || die "workflows/api/wan22_ti2v_5b.json missing.
Regenerate it with ./scripts/workflow-to-api (needs ComfyUI running once)."

port_busy() { command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$1" 2>/dev/null | grep -q ":$1"; }

ENGINE_PID=""
cleanup() {
  if [[ -n "$ENGINE_PID" ]] && kill -0 "$ENGINE_PID" 2>/dev/null; then
    info "stopping ComfyUI"
    kill -TERM "$ENGINE_PID" 2>/dev/null || true
    for _ in $(seq 1 20); do kill -0 "$ENGINE_PID" 2>/dev/null || break; sleep 1; done
    kill -KILL "$ENGINE_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if (( START_ENGINE )); then
  if port_busy "$COMFY_PORT"; then
    info "ComfyUI already running on 127.0.0.1:$COMFY_PORT — reusing it"
  else
    mkdir -p logs
    ENGINE_LOG="logs/comfy-$(date +%Y%m%d-%H%M%S).log"
    info "starting ComfyUI ($ENGINE_MODE mode) — log: $ENGINE_LOG"
    ./scripts/comfy.sh "$ENGINE_MODE" > "$ENGINE_LOG" 2>&1 &
    ENGINE_PID=$!
    for _ in $(seq 1 120); do
      curl -fsS "http://127.0.0.1:$COMFY_PORT/" >/dev/null 2>&1 && break
      kill -0 "$ENGINE_PID" 2>/dev/null || die "ComfyUI exited during startup; see $ENGINE_LOG"
      sleep 1
    done
    curl -fsS "http://127.0.0.1:$COMFY_PORT/" >/dev/null 2>&1 \
      || die "ComfyUI did not become ready; see $ENGINE_LOG"
    printf '%s    ComfyUI ready%s\n' "$GRN" "$NC"
  fi
else
  port_busy "$COMFY_PORT" || printf '%s    warning: nothing is listening on %s%s\n' \
    "$YEL" "$COMFY_PORT" "$NC"
fi

if port_busy "$UI_PORT"; then
  die "port $UI_PORT is already in use — the UI may already be running"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

cat <<EOF

  ${GRN}${BLD}Open http://127.0.0.1:$UI_PORT${NC}

  engine : 127.0.0.1:$COMFY_PORT ($ENGINE_MODE mode)
  models : $( [[ -f models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors ]] \
              && echo "wan22-ti2v-5b present" || echo "${YEL}Wan weights missing — run ./scripts/modelctl install wan22-ti2v-5b${NC}" )
  note   : no authentication; localhost only. Ctrl-C stops everything.

EOF

exec python -m uvicorn app:app \
  --app-dir service \
  --host "${UI_HOST:-127.0.0.1}" \
  --port "$UI_PORT" \
  --log-level warning
