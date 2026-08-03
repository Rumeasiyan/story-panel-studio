"""Z-Image Turbo: fast few-step text-to-image.

The int8 variant, which ComfyUI drives natively — no GGUF custom node needed. It shares
the qwen_3_4b text encoder with FLUX.2 klein, so only the transformer and its own VAE
are extra on disk.

Distilled for very few steps (8 is the design point), which makes it the cheapest
full-quality generator here after the Lightning-LoRA'd SDXL.
"""

from __future__ import annotations

from .base import ComfyPipeline, Param, register

MODEL = "z_image_turbo_int8_convrot.safetensors"
TEXT_ENCODER = "qwen_3_4b.safetensors"
VAE = "ae.safetensors"


def snap16(value: int) -> int:
    return max(256, min(2048, round(value / 16) * 16))


def build(p: dict, files: dict[str, str]) -> dict:
    graph = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": MODEL, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": TEXT_ENCODER, "type": "z_image",
                         "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": p["prompt"]}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": p["negative"]}},
        "7": {"class_type": "EmptyLatentImage",
              "inputs": {"width": p["width"], "height": p["height"],
                         "batch_size": p["batch_size"]}},
        "10": {"class_type": "KSampler",
               "inputs": {"model": ["1", 0], "positive": ["5", 0],
                          "negative": ["6", 0], "latent_image": ["7", 0],
                          "seed": p["seed"], "steps": p["steps"], "cfg": p["cfg"],
                          "sampler_name": p["sampler"], "scheduler": p["scheduler"],
                          "denoise": 1.0}},
        "11": {"class_type": "VAEDecode",
               "inputs": {"samples": ["10", 0], "vae": ["3", 0]}},
        "12": {"class_type": "SaveImage",
               "inputs": {"images": ["11", 0],
                          "filename_prefix": f"image/{p['job_id']}"}},
    }
    return graph


register(ComfyPipeline(
    id="z-image-text-to-image",
    kind="image",
    title="Z-Image Turbo text to image",
    description="Fast few-step generation. 8 steps is the design point; low cfg. "
                "Shares the qwen_3_4b encoder with FLUX.2.",
    requires_profile="z-image-turbo",
    params=[
        Param("prompt", "str", required=True),
        Param("negative", "str", default=""),
        Param("steps", "int", default=8, minimum=1, maximum=50),
        Param("cfg", "float", default=1.0, minimum=0.0, maximum=10.0),
        Param("sampler", "enum", default="euler",
              choices=["euler", "euler_ancestral", "dpmpp_2m", "res_multistep"]),
        Param("scheduler", "enum", default="simple",
              choices=["simple", "normal", "sgm_uniform", "beta", "karras"]),
        Param("seed", "int", default=None),
        Param("batch_size", "int", default=1, minimum=1, maximum=4),
        Param("width", "int", default=1024, minimum=256, maximum=2048, snap=snap16),
        Param("height", "int", default=1024, minimum=256, maximum=2048, snap=snap16),
    ],
    build=build,
))
