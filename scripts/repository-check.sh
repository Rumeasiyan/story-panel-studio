#!/usr/bin/env bash
# Repository safety check.
#
# Usage:
#   scripts/repository-check.sh            # check STAGED files (used by pre-commit hook)
#   scripts/repository-check.sh --tracked  # check ALL tracked files
#   scripts/repository-check.sh --all      # both of the above
#
# Exits non-zero when a prohibited file is found.

set -uo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT" || exit 1

MODE="${1:---staged}"
MAX_BYTES=$((50 * 1024 * 1024))   # 50 MB
FAILED=0

RED=$'\033[0;31m'; YEL=$'\033[0;33m'; GRN=$'\033[0;32m'; NC=$'\033[0m'
[[ -t 1 ]] || { RED=""; YEL=""; GRN=""; NC=""; }

fail() { printf '%sFAIL%s %s\n' "$RED" "$NC" "$1"; FAILED=1; }
warn() { printf '%sWARN%s %s\n' "$YEL" "$NC" "$1"; }
ok()   { printf '%sOK%s   %s\n' "$GRN" "$NC" "$1"; }

# Extensions that must never be committed.
WEIGHT_EXT_RE='\.(safetensors|ckpt|pt|pth|bin|onnx|gguf|engine)$'
MEDIA_EXT_RE='\.(mp4|mov|mkv|webm|avi|wav|flac|mp3|aac|psd|xcf|blend|exr)$'
SECRET_RE='(^|/)(\.env(\..*)?|.*\.(token|key|pem)|id_rsa|id_ed25519|credentials\.json)$'
SECRET_ALLOW_RE='(^|/)\.env\.example$'
IGNORED_DIR_RE='^(models|input|output|temp|cache|user)/'

check_list() {
  local label="$1"; shift
  local files=("$@")
  local f size

  if [[ ${#files[@]} -eq 0 ]]; then
    ok "$label: nothing to check"
    return
  fi

  for f in "${files[@]}"; do
    [[ -z "$f" ]] && continue

    if [[ "$f" =~ $SECRET_RE ]] && ! [[ "$f" =~ $SECRET_ALLOW_RE ]]; then
      fail "$label: secret-like file: $f"
      continue
    fi
    if [[ "$f" =~ $WEIGHT_EXT_RE ]]; then
      fail "$label: model weight file: $f"
      continue
    fi
    if [[ "$f" =~ $MEDIA_EXT_RE ]]; then
      fail "$label: generated/large media file: $f"
      continue
    fi
    if [[ "$f" =~ $IGNORED_DIR_RE ]]; then
      fail "$label: file inside an ignored data directory (force-added?): $f"
      continue
    fi
    if [[ "$f" == .venv/* || "$f" == venv/* ]]; then
      fail "$label: virtual environment file: $f"
      continue
    fi

    if [[ -f "$f" ]]; then
      size=$(stat -c %s -- "$f" 2>/dev/null || echo 0)
      if (( size > MAX_BYTES )); then
        fail "$label: file larger than 50 MB ($((size / 1024 / 1024)) MB): $f"
        continue
      fi
      if (( size > 25 * 1024 * 1024 )); then
        warn "$label: file larger than 25 MB: $f"
      fi
    fi
  done
}

mapfile_or_empty() {
  # $1 = variable name, rest = command
  local __var="$1"; shift
  local __out
  __out="$("$@" 2>/dev/null)"
  if [[ -z "$__out" ]]; then
    eval "$__var=()"
  else
    mapfile -t "$__var" <<<"$__out"
  fi
}

echo "== Repository safety check (mode: $MODE) =="

if [[ "$MODE" == "--staged" || "$MODE" == "--all" ]]; then
  mapfile_or_empty STAGED git diff --cached --name-only --diff-filter=ACMR
  check_list "staged" "${STAGED[@]}"
fi

if [[ "$MODE" == "--tracked" || "$MODE" == "--all" ]]; then
  mapfile_or_empty TRACKED git ls-files
  check_list "tracked" "${TRACKED[@]}"
fi

if [[ $FAILED -eq 0 ]]; then
  printf '%sRepository safety check passed.%s\n' "$GRN" "$NC"
else
  printf '%sRepository safety check FAILED.%s\n' "$RED" "$NC"
  echo "Unstage the offending files. Weights belong in models/ (gitignored)."
fi

exit "$FAILED"
