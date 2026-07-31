#!/usr/bin/env bash
# Deliberate update of the pinned ComfyUI submodule and the Python environment.
#
#   ./scripts/update.sh              # inspect and prompt before changing the pin
#   ./scripts/update.sh --check      # report available upstream changes only
#   ./scripts/update.sh --allow-dirty
#
# Never floats silently to the latest ComfyUI commit. Never commits for you.

set -uo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

CHECK_ONLY=0
ALLOW_DIRTY=0
for arg in "$@"; do
  case "$arg" in
    --check)       CHECK_ONLY=1 ;;
    --allow-dirty) ALLOW_DIRTY=1 ;;
    -h|--help)     sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option '$arg'" >&2; exit 2 ;;
  esac
done

BLD=$'\033[1m'; GRN=$'\033[0;32m'; YEL=$'\033[0;33m'; RED=$'\033[0;31m'; NC=$'\033[0m'
[[ -t 1 ]] || { BLD=""; GRN=""; YEL=""; RED=""; NC=""; }
step() { printf '\n%s==> %s%s\n' "$BLD" "$1" "$NC"; }
ok()   { printf '    %s%s%s\n' "$GRN" "$1" "$NC"; }
warn() { printf '    %s%s%s\n' "$YEL" "$1" "$NC"; }
die()  { printf '%sERROR: %s%s\n' "$RED" "$1" "$NC" >&2; exit 1; }

# ------------------------------------------------------- 1. working tree state
step "Root working tree"
DIRTY="$(git status --porcelain --untracked-files=no | grep -v '^ M engine/ComfyUI$' || true)"
if [[ -n "$DIRTY" ]]; then
  echo "$DIRTY" | sed 's/^/    /'
  if (( ALLOW_DIRTY )); then
    warn "working tree is dirty; continuing because --allow-dirty was given"
  else
    die "root working tree is not clean. Commit or stash first, or pass --allow-dirty.
This script will not discard local changes."
  fi
else
  ok "clean"
fi

# ------------------------------------------------------------ 2. current pin
step "Current ComfyUI pin"
[[ -f engine/ComfyUI/main.py ]] || die "engine/ComfyUI is not initialized"
CURRENT="$(git -C engine/ComfyUI rev-parse HEAD)"
echo "    commit : $CURRENT"
git -C engine/ComfyUI log -1 --format='    date   : %ci%n    subject: %s' HEAD

# --------------------------------------------------------------- 3. fetch
step "Fetching upstream"
git -C engine/ComfyUI fetch --quiet origin || die "fetch failed"
DEFAULT_BRANCH="$(git -C engine/ComfyUI symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/master)"
UPSTREAM="$(git -C engine/ComfyUI rev-parse "$DEFAULT_BRANCH" 2>/dev/null || true)"
[[ -n "$UPSTREAM" ]] || die "could not resolve $DEFAULT_BRANCH"
ok "upstream $DEFAULT_BRANCH = $UPSTREAM"

if [[ "$CURRENT" == "$UPSTREAM" ]]; then
  ok "already at the latest upstream commit; nothing to update"
  exit 0
fi

# ------------------------------------------------------- 4. show the change
step "Available upstream changes"
BEHIND="$(git -C engine/ComfyUI rev-list --count "$CURRENT..$UPSTREAM" 2>/dev/null || echo '?')"
echo "    $BEHIND commit(s) ahead of the current pin"
git -C engine/ComfyUI log --oneline --no-decorate "$CURRENT..$UPSTREAM" | head -40 | sed 's/^/    /'
[[ "$BEHIND" != "?" && "$BEHIND" -gt 40 ]] && echo "    ... (truncated)"

REQ_DIFF="$(git -C engine/ComfyUI diff --stat "$CURRENT..$UPSTREAM" -- requirements.txt manager_requirements.txt || true)"
if [[ -n "$REQ_DIFF" ]]; then
  echo
  echo "    requirements changes:"
  echo "$REQ_DIFF" | sed 's/^/    /'
fi

if (( CHECK_ONLY )); then
  echo
  ok "--check: no changes made"
  exit 0
fi

# ----------------------------------------------------------- 5. approval
step "Approval"
if [[ ! -t 0 ]]; then
  die "non-interactive session; refusing to change the pinned submodule"
fi
read -r -p "    Move engine/ComfyUI to $UPSTREAM? [y/N] " reply
[[ "${reply,,}" == "y" || "${reply,,}" == "yes" ]] || { warn "aborted; pin unchanged"; exit 1; }

# ------------------------------------------------------------ 6. checkout
step "Updating submodule"
git -C engine/ComfyUI checkout --quiet "$UPSTREAM" || die "checkout failed"
ok "engine/ComfyUI now at $(git -C engine/ComfyUI rev-parse --short HEAD)"

# -------------------------------------------------------- 7. requirements
step "Reinstalling requirements"
[[ -x .venv/bin/python ]] || die ".venv missing"
# shellcheck disable=SC1091
source .venv/bin/activate
# ComfyUI's own requirements are authoritative during an update;
# requirements.lock.txt is only an environment snapshot.
cp -p requirements.lock.txt "requirements.lock.txt.bak.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
pip install -r engine/ComfyUI/requirements.txt || die "requirements install failed"
[[ -f engine/ComfyUI/manager_requirements.txt ]] && \
  pip install -r engine/ComfyUI/manager_requirements.txt
pip install -r requirements-project.txt

step "pip check"
pip check || warn "pip check reported issues"

pip freeze > requirements.lock.txt
ok "requirements.lock.txt refreshed"

# ------------------------------------------------------------- 8. doctor
step "Doctor"
./scripts/doctor.sh || die "doctor reported critical failures after the update"

# ------------------------------------------------------------- 9. handoff
step "Review and commit"
git status --short --untracked-files=no | sed 's/^/    /'
cat <<EOF

The submodule pointer change is staged for your review but NOT committed.
Test a render, then commit:

    git add engine/ComfyUI requirements.lock.txt
    git commit -m "chore: update ComfyUI pin to $(git -C engine/ComfyUI rev-parse --short HEAD)"

To roll back instead:

    git -C engine/ComfyUI checkout $CURRENT
EOF
