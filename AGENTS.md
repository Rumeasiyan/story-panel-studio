# AGENTS.md — story-panel-studio

Working guide for this repository. Read before touching anything.

## What this project is

A **local generation service** for AI story-video assets, running on one workstation:
Fedora + Hyprland, NVIDIA RTX 3050 with 8 GB VRAM. It exposes images, image editing,
narration, subtitles and video over one REST API on `127.0.0.1:8189`, backed by ComfyUI
on `127.0.0.1:8188`.

**It generates; it does not orchestrate.** A separate application queues jobs, collects
the files, and does script writing, assembly, thumbnails, SEO and upload. Do not add
batch orchestration, scheduling, or publishing here — that boundary is deliberate.

The consumer is a four-channel faceless YouTube network (anime x cinematic, English x
Tamil) producing still-panel story videos with synthetic narration, at four videos a day.
Two consequences shape everything: **generation must run locally** (the venture has a
$50/month opex cap, so hosted image APIs are out at production volume), and **human
time is the scarce resource, not GPU time**.

The repository is a **reproducible recipe**, not a model warehouse. Weights, renders and
environments are never committed; they are rebuilt from pinned manifests.

## Where to look

| Path | When you need it |
|---|---|
| `service/API.md` | The API contract. Start here if you are writing a caller. |
| `service/pipelines/` | One module per capability. Add a capability here, not in `app.py`. |
| `service/app.py` | Routes, parameter validation, file serving. Generic across pipelines. |
| `service/jobs.py` | SQLite job store and the single serialized worker. |
| `config/model-profiles.yaml` | Every model: pinned revision, size, SHA-256, licence. |
| `config/generation-locks.yaml` | **Which narration engine and anchor to use per language.** Read before generating any audio. |
| `config/extra_model_paths.yaml` | How ComfyUI finds weights in the root `models/`. |
| `scripts/` | `doctor`, `comfy`, `serve`, `modelctl`, `forget-generation`, `fetch-tts`, `train-lora`. |
| `tools/sd-scripts` | kohya-ss trainer, pinned submodule. Runs in `.venv-trainer`. |
| `reports/BENCHMARKS.md` | Measured timings on this exact machine. Use these, do not guess. |
| `reports/MODEL_LICENSES.md` | Licence position per model, including the unresolved ones. |
| `docs/DECISIONS.md` | Why things are the way they are. Read before reversing a decision. |
| `docs/START-HERE.md` | Entry point for the consuming goal repo. Keep it true — it is what the orchestrator plans against. |
| `workflows/` | Committed ComfyUI JSON, copied verbatim from official templates. |

## Constraints

Each of these has already caused, or nearly caused, a real failure here.

| Rule | Why | Enforced at |
|---|---|---|
| ComfyUI binds to `127.0.0.1` only | `/prompt` executes arbitrary node graphs. Exposing it is remote code execution on this workstation. | `scripts/comfy.sh` refuses non-loopback `COMFY_HOST` |
| User input never becomes graph structure | Same reason. Pipelines fill typed fields into a fixed template; a caller-supplied graph would be arbitrary execution. | `service/pipelines/*.py` build functions |
| Never install a model's dependencies into `.venv` without checking `transformers` and `torch` after | `parler-tts` pins `transformers==4.46.1` and sd-scripts pins `4.54.1`; ComfyUI needs `>=4.50.3`. Installing parler into `.venv` downgraded transformers and left the image engine one restart from breaking. | `.venv-parler`, `.venv-trainer` isolation |
| Weights live once under root `models/`, never inside `engine/ComfyUI/models` | Keeps the submodule clean and lets other engines share the store. | `config/extra_model_paths.yaml` |
| Never commit weights, renders, inputs, `.env`, or caches | A 7 GB checkpoint in git history is effectively permanent. | `.githooks/pre-commit`, `.github/workflows/repository-safety.yml` |
| Pin every model to a commit SHA, never `main` | `main` moves; a floating pin makes a "reproducible" manifest a lie. | `config/model-profiles.yaml` |
| Pin ComfyUI and custom nodes by commit; add nodes one at a time | Node packs can replace torch/CUDA packages. | `.gitmodules`, `scripts/custom-nodectl` |
| Generation uses the locked model for the job — images, video and narration | Every alternative was generated and then rejected by looking or listening. An agent picking a "better" model from its description silently changes the look or voice of a channel. | `config/generation-locks.yaml` |
| Do not touch the NVIDIA driver, Secure Boot, kernels, or Hyprland config | This is also a gaming machine with a working driver. | — |
| Deleting a job must clear the WAL too | `VACUUM` alone leaves deleted prompts readable in `app.db-wal`. Found by planting a canary and grepping. | `jobs.purge_database()` |
| `--shred` cannot erase on this filesystem | `/home` is btrfs, copy-on-write: overwriting writes new blocks and leaves the original. LUKS is the real protection. | `scripts/forget-generation` warns |

## Locked models

**Use `config/generation-locks.yaml`. Do not choose a model yourself.**

| Job | Use |
|---|---|
| Anime panels | `sdxl-text-to-image`, `model=anime` (Illustrious-XL v2.0, **booru tags**) |
| Cinematic panels | `sdxl-text-to-image`, `model=cinematic` (RealVisXL V4, prose) |
| Character consistency | LoRA via `./scripts/train-lora --base illustrious` |
| Establishing shots, no character | `flux2-text-to-image` |
| Image editing | `flux2-edit` |
| Video | **out of scope** — no weights installed, do not download |

Narration:

| Language | Pipeline | Anchor |
|---|---|---|
| English | `tts-chatterbox` | `assets/voices/locked/en.wav` |
| Tamil | `tts-omnivoice` | `assets/voices/locked/a01-auto.wav` |
| Sinhala | `tts-omnivoice` | `assets/voices/locked/a01-auto.wav` |

Deviate only when the request explicitly asks for a different engine or voice. "This
model supports more languages" or "this one is newer" is not a reason — the locked set
was picked by listening to generated samples, and the alternatives were rejected the
same way. Reference output for each is in `output/voice-lock/`.

Three things that are easy to get wrong:

- **Voice identity lives only in the anchor clip.** No parameter changes timbre or age.
  Without an anchor, every call invents a new speaker, so a multi-beat narration drifts.
- **`a01-auto.wav` cannot be regenerated.** It came from OmniVoice's auto mode, which
  invents a speaker per call. The file is the only copy of that narrator.
- **Write in spoken register, not written.** Literary Tamil (`வந்தான்`) and written
  Sinhala (`ඔහු ... සිටියේය`) read as a news bulletin. `generation-locks.yaml` gives the
  markers for each.

Emotion is per-beat and belongs in `segments`, one call per beat — see `service/API.md`.
English has real emotion control; Tamil and Sinhala have pacing only, which is a
limitation of OmniVoice and not something settings can fix.

## Commands

All verified working. Run from the repository root.

```bash
./bootstrap.sh --core-only        # rebuild the environment from scratch, idempotent
./scripts/doctor.sh               # PASS/WARN/FAIL health check; non-zero on failure
./scripts/serve.sh                # start ComfyUI + the API on :8189
./scripts/serve.sh --no-engine    # API only, ComfyUI already running
./scripts/repository-check.sh --all   # safety scan; the pre-commit hook runs --staged
make help                         # every wrapper target
```

Models and assets:

```bash
./scripts/train-lora --check          # verify the trainer environment
./scripts/train-lora --name <char> --images <dir> [--base illustrious] [--resolution 768]
./scripts/modelctl list|status|show <p>|install <p>|verify <p> [--hash]|disk
./scripts/fetch-tts [--check]     # narration models (gated: accept terms on HF first)
./scripts/custom-nodectl list|verify|install <id>
./scripts/forget-generation <job-id>|--all|--audit
./scripts/workflow-to-api IN -o OUT   # UI workflow -> API schema, needs ComfyUI running
```

There is no test suite and no linter config. Verification here is running the thing:
`doctor.sh`, then a real job through the API.

## Conventions

- **Commits:** Conventional Commits, as the history already does — `feat(scope):`,
  `fix:`, `docs:`, `chore:`. Body explains *why*, and states what was measured or
  verified. Several commits record a bug found by testing rather than review; keep that.
- **Branching:** commit directly to `main`. Single operator, no reviewers.
- **Python:** 4-space indent, type hints on function signatures, module docstrings that
  explain *why the module exists*. Comments explain reasoning, not mechanics.
- **Numbers:** never state a timing or size you have not measured. `reports/BENCHMARKS.md`
  exists so estimates can be replaced with facts.

## Versioning

| | |
|---|---|
| Canonical source | `VERSION` at the repository root |
| Current version | `2.3.0` |
| Build number | none — this is not a packaged application |
| Displayed at | `GET /api/status` and `/docs`, read via `config.VERSION` |

`service/config.py` reads `VERSION` and `service/app.py` uses it. **Never hardcode a
version anywhere else** — there was a duplicate in `app.py` and it is gone.

Bump on **every completed change**, using the highest applicable:

| Change | Bump |
|---|---|
| Breaking API change — a pipeline id, parameter, or response shape a caller depends on | MAJOR |
| New pipeline, new model profile, new endpoint, backward-compatible parameter | MINOR |
| Bug fix, error-message improvement, dependency fix | PATCH |
| Docs, comments, benchmarks, refactor with no behaviour change | none |

```bash
echo "2.1.0" > VERSION            # then note it in CHANGELOG.md
curl -s localhost:8189/api/status # confirm the running service reports it
```

Do not tag, release, or deploy unless explicitly asked.

## Workflow

1. **Check for an open issue.** `gh issue list`. If none covers the work, open one
   (see below) and assign it to `Rumeasiyan`.
2. **Read** `docs/DECISIONS.md` if the work touches an area with a recorded decision.
3. **Build.** Verify by running it, not by reading it — this repo has no tests, and
   three real bugs here were found only by executing the path.
4. **Bump `VERSION`** per the table above, and add a `CHANGELOG.md` entry.
5. **Record a decision** in `docs/DECISIONS.md` if a future reader would ask "why is it
   like this?".
6. **Run** `./scripts/doctor.sh` and `./scripts/repository-check.sh --all`.
7. **Commit** referencing the issue (`refs #12`), then comment the outcome on the issue
   and close it: what was built, what was verified, the resulting version, and anything
   deferred with a link to the follow-up issue.

## Issues

**An item raised only in conversation is lost.** Anything a future reader would need —
an open question, a deferred fix, a discovered bug, a risky assumption — becomes an
issue *when it is found*, not in a closing summary.

**Issues must be self-contained.** The reader has not seen the conversation. No "as
discussed". State what it is, the concrete consequence of ignoring it, where it surfaced
(paths), and for decisions the realistic options with a recommendation and its reasoning.

Too small for an issue: renaming a local variable, fixing a typo, adjusting a comment.
If it is done in the same commit as the work that revealed it, it does not need one.

Labels are defined in this repository rather than inherited from GitHub's defaults —
see `gh label list`. They map to how this project actually fails: `security` for the
localhost/graph-execution boundary, `licence` for unresolved model terms, `models` for
weight and manifest work, `consistency` for character and voice identity, `vram` for
things that fit or do not fit in 8 GB.
