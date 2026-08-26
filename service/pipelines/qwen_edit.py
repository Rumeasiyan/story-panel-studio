"""Qwen-Image-Edit — the compositional editor the other pipelines cannot be.

`flux2-edit` restyles a whole frame and `sdxl-inpaint` repaints a masked region. Neither
can take two photographs of two different people and put *those* people somewhere new,
doing something new, faces intact, with no mask. That is what this is for.

It is a 20B model on an 8 GB card, so it runs as a GGUF quant streamed from system RAM
rather than held on the GPU. Expect minutes per image, not seconds — it is a hero-shot
tool, not a panel factory. Everything routine stays on the locked SDXL and FLUX.2 paths;
see config/generation-locks.yaml.

Apache-2.0, which is why it is viable here at all — FLUX.2-dev and HunyuanImage are
larger *and* non-commercial.
"""

from __future__ import annotations

from .base import ComfyPipeline, Param, register

UNET = "qwen-image-edit-2511-Q4_K_M.gguf"
TEXT_ENCODER = "qwen_2.5_vl_7b_nvfp4.safetensors"
VAE = "qwen_image_vae.safetensors"

# Node names verified against this ComfyUI: UnetLoaderGGUF comes from the pinned
# comfyui-gguf node, the rest are native.
MAX_REFERENCES = 3


def build_edit(p: dict, files: dict[str, str]) -> dict:
    """Compose an edit conditioned on up to three reference images.

    TextEncodeQwenImageEditPlus takes image1..image3 directly, which is what makes the
    two-subject case possible: each person is a separate reference rather than something
    the model has to disentangle from one composite.
    """
    graph: dict = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": UNET}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": TEXT_ENCODER, "type": "qwen_image"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
    }

    encode_inputs = {"clip": ["2", 0], "prompt": p["prompt"], "vae": ["3", 0]}
    keys = ["image", "reference_2", "reference_3"]
    loaded = 0
    for index, key in enumerate(keys, start=1):
        name = files.get(key)
        if not name:
            continue
        node = str(10 + index)
        graph[node] = {"class_type": "LoadImage", "inputs": {"image": name}}
        encode_inputs[f"image{index}"] = [node, 0]
        loaded += 1

    if not loaded:
        raise ValueError(
            "this pipeline edits existing images — supply at least 'image'. "
            "For generation from a prompt alone use flux2-text-to-image or "
            "sdxl-text-to-image."
        )

    graph["20"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": encode_inputs}
    graph["21"] = {"class_type": "TextEncodeQwenImageEditPlus",
                   "inputs": {"clip": ["2", 0], "prompt": p.get("negative") or "",
                              "vae": ["3", 0]}}
    graph["30"] = {"class_type": "EmptySD3LatentImage",
                   "inputs": {"width": p["width"], "height": p["height"],
                              "batch_size": 1}}
    graph["40"] = {
        "class_type": "KSampler",
        "inputs": {"model": ["1", 0], "positive": ["20", 0], "negative": ["21", 0],
                   "latent_image": ["30", 0], "seed": p["seed"], "steps": p["steps"],
                   "cfg": p["cfg"], "sampler_name": "euler", "scheduler": "simple",
                   "denoise": 1.0},
    }
    graph["50"] = {"class_type": "VAEDecode",
                   "inputs": {"samples": ["40", 0], "vae": ["3", 0]}}
    graph["60"] = {"class_type": "SaveImage",
                   "inputs": {"images": ["50", 0],
                              "filename_prefix": f"image/{p['job_id']}"}}
    return graph


register(ComfyPipeline(
    id="qwen-image-edit",
    kind="image",
    title="Qwen-Image-Edit 2511 (compositional edit, slow)",
    description="Put specific people or objects from reference images into a new scene, "
                "pose or interaction, without a mask. Takes up to three references. "
                "20B streamed from system RAM on this machine: MINUTES per image, so "
                "use it for shots the locked pipelines cannot do, not for panels.",
    requires_profile="qwen-image-edit-2511",
    accepts_files=["image", "reference_2", "reference_3"],
    params=[
        Param("prompt", "str", required=True,
              help="Describe the finished image, referring to the inputs — e.g. 'the "
                   "man from image 1 and the woman from image 2 embracing on a beach "
                   "at sunset, keep both faces exactly'."),
        Param("negative", "str", default=""),
        Param("steps", "int", default=20, minimum=1, maximum=50),
        Param("cfg", "float", default=2.5, minimum=0.0, maximum=10.0),
        Param("seed", "int", default=None),
        Param("width", "int", default=1024, minimum=256, maximum=1536),
        Param("height", "int", default=1024, minimum=256, maximum=1536),
    ],
    build=build_edit,
))
