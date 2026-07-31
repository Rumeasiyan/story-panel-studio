"""Async client for the local ComfyUI HTTP/WebSocket API."""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

import aiohttp

from config import COMFY_URL, COMFY_WS


class ComfyError(RuntimeError):
    pass


def explain_rejection(body: str, status: int) -> str:
    """Turn ComfyUI's validation JSON into one readable sentence.

    The common case by far is a missing model file, which surfaces as
    "value_not_in_list" on a loader node — worth naming explicitly so the UI can say
    what to install rather than dumping raw JSON.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return f"ComfyUI rejected the prompt (HTTP {status}): {body[:300]}"

    messages: list[str] = []
    missing_models: list[str] = []

    for node_id, node_error in (payload.get("node_errors") or {}).items():
        for item in node_error.get("errors", []) or []:
            details = item.get("details") or ""
            if item.get("type") == "value_not_in_list" and "_name:" in details:
                wanted = details.split("'")[1] if "'" in details else details
                missing_models.append(wanted)
            else:
                messages.append(f"node {node_id}: {item.get('message')} ({details})")

    if missing_models:
        names = ", ".join(dict.fromkeys(missing_models))
        return (
            f"model file not found: {names}. "
            "Install it with ./scripts/modelctl install wan22-ti2v-5b, then restart "
            "ComfyUI so it rescans models/."
        )
    if messages:
        return "; ".join(messages[:4])

    error = payload.get("error") or {}
    return error.get("message") or f"ComfyUI rejected the prompt (HTTP {status})"


class ComfyClient:
    def __init__(self) -> None:
        self.client_id = str(uuid.uuid4())
        self._session: aiohttp.ClientSession | None = None

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=10)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def reachable(self) -> bool:
        try:
            session = await self.session()
            async with session.get(f"{COMFY_URL}/system_stats", timeout=
                                   aiohttp.ClientTimeout(total=5)) as response:
                return response.status == 200
        except Exception:
            return False

    async def system_stats(self) -> dict | None:
        try:
            session = await self.session()
            async with session.get(f"{COMFY_URL}/system_stats", timeout=
                                   aiohttp.ClientTimeout(total=5)) as response:
                if response.status != 200:
                    return None
                return await response.json()
        except Exception:
            return None

    async def upload_image(self, data: bytes, filename: str) -> str:
        """Upload an image into ComfyUI's input directory; returns its reference name."""
        session = await self.session()
        form = aiohttp.FormData()
        form.add_field("image", data, filename=filename, content_type="image/png")
        form.add_field("overwrite", "true")
        async with session.post(f"{COMFY_URL}/upload/image", data=form) as response:
            if response.status != 200:
                raise ComfyError(f"image upload failed: HTTP {response.status}")
            payload = await response.json()
        name = payload.get("name") or filename
        subfolder = payload.get("subfolder") or ""
        return f"{subfolder}/{name}" if subfolder else name

    async def submit(self, graph: dict) -> str:
        """Queue a prompt; returns ComfyUI's prompt_id."""
        session = await self.session()
        body = {"prompt": graph, "client_id": self.client_id}
        async with session.post(f"{COMFY_URL}/prompt", json=body) as response:
            text = await response.text()
            if response.status != 200:
                raise ComfyError(explain_rejection(text, response.status))
            payload = json.loads(text)
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise ComfyError(f"no prompt_id in response: {payload}")
        return prompt_id

    async def interrupt(self) -> None:
        session = await self.session()
        try:
            async with session.post(f"{COMFY_URL}/interrupt") as response:
                await response.read()
        except Exception:
            pass

    async def history(self, prompt_id: str) -> dict | None:
        session = await self.session()
        async with session.get(f"{COMFY_URL}/history/{prompt_id}") as response:
            if response.status != 200:
                return None
            payload = await response.json()
        return payload.get(prompt_id)

    async def watch(
        self,
        prompt_id: str,
        on_progress: Callable[[float, str | None], Any],
    ) -> dict:
        """Follow one prompt to completion over the WebSocket.

        Calls `on_progress(fraction, node_id)` as sampling advances and returns the
        history entry for the finished prompt.
        """
        session = await self.session()
        async with session.ws_connect(
            f"{COMFY_WS}?clientId={self.client_id}", heartbeat=20
        ) as ws:
            async for message in ws:
                if message.type is not aiohttp.WSMsgType.TEXT:
                    continue
                try:
                    event = json.loads(message.data)
                except json.JSONDecodeError:
                    continue

                kind = event.get("type")
                data = event.get("data") or {}
                if data.get("prompt_id") not in (None, prompt_id):
                    continue

                if kind == "progress":
                    total = data.get("max") or 1
                    value = data.get("value") or 0
                    await _maybe_await(on_progress(value / total, data.get("node")))
                elif kind == "executing" and data.get("node") is None:
                    # node == None marks the end of this prompt's execution.
                    break
                elif kind == "execution_error":
                    raise ComfyError(
                        data.get("exception_message")
                        or f"execution error in node {data.get('node_id')}"
                    )
                elif kind in ("execution_interrupted", "execution_cached"):
                    if kind == "execution_interrupted":
                        raise ComfyError("interrupted")

        entry = await self.history(prompt_id)
        if entry is None:
            raise ComfyError("prompt finished but no history entry was returned")
        return entry


async def _maybe_await(value):
    if hasattr(value, "__await__"):
        return await value
    return value


def outputs_from_history(entry: dict) -> list[dict]:
    """Flatten every saved file recorded in a history entry."""
    files: list[dict] = []
    for node_output in (entry.get("outputs") or {}).values():
        for key in ("videos", "images", "gifs", "files"):
            for item in node_output.get(key, []) or []:
                if isinstance(item, dict) and item.get("filename"):
                    files.append(item)
    return files
