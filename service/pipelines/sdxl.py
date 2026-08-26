"""SDXL pipelines: text-to-image, image-to-image, and inpainting.

Graphs are built here rather than loaded from a template because SDXL's graph is small
and fully known. Model input is restricted to checkpoints declared in CHECKPOINTS, so a
caller cannot point the loader at an arbitrary file on disk.
"""

from __future__ import annotations

from .base import ComfyPipeline, Param, register

# Only these checkpoints may be selected. Keys are stable ids for the API; values are
# the exact filenames ComfyUI resolves through config/extra_model_paths.yaml.
CHECKPOINTS = {
    "anime": "Illustrious-XL-v2.0.safetensors",
    "cinematic": "RealVisXL_V4.0.safetensors",
}

# Illustrious is trained on booru tagging: it expects comma-separated tags
# ("1girl, long hair, city street, night") rather than the prose RealVis handles well.
# Same pipeline, different prompting style.
BOORU_CHECKPOINTS = {"anime"}

SAMPLERS = ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_sde",
            "uni_pc", "ddim", "lcm"]
SCHEDULERS = ["normal", "karras", "exponential", "sgm_uniform", "simple", "beta"]

DEFAULT_NEGATIVE = (
    "lowres, bad anatomy, bad hands, extra digits, fewer digits, cropped, worst quality, "
    "low quality, jpeg artifacts, signature, watermark, username, blurry, text, error, "
    "distorted face, deformed"
)

# SDXL's VAE works in units of 8; keeping to 64 also keeps the aspect buckets sane.
def snap8(value: int) -> int:
    return max(256, min(2048, round(value / 8) * 8))


COMMON = [
    Param("prompt", "str", required=True, help="What to draw."),
    Param("negative", "str", default=DEFAULT_NEGATIVE, help="What to avoid."),
    Param("model", "enum", default="anime", choices=list(CHECKPOINTS),
          help="Checkpoint: anime (Illustrious-XL v2.0, booru tags) or cinematic "
               "(RealVisXL V4, prose). "
               "The last two are booru-tag driven — prompt with comma-separated tags."),
    Param("steps", "int", default=25, minimum=1, maximum=100),
    Param("cfg", "float", default=6.0, minimum=0.0, maximum=20.0),
    Param("sampler", "enum", default="euler", choices=SAMPLERS),
    Param("scheduler", "enum", default="normal", choices=SCHEDULERS),
    Param("seed", "int", default=None, help="Blank or -1 picks a random seed."),
    Param("batch_size", "int", default=1, minimum=1, maximum=8,
          help="Images per request. Each costs the same as a separate render."),
    Param("lora", "str", default=None,
          help="LoRA filename from GET /api/loras. Use a trained character LoRA for "
               "consistency, or sdxl_lightning_4step_lora.safetensors for ~3x speed "
               "(then set steps=4, cfg=1.5, sampler=euler, scheduler=sgm_uniform)."),
    Param("lora_strength", "float", default=0.85, minimum=0.0, maximum=2.0),
]


def _base_graph(p: dict) -> dict:
    """Loader + prompts, shared by every SDXL variant."""
    ckpt = CHECKPOINTS[p["model"]]
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
    }
    model_src, clip_src = ["1", 0], ["1", 1]

    # A character LoRA is the reliable way to hold identity across many panels.
    if p.get("lora"):
        graph["10"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": model_src, "clip": clip_src,
                "lora_name": p["lora"],
                "strength_model": p["lora_strength"],
                "strength_clip": p["lora_strength"],
            },
        }
        model_src, clip_src = ["10", 0], ["10", 1]

    graph["2"] = {"class_type": "CLIPTextEncode",
                  "inputs": {"clip": clip_src, "text": p["prompt"]}}
    graph["3"] = {"class_type": "CLIPTextEncode",
                  "inputs": {"clip": clip_src, "text": p["negative"]}}
    graph["_model"] = model_src  # consumed by callers, stripped before submit
    return graph


def _finish(graph: dict, p: dict, latent: list, denoise: float, prefix: str) -> dict:
    model_src = graph.pop("_model")
    graph["5"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_src, "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": latent,
            "seed": p["seed"], "steps": p["steps"], "cfg": p["cfg"],
            "sampler_name": p["sampler"], "scheduler": p["scheduler"],
            "denoise": denoise,
        },
    }
    graph["6"] = {"class_type": "VAEDecode",
                  "inputs": {"samples": ["5", 0], "vae": ["1", 2]}}
    graph["7"] = {"class_type": "SaveImage",
                  "inputs": {"images": ["6", 0], "filename_prefix": prefix}}
    return graph


def build_text_to_image(p: dict, files: dict[str, str]) -> dict:
    graph = _base_graph(p)
    graph["4"] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": p["width"], "height": p["height"],
                   "batch_size": p["batch_size"]},
    }
    return _finish(graph, p, ["4", 0], 1.0, f"image/{p['job_id']}")


def build_image_to_image(p: dict, files: dict[str, str]) -> dict:
    graph = _base_graph(p)
    graph["20"] = {"class_type": "LoadImage", "inputs": {"image": files["image"]}}
    # Scale the source so the latent matches the requested output size.
    graph["21"] = {
        "class_type": "ImageScale",
        "inputs": {"image": ["20", 0], "width": p["width"], "height": p["height"],
                   "upscale_method": "lanczos", "crop": "disabled"},
    }
    graph["22"] = {"class_type": "VAEEncode",
                   "inputs": {"pixels": ["21", 0], "vae": ["1", 2]}}
    latent = ["22", 0]
    if p["batch_size"] > 1:
        graph["23"] = {"class_type": "RepeatLatentBatch",
                       "inputs": {"samples": latent, "amount": p["batch_size"]}}
        latent = ["23", 0]
    return _finish(graph, p, latent, p["denoise"], f"image/{p['job_id']}")


def build_inpaint(p: dict, files: dict[str, str]) -> dict:
    graph = _base_graph(p)
    graph["20"] = {"class_type": "LoadImage", "inputs": {"image": files["image"]}}
    graph["21"] = {"class_type": "LoadImageMask",
                   "inputs": {"image": files["mask"], "channel": "red"}}
    graph["22"] = {
        "class_type": "VAEEncodeForInpaint",
        "inputs": {"pixels": ["20", 0], "vae": ["1", 2], "mask": ["21", 0],
                   "grow_mask_by": p["grow_mask_by"]},
    }
    return _finish(graph, p, ["22", 0], 1.0, f"image/{p['job_id']}")


SIZE = [
    Param("width", "int", default=1024, minimum=256, maximum=2048, snap=snap8),
    Param("height", "int", default=1024, minimum=256, maximum=2048, snap=snap8),
]

register(ComfyPipeline(
    id="sdxl-text-to-image",
    kind="image",
    title="SDXL text to image",
    description="Generate a panel from a prompt. Anime or cinematic checkpoint, "
                "optional character LoRA.",
    requires_profile="anime-sdxl",
    params=COMMON + SIZE,
    build=build_text_to_image,
))

register(ComfyPipeline(
    id="sdxl-image-to-image",
    kind="image",
    title="SDXL image to image",
    description="Redraw an existing panel guided by a prompt. Lower denoise keeps more "
                "of the source; 0.3-0.5 preserves composition and character, 0.7+ "
                "effectively reinvents the image.",
    requires_profile="anime-sdxl",
    accepts_files=["image"],
    params=COMMON + SIZE + [
        Param("denoise", "float", default=0.55, minimum=0.05, maximum=1.0,
              help="How far from the source to travel. Lower preserves more."),
    ],
    build=build_image_to_image,
))

register(ComfyPipeline(
    id="sdxl-inpaint",
    kind="image",
    title="SDXL inpaint",
    description="Regenerate only the masked region. White in the mask marks the area "
                "to replace.",
    requires_profile="anime-sdxl",
    accepts_files=["image", "mask"],
    params=COMMON + [
        Param("grow_mask_by", "int", default=6, minimum=0, maximum=64,
              help="Feather the mask edge to blend the seam."),
    ],
    build=build_inpaint,
))
