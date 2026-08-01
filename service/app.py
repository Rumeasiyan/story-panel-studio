"""Local generation API.

Serves image generation, image editing, video, narration and subtitles over one
pipeline-agnostic REST interface. It generates; it does not orchestrate. A caller
queues jobs, polls them, and collects the files.

    ./scripts/serve.sh          then http://127.0.0.1:8189/  and  /docs

No authentication. Bind beyond loopback only on a network you trust.
"""

from __future__ import annotations

import io
import mimetypes
import random
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
# Starlette's UploadFile, not FastAPI's subclass: form.multi_items() yields the parent
# type, so isinstance() against the subclass silently discards every upload.
from starlette.datastructures import UploadFile

import jobs as jobstore
import pipelines
from config import (
    DATA_DIR,
    MAX_UPLOAD_BYTES,
    MODELS_DIR,
    OUTPUT_DIR,
    SERVICE_DIR,
    THUMB_DIR,
    UI_HOST,
    UI_PORT,
)

UPLOAD_DIR = DATA_DIR / "uploads"

AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}

runner = jobstore.Runner()


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobstore.init_db()
    for directory in (UPLOAD_DIR, THUMB_DIR, OUTPUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    runner.fail_orphans()
    runner.start()
    yield
    await runner.stop()


app = FastAPI(
    title="ai-video-gen generation API",
    description=__doc__,
    version="2.0.0",
    lifespan=lifespan,
)


# ------------------------------------------------------------------ validation

def coerce(param: pipelines.Param, raw):
    """Validate and normalise one parameter. Raises HTTPException on bad input."""
    if raw is None or raw == "":
        if param.required:
            raise HTTPException(400, f"'{param.name}' is required")
        return param.default

    try:
        if param.type == "int":
            value = int(float(raw))
        elif param.type == "float":
            value = float(raw)
        elif param.type == "bool":
            value = str(raw).strip().lower() in ("1", "true", "yes", "on")
        else:
            value = str(raw).strip()
    except (TypeError, ValueError):
        raise HTTPException(400, f"'{param.name}' must be a {param.type}") from None

    if param.type == "enum" and param.choices and value not in param.choices:
        raise HTTPException(
            400, f"'{param.name}' must be one of: {', '.join(map(str, param.choices))}"
        )
    if param.type in ("int", "float"):
        if param.minimum is not None and value < param.minimum:
            value = param.minimum
        if param.maximum is not None and value > param.maximum:
            value = param.maximum
    if param.type == "str":
        value = value[:20000]
    if param.snap:
        value = param.snap(value)
    return value


def normalise_upload(raw: bytes, key: str, filename: str, job_stem: str) -> str:
    """Store an upload safely. Images are re-encoded; audio is size-checked only."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"'{key}' exceeds {MAX_UPLOAD_BYTES // (1024*1024)} MB")
    if not raw:
        raise HTTPException(400, f"'{key}' is empty")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename or "").suffix.lower()

    if suffix in AUDIO_SUFFIXES:
        name = f"{job_stem}_{key}{suffix}"
        (UPLOAD_DIR / name).write_bytes(raw)
        return name

    # Anything else must be a decodable image; re-encode rather than trust it.
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"'{key}' is not a readable image: {exc}") from exc
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGB")
    if max(image.size) > 4096:
        image.thumbnail((4096, 4096))
    name = f"{job_stem}_{key}.png"
    image.save(UPLOAD_DIR / name, format="PNG")
    return name


# --------------------------------------------------------------------- routes

@app.get("/api/pipelines", summary="List generation capabilities and their parameters")
async def list_pipelines(kind: str | None = None):
    items = [p.describe() for p in pipelines.all_pipelines()
             if kind is None or p.kind == kind]
    return {"pipelines": items}


@app.get("/api/pipelines/{pipeline_id}")
async def describe_pipeline(pipeline_id: str):
    pipeline = pipelines.get(pipeline_id)
    if pipeline is None:
        raise HTTPException(404, f"unknown pipeline '{pipeline_id}'")
    return pipeline.describe()


@app.get("/api/status", summary="Engine reachability, GPU and queue depth")
async def status():
    stats = await runner.client.system_stats()
    gpu = None
    if stats and (stats.get("devices") or []):
        device = stats["devices"][0]
        gpu = {"name": device.get("name"), "vram_total": device.get("vram_total"),
               "vram_free": device.get("vram_free")}
    return {
        "comfy_up": stats is not None,
        "comfy_version": (stats or {}).get("system", {}).get("comfyui_version"),
        "gpu": gpu,
        "current": runner.current,
        "queued": runner.queue.qsize(),
        "total_jobs": jobstore.count_jobs(),
        "pipelines": [p.id for p in pipelines.all_pipelines()],
    }


@app.post("/api/generate", summary="Queue a generation job")
async def generate(request: Request):
    """Accepts multipart/form-data or JSON.

    Required field: `pipeline`. Everything else is that pipeline's parameters, plus any
    files it accepts (multipart only). Returns immediately with a job id — poll
    /api/jobs/{id} for progress.
    """
    uploads: dict[str, UploadFile] = {}
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        raw = {}
        for key, value in form.multi_items():
            if isinstance(value, UploadFile):
                uploads[key] = value
            else:
                raw[key] = value
    else:
        try:
            raw = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "body must be JSON or multipart/form-data") from None
        if not isinstance(raw, dict):
            raise HTTPException(400, "JSON body must be an object")

    pipeline_id = raw.get("pipeline")
    if not pipeline_id:
        raise HTTPException(
            400, "'pipeline' is required. See GET /api/pipelines for the options."
        )
    pipeline = pipelines.get(pipeline_id)
    if pipeline is None:
        known = ", ".join(p.id for p in pipelines.all_pipelines())
        raise HTTPException(400, f"unknown pipeline '{pipeline_id}'. Known: {known}")

    params: dict = {}
    for param in pipeline.params:
        params[param.name] = coerce(param, raw.get(param.name))

    # A seed is always concrete in the record, so any job can be reproduced exactly.
    if "seed" in params and params["seed"] in (None, "", -1):
        params["seed"] = random.randint(0, 2**63 - 1)

    for key in uploads:
        if key not in pipeline.accepts_files:
            raise HTTPException(
                400,
                f"'{pipeline_id}' does not accept a file called '{key}'. "
                f"Accepted: {', '.join(pipeline.accepts_files) or 'none'}",
            )

    job = jobstore.create_job(pipeline_id, pipeline.kind, params, {})

    files: dict[str, str] = {}
    try:
        for key, upload in uploads.items():
            files[key] = normalise_upload(
                await upload.read(), key, upload.filename or "", job["id"]
            )
    except HTTPException:
        jobstore.delete_job(job["id"])
        raise

    if files:
        jobstore.update_job(job["id"], files=files)

    await runner.enqueue(job["id"])
    return {"id": job["id"], "pipeline": pipeline_id, "kind": pipeline.kind,
            "status": "queued", "params": params}


@app.get("/api/jobs", summary="List jobs, newest first")
async def api_jobs(limit: int = 100, offset: int = 0,
                   kind: str | None = None, status: str | None = None):
    limit = max(1, min(500, limit))
    items = jobstore.list_jobs(limit=limit, offset=max(0, offset),
                               kind=kind, status=status)
    for item in items:
        item["queue_position"] = runner.queue_position(item["id"])
    return {"jobs": items, "total": jobstore.count_jobs(kind)}


@app.get("/api/jobs/{job_id}", summary="One job, including progress and outputs")
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


@app.delete("/api/jobs/{job_id}", summary="Delete a job and every trace of it")
async def api_delete(job_id: str):
    if runner.current == job_id:
        raise HTTPException(409, "cannot delete a job while it is running")
    job = jobstore.get_job(job_id)
    if job is None:
        raise HTTPException(404, "no such job")
    if job.get("prompt_id"):
        await runner.client.forget_history(job["prompt_id"])
    jobstore.delete_job(job_id)
    return {"ok": True}


def safe_path(base: Path, relative: str) -> Path:
    base = base.resolve()
    target = (base / relative).resolve()
    if base not in target.parents and target.parent != base:
        raise HTTPException(400, "invalid path")
    if not target.is_file():
        raise HTTPException(404, "file not found")
    return target


def ranged_response(path: Path, request: Request) -> Response:
    """Serve with Range support so players can seek."""
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
        start = max(0, size - int(end_raw or 0))
        end = size - 1
    if start >= size or start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    end = min(end, size - 1)

    def stream():
        remaining = end - start + 1
        with path.open("rb") as handle:
            handle.seek(start)
            while remaining > 0:
                chunk = handle.read(min(512 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        stream(), status_code=206, media_type=media_type,
        headers={"Content-Range": f"bytes {start}-{end}/{size}",
                 "Accept-Ranges": "bytes", "Content-Length": str(end - start + 1)},
    )


def job_outputs(job_id: str) -> tuple[dict, list[str]]:
    job = jobstore.get_job(job_id)
    if job is None:
        raise HTTPException(404, "no such job")
    outputs = job.get("outputs") or []
    if not outputs:
        raise HTTPException(404, "this job has produced no output")
    return job, outputs


@app.get("/api/jobs/{job_id}/output", summary="Fetch an output file")
async def api_output(job_id: str, request: Request, index: int = 0,
                     download: bool = False):
    _job, outputs = job_outputs(job_id)
    if index < 0 or index >= len(outputs):
        raise HTTPException(404, f"index out of range; this job has {len(outputs)}")
    path = safe_path(OUTPUT_DIR, outputs[index])
    if download:
        return FileResponse(path, filename=f"{job_id}_{index}{path.suffix}")
    return ranged_response(path, request)


@app.get("/api/jobs/{job_id}/outputs", summary="List a job's output files")
async def api_output_list(job_id: str):
    job, outputs = job_outputs(job_id)
    return {
        "id": job_id,
        "kind": job["kind"],
        "outputs": [
            {"index": i, "path": relative,
             "url": f"/api/jobs/{job_id}/output?index={i}",
             "bytes": (OUTPUT_DIR / relative).stat().st_size
             if (OUTPUT_DIR / relative).exists() else None}
            for i, relative in enumerate(outputs)
        ],
    }


@app.get("/api/jobs/{job_id}/thumb")
async def api_thumb(job_id: str):
    job = jobstore.get_job(job_id)
    if job is None or not job.get("thumb"):
        raise HTTPException(404, "no thumbnail")
    return FileResponse(safe_path(THUMB_DIR, job["thumb"]), media_type="image/jpeg")


@app.get("/api/jobs/{job_id}/input")
async def api_input(job_id: str, key: str = "image"):
    job = jobstore.get_job(job_id)
    if job is None:
        raise HTTPException(404, "no such job")
    name = (job.get("files") or {}).get(key)
    if not name:
        raise HTTPException(404, f"this job had no '{key}' input")
    return FileResponse(safe_path(UPLOAD_DIR, name))


@app.get("/api/loras", summary="Character/style LoRAs available to SDXL")
async def api_loras():
    directory = MODELS_DIR / "loras"
    names = sorted(p.name for p in directory.glob("*.safetensors")) \
        if directory.exists() else []
    return {"loras": names}


app.mount("/", StaticFiles(directory=SERVICE_DIR / "static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=UI_HOST, port=UI_PORT, log_level="info")
