# Wan 2.2 TI2V-5B

Official ComfyUI built-in template `video_wan2_2_5B_ti2v`, copied verbatim from
`comfyui-workflow-templates` 0.11.23 on 2026-08-01. Not hand-authored.

Requires the `wan22-ti2v-5b` model profile:

```bash
./scripts/modelctl install wan22-ti2v-5b
./scripts/modelctl verify  wan22-ti2v-5b
```

## Generating a video

```bash
./scripts/comfy.sh wan          # low-VRAM, previews off, localhost only
```

Open <http://127.0.0.1:8188>, then **Workflow → Open** →
`workflows/video/wan22/wan2.2_ti2v_5B_official.json`.

### Change the defaults before the first run

The template ships at 1280x704 / 121 frames, which will not fit in 8 GB. In the
**Wan22ImageToVideoLatent** node set:

| Widget | Template default | First test on RTX 3050 |
|---|---|---|
| width | 1280 | **512** |
| height | 704 | **288** |
| length (frames) | 121 | **41** |
| batch_size | 1 | 1 |

Only after that run is stable, try 640x360 / 49 frames. Do not start at 720p.

`KSampler` defaults to 20 steps, cfg 5, `uni_pc` / `simple`. Leave them for the first
run so the benchmark is comparable.

### Image-to-video vs text-to-video

The **LoadImage** node (id 56) drives image-to-video. Either:

- drag an image onto the node in the browser — ComfyUI uploads it to `input/`; or
- copy the file into `input/` yourself and pick it from the node's dropdown.

For pure text-to-video, bypass or remove the LoadImage connection and drive the latent
node from the prompt alone.

Prompts live in the two **CLIPTextEncode** nodes (positive id 6, negative id 7). The
template's negative prompt is Chinese — that is upstream's, and it works; replace it
with your own if you prefer.

Press **Run**. First run also loads ~18 GB of weights from disk, so it is slow.

## Where everything is stored

| Thing | Location | Tracked by Git? |
|---|---|---|
| Input images you attach | `input/` | No — gitignored |
| Rendered video | `output/video/ComfyUI_00001_.mp4` (prefix set in the **SaveVideo** node) | No — gitignored |
| Prompt + full workflow | Embedded as metadata inside the output file, so dragging the video back into ComfyUI restores the graph | — |
| Run history (queue panel) | ComfyUI server memory, lost on restart | No |
| Workflows you save in the UI | `user/default/workflows/` | No — `user/` is gitignored |
| ComfyUI local state/database | `user/comfyui.db` | No |
| Model weights | `models/` | No |
| Server logs | `logs/`, `user/comfyui_8188.log` | No |

Nothing you generate is uploaded anywhere. The server binds to `127.0.0.1:8188` only.

## Deleting a generation completely

Four places can hold traces. Do all four for a full delete.

1. **The output file**

   ```bash
   ls output/video/
   rm output/video/ComfyUI_00007_.mp4
   ```

   This also destroys the embedded prompt and workflow metadata.

2. **The run history** — the queue/history panel in the UI. Use the trash icon to clear
   it, or from a terminal while the server is running:

   ```bash
   # delete one entry (get prompt_id from the history listing)
   curl -s -X POST http://127.0.0.1:8188/history \
     -H 'Content-Type: application/json' \
     -d '{"delete": ["<prompt_id>"]}'

   # clear the whole history
   curl -s -X POST http://127.0.0.1:8188/history \
     -H 'Content-Type: application/json' -d '{"clear": true}'
   ```

   History is in-memory anyway — restarting ComfyUI clears it.

3. **The input image**, if you attached one:

   ```bash
   rm input/your-image.png
   ```

4. **The saved workflow**, if you saved it in the UI:

   ```bash
   ls user/default/workflows/
   rm user/default/workflows/your-workflow.json
   ```

Optional, if you also want the browser to forget the open graph: clear site data for
`127.0.0.1:8188`, or just open a different workflow.

Nothing above touches Git — `output/`, `input/` and `user/` are all gitignored, so a
deleted generation leaves no trace in history.

## Record the run

After each test, append an entry to `reports/BENCHMARKS.md`: resolution, frames, steps,
sampler, seed, wall-clock time, peak VRAM, peak RAM, swap, output path, artifacts.

Measure VRAM in a second terminal while it renders:

```bash
nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 1
```
