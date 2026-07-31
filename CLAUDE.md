# CLAUDE.md — ai-video-gen

Persistent project rules. Read this before any action in this repository.

## Project identity

- Project root: `~/external/ai-video-gen` (absolute: `/home/sshroot/external/ai-video-gen`)
- Platform: Fedora Linux + Hyprland (Wayland). Also a gaming machine.
- GPU: NVIDIA GeForce RTX 3050, 8 GB VRAM
- This repository is a **reproducible recipe**, not a model/output warehouse.
- Primary engine: ComfyUI
- ComfyUI location: `engine/ComfyUI` (pinned Git submodule)
- Python environment: `.venv` (project root, never inside the submodule)
- Shared model store: root `models/`
- Model registry: `config/model-profiles.yaml`
- Local active profile state: `.active-model-profile` (gitignored)
- Generated content: `output/`
- ComfyUI user data: `user/`

## Persistent rules

1. Inspect before changing.
2. Never commit weights, renders, inputs, secrets, caches, logs, or the virtual environment.
3. Never use `sudo pip`. Never install project packages into Fedora's system Python.
4. Never modify a working NVIDIA installation without explicit approval. If `nvidia-smi`
   works and reports the RTX 3050, do not touch the driver.
5. Do not disable Secure Boot. Do not remove kernels or NVIDIA packages.
6. Do not install the full system CUDA Toolkit; use official CUDA-enabled PyTorch wheels.
7. Never expose ComfyUI publicly. Bind only to `127.0.0.1:8188`. Never `--listen 0.0.0.0`.
8. Use external model paths (`config/extra_model_paths.yaml`) instead of copying or
   symlinking weights into `engine/ComfyUI/models`. Store weights once under root `models/`.
9. Pin ComfyUI and every custom node by Git commit. Add custom nodes one at a time.
   Do not bulk-install unknown node packs.
10. Update deliberately, test after updating, and commit submodule pointer changes.
11. Ask before large downloads: any single file > 5 GB, or any set > 10 GB.
12. Do not use Git LFS for publicly available model weights.
13. Store model licences and sources in `reports/MODEL_LICENSES.md` before production use.
14. Never commit an asset whose licence does not allow the intended use.
15. Keep workflows and prompt libraries committed.
16. Back up an existing file before replacing it. Keep install scripts idempotent.
17. Record installed versions and validation results (`reports/INSTALLATION_REPORT.md`).
18. A failed phase must produce a diagnosis; do not make unrelated changes in response.
19. Do not run destructive Git commands (`git reset --hard`, `git clean -fdx`, forced
    checkout) without explicit approval. Do not destroy local changes.
20. Do not change Hyprland, monitor, gaming, Steam/Proton, kernel, or bootloader config
    unless a confirmed problem requires it.
21. Run `./scripts/doctor.sh` after environment changes.
22. Run `./scripts/repository-check.sh` before commits.
23. Do not modify global Git configuration; this repo uses local `core.hooksPath`.

## Standard commands

```bash
./bootstrap.sh                      # full idempotent setup
./bootstrap.sh --core-only          # no model downloads
./bootstrap.sh --skip-system-packages
./bootstrap.sh --repair

./scripts/doctor.sh                 # PASS/WARN/FAIL health check
./scripts/repository-check.sh       # git safety scan

./scripts/comfy.sh image            # normal VRAM mode
./scripts/comfy.sh lowvram          # low-VRAM mode
./scripts/comfy.sh wan              # most conservative, for Wan 2.2
./scripts/comfy.sh help

./scripts/modelctl list
./scripts/modelctl show <profile>
./scripts/modelctl status
./scripts/modelctl install <profile>
./scripts/modelctl set <profile>
./scripts/modelctl verify <profile>
./scripts/modelctl disk

./scripts/custom-nodectl list|install <id>|verify|update <id>

./scripts/update.sh                 # deliberate ComfyUI/submodule update
./scripts/snapshot.sh               # environment snapshot report
```

Makefile wrappers: `make help bootstrap doctor run run-lowvram run-wan models
model-status repo-check snapshot update`.

## Model profile caveat

> Selecting a model profile controls downloads and script defaults. A ComfyUI workflow
> still stores the exact model filename it loads; switching profiles does not magically
> rewrite every workflow. After switching a profile, open the workflow and select the
> intended checkpoint in the loader node.

## VRAM reality (8 GB)

- SDXL still-image generation is the production priority.
- Wan 2.2 TI2V-5B is an experiment relying on ComfyUI native offloading.
- Start Wan tests at 512x288 / 41 frames. Do not start at 720p.
- Do not install 14B Wan models by default.
- Reserve ~1 GB VRAM for Hyprland and the desktop (`COMFY_RESERVE_VRAM`).
