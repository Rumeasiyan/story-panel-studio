"""Local web UI for Wan 2.2 video generation.

Binds to 127.0.0.1 and has no authentication — it is a single-user local tool. Do not
expose it to a network without putting real auth and quotas in front of it.

    ./scripts/serve.sh          then open http://127.0.0.1:8189
"""

from __future__ import annotations

import io
import mimetypes
import os
import random
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# service/ is added to sys.path by uvicorn's app dir; make direct execution work too.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

import jobs as jobstore
from config import (
    BASELINE_COST,
    BASELINE_VRAM_GIB,
    DATA_DIR,
    DEFAULTS,
    DEFAULT_NEGATIVE,
    FRAME_CHOICES,
    DIM_STEP,
    FRAME_STEP,
    MAX_DIM,
    MAX_FRAMES,
    MAX_UPLOAD_BYTES,
    MIN_DIM,
    MIN_FRAMES,
    OUTPUT_DIR,
    PRESETS,
    SERVICE_DIR,
    THUMB_DIR,
    UI_HOST,
    UI_PORT,
)

UPLOAD_DIR = DATA_DIR / "uploads"

SAMPLERS = ["uni_pc", "euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "ddim"]
SCHEDULERS = ["simple", "normal", "karras", "beta", "sgm_uniform"]

runner = jobstore.Runner()


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobstore.init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    runner.requeue_orphans()
    runner.start()
    yield
    await runner.stop()


app = FastAPI(title="ai-video-gen", lifespan=lifespan)


# ------------------------------------------------------------------ validation

def clean_text(value: str, limit: int = 4000) -> str:
    return (value or "").strip()[:limit]


def parse_int(value, default: int, low: int, high: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def parse_float(value, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def snap(value: int) -> int:
    """Round a dimension to the multiple of 16 that Wan's VAE requires."""
    return max(MIN_DIM, min(MAX_DIM, round(value / DIM_STEP) * DIM_STEP))


def normalise_image(raw: bytes, job_id: str) -> str:
    """Re-encode an upload to PNG. Never trust an uploaded file as-is."""
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"not a readable image: {exc}") from exc

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    if max(image.size) > 4096:
        image.thumbnail((4096, 4096))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{job_id}.png"
    image.save(UPLOAD_DIR / name, format="PNG")
    return name


# ---------------------------------------------------------------------- routes

@app.get("/api/options")
async def options():
    return {
        "presets": [
            {"id": key, "width": w, "height": h, "note": note}
            for key, (w, h, note) in PRESETS.items()
        ],
        "frames": FRAME_CHOICES,
        "samplers": SAMPLERS,
        "schedulers": SCHEDULERS,
        "defaults": DEFAULTS,
        "limits": {
            "min_dim": MIN_DIM,
            "max_dim": MAX_DIM,
            "dim_step": DIM_STEP,
            "frame_step": FRAME_STEP,
            "min_frames": MIN_FRAMES,
            "max_frames": MAX_FRAMES,
            "baseline_cost": BASELINE_COST,
            "baseline_vram_gib": BASELINE_VRAM_GIB,
        },
        "default_negative": DEFAULT_NEGATIVE,
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
    }


@app.get("/api/status")
async def status():
    stats = await runner.client.system_stats()
    gpu = None
    if stats:
        devices = stats.get("devices") or []
        if devices:
            device = devices[0]
            gpu = {
                "name": device.get("name"),
                "vram_total": device.get("vram_total"),
                "vram_free": device.get("vram_free"),
            }
    return {
        "comfy_up": stats is not None,
        "comfy_version": (stats or {}).get("system", {}).get("comfyui_version"),
        "gpu": gpu,
        "current": runner.current,
        "queued": runner.queue.qsize(),
        "total_jobs": jobstore.count_jobs(),
    }


@app.post("/api/generate")
async def generate(
    prompt: str = Form(...),
    negative: str = Form(DEFAULT_NEGATIVE),
    preset: str = Form(DEFAULTS["preset"]),
    width: int = Form(512),
    height: int = Form(288),
    frames: int = Form(DEFAULTS["frames"]),
    steps: int = Form(DEFAULTS["steps"]),
    cfg: float = Form(DEFAULTS["cfg"]),
    fps: int = Form(DEFAULTS["fps"]),
    shift: float = Form(DEFAULTS["shift"]),
    sampler: str = Form(DEFAULTS["sampler"]),
    scheduler: str = Form(DEFAULTS["scheduler"]),
    seed: str = Form(""),
    image: UploadFile | None = None,
):
    prompt = clean_text(prompt)
    if not prompt:
        raise HTTPException(400, "a prompt is required")

    if preset == "custom":
        # Only the model's own constraints are enforced. How much the GPU can take is
        # the operator's call: the UI shows the cost, it does not veto it.
        width = snap(parse_int(width, 512, MIN_DIM, MAX_DIM))
        height = snap(parse_int(height, 288, MIN_DIM, MAX_DIM))
    elif preset in PRESETS:
        width, height, _ = PRESETS[preset]
    else:
        raise HTTPException(400, f"unknown preset '{preset}'")

    frames = parse_int(frames, DEFAULTS["frames"], MIN_FRAMES, MAX_FRAMES)
    # Wan needs length = 4n + 1.
    frames = frames - ((frames - 1) % FRAME_STEP)

    steps = parse_int(steps, DEFAULTS["steps"], 1, 60)
    fps = parse_int(fps, DEFAULTS["fps"], 1, 60)
    cfg = parse_float(cfg, DEFAULTS["cfg"], 0.0, 20.0)
    shift = parse_float(shift, DEFAULTS["shift"], 0.0, 20.0)

    if sampler not in SAMPLERS:
        raise HTTPException(400, f"unknown sampler '{sampler}'")
    if scheduler not in SCHEDULERS:
        raise HTTPException(400, f"unknown scheduler '{scheduler}'")

    seed_value = seed.strip()
    if seed_value and re.fullmatch(r"\d{1,19}", seed_value):
        seed_number = int(seed_value)
    else:
        seed_number = random.randint(0, 2**63 - 1)

    params = {
        "prompt": prompt,
        "negative": clean_text(negative),
        "mode": "image" if image is not None else "text",
        "image_name": None,
        "width": width,
        "height": height,
        "frames": frames,
        "steps": steps,
        "cfg": cfg,
        "fps": fps,
        "shift": shift,
        "sampler": sampler,
        "scheduler": scheduler,
        "seed": seed_number,
    }

    job = jobstore.create_job(params)

    if image is not None:
        raw = await image.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            jobstore.delete_job(job["id"])
            raise HTTPException(
                413, f"image is larger than {MAX_UPLOAD_BYTES // (1024*1024)} MB"
            )
        if not raw:
            jobstore.delete_job(job["id"])
            raise HTTPException(400, "the uploaded image is empty")
        try:
            name = normalise_image(raw, job["id"])
        except HTTPException:
            jobstore.delete_job(job["id"])
            raise
        jobstore.update_job(job["id"], image_name=name, mode="image")
        job["image_name"] = name

    await runner.enqueue(job["id"])
    return {"id": job["id"]}


@app.get("/api/jobs")
async def api_jobs(limit: int = 200, offset: int = 0):
    limit = max(1, min(500, limit))
    items = jobstore.list_jobs(limit=limit, offset=max(0, offset))
    for item in items:
        item["queue_position"] = runner.queue_position(item["id"])
    return {"jobs": items, "total": jobstore.count_jobs()}


@app.get("/api/jobs/{job_id}")
async def api_job(job_id: str):
    job = jobstore.get_job(job_id)
    if job is None:
        raise HTTPException(404, "no such job")
    job["queue_position"] = runner.queue_position(job_id)
    return job


@app.post("/api/jobs/{job_id}/cancel")
async def api_cancel(job_id: str):
    if not await runner.cancel(job_id):
        raise HTTPException(409, "job is not queued or running")
    return {"ok": True}


@app.delete("/api/jobs/{job_id}")
async def api_delete(job_id: str):
    if runner.current == job_id:
        raise HTTPException(409, "cannot delete a job while it is rendering")
    job = jobstore.get_job(job_id)
    if job is None:
        raise HTTPException(404, "no such job")
    # Purge the engine's own copy of the prompt before dropping our record of it.
    if job.get("prompt_id"):
        await runner.client.forget_history(job["prompt_id"])
    if not jobstore.delete_job(job_id):
        raise HTTPException(404, "no such job")
    return {"ok": True}


def safe_path(base: Path, relative: str) -> Path:
    target = (base / relative).resolve()
    if base.resolve() not in target.parents and target.parent != base.resolve():
        raise HTTPException(400, "invalid path")
    if not target.is_file():
        raise HTTPException(404, "file not found")
    return target


def ranged_file_response(path: Path, request: Request) -> Response:
    """Serve a file with Range support so the player can seek and go fullscreen."""
    size = path.stat().st_size
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    range_header = request.headers.get("range")

    if not range_header:
        return FileResponse(path, media_type=media_type,
                            headers={"Accept-Ranges": "bytes"})

    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
    if not match:
        raise HTTPException(416, "malformed Range header")

    start_raw, end_raw = match.groups()
    if start_raw:
        start = int(start_raw)
        end = int(end_raw) if end_raw else size - 1
    else:
        # Suffix form: bytes=-N means the final N bytes.
        length = int(end_raw or 0)
        start = max(0, size - length)
        end = size - 1

    if start >= size or start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    end = min(end, size - 1)

    def stream():
        remaining = end - start + 1
        with path.open("rb") as handle:
            handle.seek(start)
            while remaining > 0:
                chunk = handle.read(min(1024 * 512, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        stream(),
        status_code=206,
        media_type=media_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        },
    )


@app.get("/api/jobs/{job_id}/video")
async def api_video(job_id: str, request: Request):
    job = jobstore.get_job(job_id)
    if job is None or not job.get("video_path"):
        raise HTTPException(404, "no video for this job")
    return ranged_file_response(safe_path(OUTPUT_DIR, job["video_path"]), request)


@app.get("/api/jobs/{job_id}/download")
async def api_download(job_id: str):
    job = jobstore.get_job(job_id)
    if job is None or not job.get("video_path"):
        raise HTTPException(404, "no video for this job")
    path = safe_path(OUTPUT_DIR, job["video_path"])
    return FileResponse(path, media_type="video/mp4",
                        filename=f"{job_id}{path.suffix}")


@app.get("/api/jobs/{job_id}/thumb")
async def api_thumb(job_id: str):
    job = jobstore.get_job(job_id)
    if job is None or not job.get("thumb_path"):
        raise HTTPException(404, "no thumbnail")
    return FileResponse(safe_path(THUMB_DIR, job["thumb_path"]),
                        media_type="image/jpeg")


@app.get("/api/jobs/{job_id}/source")
async def api_source(job_id: str):
    job = jobstore.get_job(job_id)
    if job is None or not job.get("image_name"):
        raise HTTPException(404, "this job had no input image")
    return FileResponse(safe_path(UPLOAD_DIR, job["image_name"]),
                        media_type="image/png")


app.mount("/", StaticFiles(directory=SERVICE_DIR / "static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=UI_HOST, port=UI_PORT, log_level="info")
