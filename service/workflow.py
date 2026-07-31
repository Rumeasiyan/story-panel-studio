"""Build a ComfyUI API payload from validated user input.

The template is fixed and lives in workflows/api/. User input only ever reaches typed
fields inside it — never the graph structure. That boundary is deliberate: ComfyUI's
/prompt endpoint executes whatever graph it is handed, so accepting a caller-supplied
graph would hand over arbitrary execution on this machine.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from config import (
    API_WORKFLOW,
    NODE_CREATE_VIDEO,
    NODE_KSAMPLER,
    NODE_LATENT,
    NODE_LOAD_IMAGE,
    NODE_MODEL_SAMPLING,
    NODE_NEGATIVE,
    NODE_POSITIVE,
    NODE_SAVE_VIDEO,
)

_template_cache: dict | None = None


def load_template() -> dict:
    global _template_cache
    if _template_cache is None:
        if not API_WORKFLOW.exists():
            raise FileNotFoundError(
                f"missing {API_WORKFLOW}. Regenerate it with:\n"
                "  ./scripts/workflow-to-api workflows/video/wan22/"
                "wan2.2_ti2v_5B_official.json -o workflows/api/wan22_ti2v_5b.json"
            )
        _template_cache = json.loads(API_WORKFLOW.read_text())
    return copy.deepcopy(_template_cache)


def build(job: dict[str, Any], image_name: str | None) -> dict:
    """Return the /prompt payload for one job.

    `image_name` is the filename ComfyUI returned from /upload/image, or None for
    text-to-video.
    """
    graph = load_template()

    graph[NODE_POSITIVE]["inputs"]["text"] = job["prompt"]
    graph[NODE_NEGATIVE]["inputs"]["text"] = job["negative"]

    latent = graph[NODE_LATENT]["inputs"]
    latent["width"] = job["width"]
    latent["height"] = job["height"]
    latent["length"] = job["frames"]
    latent["batch_size"] = 1

    sampler = graph[NODE_KSAMPLER]["inputs"]
    sampler["seed"] = job["seed"]
    sampler["steps"] = job["steps"]
    sampler["cfg"] = job["cfg"]
    sampler["sampler_name"] = job["sampler"]
    sampler["scheduler"] = job["scheduler"]

    graph[NODE_MODEL_SAMPLING]["inputs"]["shift"] = job["shift"]
    graph[NODE_CREATE_VIDEO]["inputs"]["fps"] = job["fps"]

    # One file per job, so a render is easy to trace back to its history row.
    graph[NODE_SAVE_VIDEO]["inputs"]["filename_prefix"] = f"video/{job['id']}"

    if image_name:
        # The upstream template ships with its LoadImage node muted, so the converter
        # drops it. Re-add it and wire it into the latent node for image-to-video.
        graph[NODE_LOAD_IMAGE] = {
            "class_type": "LoadImage",
            "inputs": {"image": image_name},
        }
        latent["start_image"] = [NODE_LOAD_IMAGE, 0]
    else:
        # Text-to-video: no start frame at all.
        latent.pop("start_image", None)
        graph.pop(NODE_LOAD_IMAGE, None)

    return graph
