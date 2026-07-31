"""Shared paths and defaults for the local web UI."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SERVICE_DIR = ROOT / "service"
DATA_DIR = SERVICE_DIR / "data"
THUMB_DIR = DATA_DIR / "thumbs"
DB_PATH = DATA_DIR / "app.db"

OUTPUT_DIR = ROOT / "output"
INPUT_DIR = ROOT / "input"

API_WORKFLOW = ROOT / "workflows" / "api" / "wan22_ti2v_5b.json"

COMFY_HOST = os.environ.get("COMFY_HOST", "127.0.0.1")
COMFY_PORT = int(os.environ.get("COMFY_PORT", "8188"))
COMFY_URL = f"http://{COMFY_HOST}:{COMFY_PORT}"
COMFY_WS = f"ws://{COMFY_HOST}:{COMFY_PORT}/ws"

# The UI itself. Localhost only — this app has no authentication.
UI_HOST = os.environ.get("UI_HOST", "127.0.0.1")
UI_PORT = int(os.environ.get("UI_PORT", "8189"))

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# Resolution presets. Wan's VAE needs both dimensions to be multiples of 16.
PRESETS = {
    "512x288": (512, 288, "safe on 8 GB — start here"),
    "640x360": (640, 360, "step up once 512x288 is stable"),
    "704x384": (704, 384, "heavier; expect more offloading"),
    "832x480": (832, 480, "risky on 8 GB"),
    "1280x704": (1280, 704, "template default — will likely not fit 8 GB"),
}

# Wan wants length = 4n + 1.
FRAME_CHOICES = [25, 41, 49, 65, 81, 121]

# Model requirements, not hardware limits: Wan's VAE needs both dimensions to be
# multiples of 16, and its latent layout needs length = 4n + 1. These always apply.
DIM_STEP = 16
FRAME_STEP = 4

# Sanity bounds only — deliberately generous so this runs unchanged on a bigger GPU.
# Nothing here is tuned to the RTX 3050. Raise them in config/runtime.env if needed.
MIN_DIM = 128
MAX_DIM = int(os.environ.get("UI_MAX_DIM", "4096"))
MIN_FRAMES = 5
MAX_FRAMES = int(os.environ.get("UI_MAX_FRAMES", "1001"))

# Reference point for the cost display: the largest setting confirmed comfortable on an
# 8 GiB card. The UI rescales this against whatever GPU is actually detected, so the
# guidance follows the hardware instead of assuming it.
BASELINE_COST = 512 * 288 * 41
BASELINE_VRAM_GIB = 8.0

DEFAULTS = {
    "preset": "512x288",
    "frames": 41,
    "steps": 20,
    "cfg": 5.0,
    "fps": 24,
    "shift": 8.0,
    "sampler": "uni_pc",
    "scheduler": "simple",
}

# Upstream template's negative prompt (Chinese), kept as the default.
DEFAULT_NEGATIVE = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
    "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
    "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
    "杂乱的背景，三条腿，背景人很多，倒着走"
)

# Node ids inside workflows/api/wan22_ti2v_5b.json.
NODE_POSITIVE = "6"
NODE_NEGATIVE = "7"
NODE_KSAMPLER = "3"
NODE_LATENT = "55"
NODE_CREATE_VIDEO = "57"
NODE_SAVE_VIDEO = "58"
NODE_MODEL_SAMPLING = "48"
NODE_LOAD_IMAGE = "56"
