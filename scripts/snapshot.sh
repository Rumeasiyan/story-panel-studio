#!/usr/bin/env bash
# Record the current environment. Writes a timestamped report under reports/
# and refreshes reports/ENVIRONMENT.md as the durable summary.
#
#   ./scripts/snapshot.sh

set -uo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="logs/snapshot-$STAMP.md"
mkdir -p reports logs

py() { [[ -x .venv/bin/python ]] && .venv/bin/python "$@" 2>/dev/null; }

{
  echo "# Environment snapshot"
  echo
  echo "- Generated: $(date -Iseconds)"
  echo "- Project root: \`$ROOT\`"
  echo
  echo "## System"
  echo
  echo "| Item | Value |"
  echo "|---|---|"
  echo "| Fedora | $(cat /etc/fedora-release 2>/dev/null || echo unknown) |"
  echo "| Kernel | $(uname -r) |"
  echo "| Session | ${XDG_SESSION_TYPE:-unknown} / ${XDG_CURRENT_DESKTOP:-unknown} |"
  echo "| GPU | $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1) |"
  echo "| NVIDIA driver | $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1) |"
  echo "| VRAM | $(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1) |"
  echo "| RAM | $(free -h | awk '/^Mem:/{print $2}') |"
  echo "| Secure Boot | $(mokutil --sb-state 2>/dev/null | head -1) |"
  echo
  echo "## Software"
  echo
  echo "| Item | Value |"
  echo "|---|---|"
  echo "| Git | $(git --version | awk '{print $3}') |"
  echo "| Python (.venv) | $(py -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])') |"
  echo "| pip | $(py -m pip --version 2>/dev/null | awk '{print $2}') |"
  echo "| PyTorch | $(py -c 'import torch;print(torch.__version__)') |"
  echo "| PyTorch CUDA runtime | $(py -c 'import torch;print(torch.version.cuda)') |"
  echo "| torch.cuda.is_available() | $(py -c 'import torch;print(torch.cuda.is_available())') |"
  echo "| FFmpeg | $(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}') |"
  echo "| ComfyUI commit | \`$(git -C engine/ComfyUI rev-parse HEAD 2>/dev/null || echo unknown)\` |"
  echo "| ComfyUI subject | $(git -C engine/ComfyUI log -1 --format=%s 2>/dev/null || echo -) |"
  echo
  echo "## Custom nodes"
  echo
  if [[ -d custom_nodes ]] && find custom_nodes -mindepth 1 -maxdepth 1 -type d | grep -q .; then
    for d in custom_nodes/*/; do
      [[ -d "$d/.git" ]] || continue
      echo "- \`${d%/}\` @ $(git -C "$d" rev-parse HEAD 2>/dev/null)"
    done
  else
    echo "_none installed_"
  fi
  echo
  echo "## Model profiles"
  echo
  echo '```'
  ./scripts/modelctl status 2>&1 | sed 's/\x1b\[[0-9;]*m//g'
  echo '```'
  echo
  echo "## Disk usage"
  echo
  echo '```'
  ./scripts/modelctl disk 2>&1 | sed 's/\x1b\[[0-9;]*m//g'
  df -h "$ROOT" 2>/dev/null
  echo '```'
  echo
  echo "## pip freeze"
  echo
  echo '```'
  py -m pip freeze
  echo '```'
} > "$OUT"

cp -f "$OUT" reports/ENVIRONMENT.md

echo "wrote $OUT"
echo "wrote reports/ENVIRONMENT.md (durable summary)"
