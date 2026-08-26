"""Wan video pipelines.

wan22-ti2v-5b is the quality option (720p native, 24 fps, 5s at 121 frames).
wan21-fun-inp-1.3b is the fast drafting option (16 fps, so 5s is 81 frames).
"""

from __future__ import annotations

import copy
import json

from config import API_WORKFLOW, ROOT

from .base import ComfyPipeline, Param, register

DEFAULT_NEGATIVE = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
    "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
    "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
    "杂乱的背景，三条腿，背景人很多，倒着走"
)

SAMPLERS = ["uni_pc", "euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "ddim"]
SCHEDULERS = ["simple", "normal", "karras", "beta", "sgm_uniform"]

_template_cache: dict | None = None


def snap16(value: int) -> int:
    """Wan's VAE needs both dimensions on a multiple of 16."""
    return max(128, min(4096, round(value / 16) * 16))


def snap_frames(value: int) -> int:
    """Wan's latent layout needs length = 4n + 1."""
    value = max(5, min(1001, int(value)))
    return value - ((value - 1) % 4)


def _template() -> dict:
    global _template_cache
    if _template_cache is None:
        if not API_WORKFLOW.exists():
            raise FileNotFoundError(
                f"missing {API_WORKFLOW}. Regenerate with ./scripts/workflow-to-api"
            )
        _template_cache = json.loads(API_WORKFLOW.read_text())
    return copy.deepcopy(_template_cache)


def build_wan22(p: dict, files: dict[str, str]) -> dict:
    graph = _template()
    graph["6"]["inputs"]["text"] = p["prompt"]
    graph["7"]["inputs"]["text"] = p["negative"]

    latent = graph["55"]["inputs"]
    latent.update(width=p["width"], height=p["height"], length=p["frames"],
                  batch_size=1)

    sampler = graph["3"]["inputs"]
    sampler.update(seed=p["seed"], steps=p["steps"], cfg=p["cfg"],
                   sampler_name=p["sampler"], scheduler=p["scheduler"])

    graph["48"]["inputs"]["shift"] = p["shift"]
    graph["57"]["inputs"]["fps"] = p["fps"]
    graph["58"]["inputs"]["filename_prefix"] = f"video/{p['job_id']}"

    if files.get("image"):
        graph["56"] = {"class_type": "LoadImage",
                       "inputs": {"image": files["image"]}}
        latent["start_image"] = ["56", 0]
    else:
        latent.pop("start_image", None)
        graph.pop("56", None)
    return graph


VIDEO_COMMON = [
    Param("prompt", "str", required=True,
          help="Describe the motion, not just the scene."),
    Param("negative", "str", default=DEFAULT_NEGATIVE),
    Param("width", "int", default=512, minimum=128, maximum=4096, snap=snap16),
    Param("height", "int", default=288, minimum=128, maximum=4096, snap=snap16),
    Param("frames", "int", default=41, minimum=5, maximum=1001, snap=snap_frames,
          help="Length in frames; 4n+1. Seconds = frames / fps."),
    Param("steps", "int", default=20, minimum=1, maximum=60),
    Param("cfg", "float", default=5.0, minimum=0.0, maximum=20.0),
    Param("shift", "float", default=8.0, minimum=0.0, maximum=20.0),
    Param("sampler", "enum", default="uni_pc", choices=SAMPLERS),
    Param("scheduler", "enum", default="simple", choices=SCHEDULERS),
    Param("seed", "int", default=None),
]

register(ComfyPipeline(
    id="wan22-video",
    kind="video",
    title="Wan 2.2 TI2V-5B video",
    description="OUT OF SCOPE — do not plan around this. Weights are not installed and "
                "should not be downloaded: generation time did not justify the result "
                "for a still-panel product, and motion belongs to the orchestrator "
                "(pan/zoom over panels). Left registered as an escape hatch only. "
                "Text or image to video, 720p at 24 fps, up to 121 frames (5s).",
    requires_profile="wan22-ti2v-5b",
    accepts_files=["image"],
    params=VIDEO_COMMON + [Param("fps", "int", default=24, minimum=1, maximum=60)],
    build=build_wan22,
))
