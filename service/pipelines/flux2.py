"""FLUX.2 klein 4B: text-to-image and instruction editing.

One model does both. Editing is instruction-driven — "change the background to night",
"give her a red coat" — with the rest of the frame left alone, which is what SDXL
img2img cannot do. It also accepts several reference images at once, useful for holding
a character's look across panels without training anything.

Distilled to 4 steps, so it stays usable on 8 GB despite offloading.
"""

from __future__ import annotations

from .base import ComfyPipeline, Param, register

MODEL = "flux-2-klein-4b-fp8.safetensors"
TEXT_ENCODER = "qwen_3_4b.safetensors"
# klein ships its own VAE under Apache-2.0. The otherwise-identical VAE in the
# Comfy-Org/flux2-dev repackage carries the FLUX non-commercial licence, and since the
# VAE decodes every image the model produces, its terms would govern the output. Using
# klein's own keeps the whole path Apache-2.0.
VAE = "flux2-klein-vae-apache.safetensors"

MAX_REFERENCES = 4


def snap16(value: int) -> int:
    return max(256, min(2048, round(value / 16) * 16))


def _loaders(graph: dict) -> None:
    graph["1"] = {"class_type": "UNETLoader",
                  "inputs": {"unet_name": MODEL, "weight_dtype": "default"}}
    graph["2"] = {"class_type": "CLIPLoader",
                  "inputs": {"clip_name": TEXT_ENCODER, "type": "flux2",
                             "device": "default"}}
    graph["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": VAE}}


def _sample_and_save(graph: dict, p: dict, latent: list, conditioning: list) -> dict:
    graph["10"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0],
            "positive": conditioning,
            "negative": ["6", 0],
            "latent_image": latent,
            "seed": p["seed"], "steps": p["steps"], "cfg": p["cfg"],
            "sampler_name": "euler", "scheduler": "simple",
            "denoise": p.get("denoise", 1.0),
        },
    }
    graph["11"] = {"class_type": "VAEDecode",
                   "inputs": {"samples": ["10", 0], "vae": ["3", 0]}}
    graph["12"] = {"class_type": "SaveImage",
                   "inputs": {"images": ["11", 0],
                              "filename_prefix": f"image/{p['job_id']}"}}
    return graph


def build_text_to_image(p: dict, files: dict[str, str]) -> dict:
    graph: dict = {}
    _loaders(graph)
    graph["5"] = {"class_type": "CLIPTextEncode",
                  "inputs": {"clip": ["2", 0], "text": p["prompt"]}}
    graph["6"] = {"class_type": "CLIPTextEncode",
                  "inputs": {"clip": ["2", 0], "text": ""}}
    graph["7"] = {"class_type": "EmptyLatentImage",
                  "inputs": {"width": p["width"], "height": p["height"],
                             "batch_size": p["batch_size"]}}
    return _sample_and_save(graph, p, ["7", 0], ["5", 0])


def build_edit(p: dict, files: dict[str, str]) -> dict:
    """Instruction edit, conditioned on one or more reference images."""
    graph: dict = {}
    _loaders(graph)
    graph["5"] = {"class_type": "CLIPTextEncode",
                  "inputs": {"clip": ["2", 0], "text": p["prompt"]}}
    graph["6"] = {"class_type": "CLIPTextEncode",
                  "inputs": {"clip": ["2", 0], "text": ""}}

    # Reference images: "image" is the one being edited, "reference_2".."reference_4"
    # are extra context (a character sheet, a style plate).
    refs = []
    for index, key in enumerate(["image", "reference_2", "reference_3", "reference_4"]):
        name = files.get(key)
        if not name:
            continue
        node = str(20 + index)
        graph[node] = {"class_type": "LoadImage", "inputs": {"image": name}}
        refs.append([node, 0])

    if not refs:
        raise ValueError("editing needs at least an 'image' file")

    # Chain the references into the conditioning. Order matters: each ReferenceLatent
    # wraps the previous conditioning, so the LAST one applied has the strongest pull.
    # "image" is encoded first (node 31) and is also what seeds the sampler latent, so
    # extra references act as context on top of it rather than replacing it.
    graph["30"] = {
        "class_type": "ReferenceLatent",
        "inputs": {"conditioning": ["5", 0], "latent": ["31", 0]},
    }
    graph["31"] = {"class_type": "VAEEncode",
                   "inputs": {"pixels": refs[0], "vae": ["3", 0]}}

    conditioning = ["30", 0]
    for extra_index, ref in enumerate(refs[1:], start=1):
        encode_node = f"4{extra_index}"
        ref_node = f"5{extra_index}"
        graph[encode_node] = {"class_type": "VAEEncode",
                              "inputs": {"pixels": ref, "vae": ["3", 0]}}
        graph[ref_node] = {
            "class_type": "ReferenceLatent",
            "inputs": {"conditioning": conditioning, "latent": [encode_node, 0]},
        }
        conditioning = [ref_node, 0]

    # Output size follows the edited image unless the caller overrides it.
    #
    # An empty latent throws the source away. That is fine at denoise 1.0, where the
    # result is regenerated from the conditioning anyway, but it makes a partial-denoise
    # edit impossible — and partial denoise is the only way to say "change this, keep
    # the rest". Below 1.0 the source latent always wins over an explicit size.
    partial = float(p.get("denoise", 1.0)) < 1.0
    if p.get("width") and p.get("height") and not partial:
        graph["7"] = {"class_type": "EmptyLatentImage",
                      "inputs": {"width": p["width"], "height": p["height"],
                                 "batch_size": p["batch_size"]}}
        latent = ["7", 0]
    else:
        latent = ["31", 0]

    return _sample_and_save(graph, p, latent, conditioning)


COMMON = [
    Param("prompt", "str", required=True),
    Param("steps", "int", default=4, minimum=1, maximum=50,
          help="klein is distilled; 4 steps is the design point."),
    Param("cfg", "float", default=1.0, minimum=0.0, maximum=10.0),
    Param("seed", "int", default=None),
    Param("batch_size", "int", default=1, minimum=1, maximum=4),
]

register(ComfyPipeline(
    id="flux2-text-to-image",
    kind="image",
    title="FLUX.2 klein text to image",
    description="Generate an image with strong prompt adherence. 4 steps.",
    requires_profile="flux2-klein-4b",
    params=COMMON + [
        Param("width", "int", default=1024, minimum=256, maximum=2048, snap=snap16),
        Param("height", "int", default=1024, minimum=256, maximum=2048, snap=snap16),
    ],
    build=build_text_to_image,
))

EDIT_ONLY = [
    Param("denoise", "float", default=1.0, minimum=0.1, maximum=1.0,
          help="How much of the source to discard. 1.0 regenerates from the "
               "instruction and keeps nothing structurally — right for a full restyle, "
               "wrong for 'remove this person, keep the room'. Try 0.5-0.8 for edits "
               "that must preserve the original composition."),
]

register(ComfyPipeline(
    id="flux2-edit",
    kind="image",
    title="FLUX.2 klein instruction edit",
    description="Edit an image by instruction while leaving the rest intact, e.g. "
                "'change the background to night'. Accepts up to 4 reference images, "
                "so a character sheet can be supplied as context for consistency.",
    requires_profile="flux2-klein-4b",
    accepts_files=["image", "reference_2", "reference_3", "reference_4"],
    params=COMMON + EDIT_ONLY + [
        Param("width", "int", default=None, minimum=256, maximum=2048, snap=snap16,
              help="Omit to keep the source image's size. Ignored when denoise < 1, "
                   "since a partial edit must start from the source latent."),
        Param("height", "int", default=None, minimum=256, maximum=2048, snap=snap16),
    ],
    build=build_edit,
))
