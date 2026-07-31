"""SQLite-backed job history and the single serialized render worker.

One GPU means one render at a time. Everything else waits in a FIFO queue. History
lives in SQLite so it survives restarts of both this service and ComfyUI.
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

from comfy_client import ComfyClient, ComfyError, outputs_from_history
from config import DB_PATH, OUTPUT_DIR, THUMB_DIR
import workflow

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    created_at    REAL NOT NULL,
    started_at    REAL,
    finished_at   REAL,
    status        TEXT NOT NULL,
    progress      REAL NOT NULL DEFAULT 0,
    prompt        TEXT NOT NULL,
    negative      TEXT NOT NULL DEFAULT '',
    mode          TEXT NOT NULL DEFAULT 'text',
    image_name    TEXT,
    width         INTEGER NOT NULL,
    height        INTEGER NOT NULL,
    frames        INTEGER NOT NULL,
    steps         INTEGER NOT NULL,
    cfg           REAL NOT NULL,
    fps           INTEGER NOT NULL,
    shift         REAL NOT NULL,
    sampler       TEXT NOT NULL,
    scheduler     TEXT NOT NULL,
    seed          INTEGER NOT NULL,
    prompt_id     TEXT,
    video_path    TEXT,
    thumb_path    TEXT,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS jobs_created_at ON jobs (created_at DESC);
"""

JOB_FIELDS = (
    "id created_at started_at finished_at status progress prompt negative mode "
    "image_name width height frames steps cfg fps shift sampler scheduler seed "
    "prompt_id video_path thumb_path error"
).split()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    job = {key: row[key] for key in row.keys()}
    if job.get("video_path"):
        job["duration"] = (
            round((job["finished_at"] or 0) - (job["started_at"] or 0), 1)
            if job.get("started_at") and job.get("finished_at")
            else None
        )
    else:
        job["duration"] = None
    job["has_video"] = bool(job.get("video_path"))
    job["has_thumb"] = bool(job.get("thumb_path"))
    return job


def create_job(params: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    record = {
        "id": job_id,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "status": "queued",
        "progress": 0.0,
        "prompt_id": None,
        "video_path": None,
        "thumb_path": None,
        "error": None,
        **params,
    }
    columns = ", ".join(JOB_FIELDS)
    placeholders = ", ".join(f":{name}" for name in JOB_FIELDS)
    with connect() as conn:
        conn.execute(f"INSERT INTO jobs ({columns}) VALUES ({placeholders})", record)
    return record


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with connect() as conn:
        conn.execute(
            f"UPDATE jobs SET {assignments} WHERE id = ?",
            (*fields.values(), job_id),
        )


def get_job(job_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return row_to_dict(row) if row else None


def list_jobs(limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def count_jobs() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def delete_job(job_id: str) -> bool:
    """Remove a job and everything it produced: video, thumbnail, history row."""
    job = get_job(job_id)
    if job is None:
        return False

    for key, base in (("video_path", OUTPUT_DIR), ("thumb_path", THUMB_DIR)):
        relative = job.get(key)
        if not relative:
            continue
        target = (base / relative).resolve()
        # Never follow a path out of its own directory.
        if base.resolve() in target.parents and target.is_file():
            target.unlink(missing_ok=True)

    with connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    return True


def make_thumbnail(video: Path, job_id: str) -> str | None:
    """Grab the first frame with ffmpeg. Returns a THUMB_DIR-relative path."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    out = THUMB_DIR / f"{job_id}.jpg"
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(video),
            "-frames:v", "1",
            "-vf", "scale=480:-2",
            str(out),
        ],
        capture_output=True,
    )
    return out.name if result.returncode == 0 and out.exists() else None


class Runner:
    """Owns the queue and the one worker task."""

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

    def requeue_orphans(self) -> None:
        """After a restart, anything left mid-flight can never resume: mark it failed."""
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
        if job_id in pending:
            return pending.index(job_id) + 1
        return None

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
            except Exception as exc:  # noqa: BLE001 - surface anything to the UI
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

        update_job(job_id, status="running", started_at=time.time(), progress=0.0)

        if not await self.client.reachable():
            raise ComfyError(
                "ComfyUI is not responding on 127.0.0.1:8188. "
                "Start it with ./scripts/comfy.sh wan"
            )

        image_ref = None
        if job.get("image_name"):
            staged = THUMB_DIR.parent / "uploads" / job["image_name"]
            if not staged.exists():
                raise ComfyError(f"uploaded image {job['image_name']} is missing")
            image_ref = await self.client.upload_image(
                staged.read_bytes(), job["image_name"]
            )

        graph = workflow.build(job, image_ref)
        prompt_id = await self.client.submit(graph)
        update_job(job_id, prompt_id=prompt_id)

        last_written = 0.0

        def on_progress(fraction: float, _node: str | None) -> None:
            nonlocal last_written
            now = time.time()
            # Throttle writes; the UI polls once a second anyway.
            if now - last_written >= 0.5 or fraction >= 1.0:
                last_written = now
                update_job(job_id, progress=round(fraction, 4))

        try:
            entry = await self.client.watch(prompt_id, on_progress)
        except ComfyError as exc:
            if "interrupt" in str(exc).lower() or job_id in self._cancelled:
                update_job(job_id, status="cancelled", finished_at=time.time())
                return
            raise

        files = outputs_from_history(entry)
        video = next(
            (f for f in files if str(f.get("filename", "")).lower().endswith(
                (".mp4", ".webm", ".mkv", ".mov"))),
            None,
        )
        if video is None:
            raise ComfyError(
                "the render finished but produced no video file "
                f"(outputs: {json.dumps(files)[:300]})"
            )

        subfolder = video.get("subfolder") or ""
        relative = f"{subfolder}/{video['filename']}" if subfolder else video["filename"]
        absolute = OUTPUT_DIR / relative
        if not absolute.exists():
            raise ComfyError(f"ComfyUI reported {relative} but it is not in output/")

        thumb = make_thumbnail(absolute, job_id)
        update_job(
            job_id,
            status="done",
            progress=1.0,
            video_path=relative,
            thumb_path=thumb,
            finished_at=time.time(),
        )
