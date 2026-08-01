"""Job store and the serialized worker.

One GPU means one job at a time; everything else queues. History lives in SQLite so it
survives restarts of both this service and ComfyUI.

Jobs are pipeline-agnostic: `pipeline` names the capability, `params` holds its typed
inputs, `outputs` holds the produced files. Adding a capability needs no schema change.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import pipelines
from comfy_client import ComfyClient, ComfyError, outputs_from_history
from config import DATA_DIR, DB_PATH, INPUT_DIR, OUTPUT_DIR, THUMB_DIR

UPLOAD_DIR = DATA_DIR / "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    created_at   REAL NOT NULL,
    started_at   REAL,
    finished_at  REAL,
    status       TEXT NOT NULL,
    progress     REAL NOT NULL DEFAULT 0,
    stage        TEXT,
    pipeline     TEXT NOT NULL,
    kind         TEXT NOT NULL,
    params       TEXT NOT NULL DEFAULT '{}',
    files        TEXT NOT NULL DEFAULT '{}',
    outputs      TEXT NOT NULL DEFAULT '[]',
    thumb        TEXT,
    prompt_id    TEXT,
    error        TEXT
);
CREATE INDEX IF NOT EXISTS jobs_created_at ON jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS jobs_kind ON jobs (kind);
"""

JSON_COLUMNS = ("params", "files", "outputs")

VIDEO_EXT = (".mp4", ".webm", ".mkv", ".mov")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def purge_database() -> None:
    """Reclaim deleted rows from the database AND its write-ahead log.

    VACUUM alone is not enough: in WAL mode a deleted row's bytes stay readable in
    app.db-wal until the log is checkpointed and truncated.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.isolation_level = None  # VACUUM cannot run inside a transaction
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    job = {key: row[key] for key in row.keys()}
    for column in JSON_COLUMNS:
        default = "[]" if column == "outputs" else "{}"
        try:
            job[column] = json.loads(job[column] or default)
        except json.JSONDecodeError:
            job[column] = [] if column == "outputs" else {}
    if job.get("started_at") and job.get("finished_at"):
        job["duration"] = round(job["finished_at"] - job["started_at"], 2)
    else:
        job["duration"] = None
    return job


def create_job(pipeline_id: str, kind: str, params: dict, files: dict) -> dict:
    job_id = uuid.uuid4().hex[:12]
    record = {
        "id": job_id,
        "created_at": time.time(),
        "status": "queued",
        "progress": 0.0,
        "stage": "queued",
        "pipeline": pipeline_id,
        "kind": kind,
        "params": json.dumps(params, ensure_ascii=False),
        "files": json.dumps(files, ensure_ascii=False),
        "outputs": "[]",
    }
    with connect() as conn:
        conn.execute(
            "INSERT INTO jobs (id, created_at, status, progress, stage, pipeline, kind, "
            "params, files, outputs) VALUES (:id, :created_at, :status, :progress, "
            ":stage, :pipeline, :kind, :params, :files, :outputs)",
            record,
        )
    return get_job(job_id)


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    for column in JSON_COLUMNS:
        if column in fields and not isinstance(fields[column], str):
            fields[column] = json.dumps(fields[column], ensure_ascii=False)
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with connect() as conn:
        conn.execute(f"UPDATE jobs SET {assignments} WHERE id = ?",
                     (*fields.values(), job_id))


def get_job(job_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return row_to_dict(row) if row else None


def list_jobs(limit: int = 200, offset: int = 0, kind: str | None = None,
              status: str | None = None) -> list[dict[str, Any]]:
    clauses, args = [], []
    if kind:
        clauses.append("kind = ?")
        args.append(kind)
    if status:
        clauses.append("status = ?")
        args.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*args, limit, offset),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def count_jobs(kind: str | None = None) -> int:
    with connect() as conn:
        if kind:
            return conn.execute("SELECT COUNT(*) FROM jobs WHERE kind = ?",
                                (kind,)).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def _unlink_under(base: Path, relative: str | None) -> None:
    """Delete `relative` inside `base`, refusing anything that escapes it."""
    if not relative:
        return
    base = base.resolve()
    target = (base / relative).resolve()
    if target == base or (base not in target.parents and target.parent != base):
        return
    if target.is_file():
        target.unlink(missing_ok=True)


def delete_job(job_id: str) -> bool:
    """Remove a job and every trace of it this service controls.

    Outputs, thumbnail, uploads (ours and ComfyUI's copy), the history row holding the
    prompt, and the free pages plus write-ahead log that would otherwise keep it
    readable. ComfyUI's in-memory history is purged by the caller, which holds the client.
    """
    job = get_job(job_id)
    if job is None:
        return False

    for relative in job.get("outputs") or []:
        _unlink_under(OUTPUT_DIR, relative)
    _unlink_under(THUMB_DIR, job.get("thumb"))
    for name in (job.get("files") or {}).values():
        _unlink_under(UPLOAD_DIR, name)
        _unlink_under(INPUT_DIR, name)

    with connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    purge_database()
    return True


def make_thumbnail(source: Path, job_id: str) -> str | None:
    """First frame for video, downscaled copy for images. Returns a THUMB_DIR name."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    out = THUMB_DIR / f"{job_id}.jpg"
    suffix = source.suffix.lower()
    if suffix in VIDEO_EXT:
        args = ["-i", str(source), "-frames:v", "1", "-vf", "scale=480:-2"]
    elif suffix in IMAGE_EXT:
        args = ["-i", str(source), "-vf", "scale=480:-2"]
    else:
        return None
    result = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, str(out)],
                            capture_output=True)
    return out.name if result.returncode == 0 and out.exists() else None


class Runner:
    """Owns the queue and the single worker task."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.client = ComfyClient()
        self.current: str | None = None
        self._task: asyncio.Task | None = None
        self._cancelled: set[str] = set()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.client.close()

    def fail_orphans(self) -> None:
        """After a restart, anything mid-flight can never resume: mark it failed."""
        with connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'error', "
                "error = 'interrupted by a service restart', finished_at = ? "
                "WHERE status IN ('running', 'queued')",
                (time.time(),),
            )

    async def enqueue(self, job_id: str) -> None:
        await self.queue.put(job_id)

    async def cancel(self, job_id: str) -> bool:
        job = get_job(job_id)
        if job is None or job["status"] not in ("queued", "running"):
            return False
        self._cancelled.add(job_id)
        if job["status"] == "running" and self.current == job_id:
            await self.client.interrupt()
        else:
            update_job(job_id, status="cancelled", finished_at=time.time())
        return True

    def queue_position(self, job_id: str) -> int | None:
        if self.current == job_id:
            return 0
        pending = list(self.queue._queue)  # noqa: SLF001 - inspection only
        return pending.index(job_id) + 1 if job_id in pending else None

    async def _loop(self) -> None:
        while True:
            job_id = await self.queue.get()
            if job_id in self._cancelled:
                self._cancelled.discard(job_id)
                update_job(job_id, status="cancelled", finished_at=time.time())
                self.queue.task_done()
                continue
            self.current = job_id
            try:
                await self._run_one(job_id)
            except asyncio.CancelledError:
                update_job(job_id, status="error", error="service shut down",
                           finished_at=time.time())
                raise
            except Exception as exc:  # noqa: BLE001 - surface everything to the API
                update_job(job_id, status="error", error=str(exc),
                           finished_at=time.time())
            finally:
                self.current = None
                self._cancelled.discard(job_id)
                self.queue.task_done()

    async def _run_one(self, job_id: str) -> None:
        job = get_job(job_id)
        if job is None:
            return
        pipeline = pipelines.get(job["pipeline"])
        if pipeline is None:
            raise ValueError(f"unknown pipeline '{job['pipeline']}'")

        update_job(job_id, status="running", started_at=time.time(), progress=0.0,
                   stage="starting")

        if isinstance(pipeline, pipelines.LocalPipeline):
            await self._run_local(job, pipeline)
        else:
            await self._run_comfy(job, pipeline)

    # ------------------------------------------------------------------ local

    async def _run_local(self, job: dict, pipeline: pipelines.LocalPipeline) -> None:
        job_id = job["id"]
        params = dict(job["params"], job_id=job_id)
        files = {key: UPLOAD_DIR / name for key, name in (job["files"] or {}).items()}

        loop = asyncio.get_running_loop()
        last = 0.0

        def progress(fraction: float, stage: str) -> None:
            nonlocal last
            now = time.time()
            if now - last >= 0.4 or fraction >= 1.0:
                last = now
                update_job(job_id, progress=round(fraction, 4), stage=stage)

        # These models are synchronous and CPU/GPU bound: keep the event loop free.
        produced = await loop.run_in_executor(None, pipeline.run, params, files, progress)

        outputs = [str(Path(path).relative_to(OUTPUT_DIR)) for path in produced]
        thumb = None
        for path in produced:
            thumb = make_thumbnail(Path(path), job_id)
            if thumb:
                break
        update_job(job_id, status="done", progress=1.0, stage="done",
                   outputs=outputs, thumb=thumb, finished_at=time.time())

    # ------------------------------------------------------------------ comfy

    async def _run_comfy(self, job: dict, pipeline: pipelines.ComfyPipeline) -> None:
        job_id = job["id"]
        if not await self.client.reachable():
            raise ComfyError(
                "ComfyUI is not responding on its configured host. "
                "Start it with ./scripts/comfy.sh wan"
            )

        # Push every uploaded file into ComfyUI's input directory.
        update_job(job_id, stage="uploading inputs")
        remote: dict[str, str] = {}
        for key, name in (job["files"] or {}).items():
            staged = UPLOAD_DIR / name
            if not staged.exists():
                raise ComfyError(f"uploaded file {name} is missing")
            remote[key] = await self.client.upload_image(staged.read_bytes(), name)

        params = dict(job["params"], job_id=job_id)
        graph = pipeline.build(params, remote)

        update_job(job_id, stage="queued in engine")
        prompt_id = await self.client.submit(graph)
        update_job(job_id, prompt_id=prompt_id, stage="sampling")

        last = 0.0

        def on_progress(fraction: float, _node: str | None) -> None:
            nonlocal last
            now = time.time()
            if now - last >= 0.5 or fraction >= 1.0:
                last = now
                update_job(job_id, progress=round(fraction, 4))

        try:
            entry = await self.client.watch(prompt_id, on_progress)
        except ComfyError as exc:
            if "interrupt" in str(exc).lower() or job_id in self._cancelled:
                update_job(job_id, status="cancelled", finished_at=time.time())
                return
            raise

        produced = outputs_from_history(entry)
        if not produced:
            raise ComfyError("the job finished but produced no files")

        outputs, first_path = [], None
        for item in produced:
            subfolder = item.get("subfolder") or ""
            relative = f"{subfolder}/{item['filename']}" if subfolder else item["filename"]
            absolute = OUTPUT_DIR / relative
            if not absolute.exists():
                continue
            outputs.append(relative)
            first_path = first_path or absolute

        if not outputs:
            raise ComfyError("ComfyUI reported outputs that are not present in output/")

        update_job(job_id, stage="thumbnailing")
        thumb = make_thumbnail(first_path, job_id) if first_path else None
        update_job(job_id, status="done", progress=1.0, stage="done",
                   outputs=outputs, thumb=thumb, finished_at=time.time())
