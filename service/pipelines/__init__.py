"""Generation pipelines exposed by the API.

Importing this package registers every pipeline. Add a capability by adding a module
here and importing it below — the API layer needs no changes.
"""

from .base import (  # noqa: F401
    ComfyPipeline,
    Kind,
    LocalPipeline,
    Param,
    Pipeline,
    all_pipelines,
    get,
    register,
)

from . import sdxl      # noqa: F401,E402  SDXL text-to-image, img2img, inpaint
from . import wan       # noqa: F401,E402  Wan 2.2 video
from . import flux2     # noqa: F401,E402  FLUX.2 klein generate + instruction edit
from . import tts       # noqa: F401,E402  IndicF5 / Indic Parler narration
from . import z_image   # noqa: F401,E402  Z-Image Turbo few-step generation
from . import subtitles # noqa: F401,E402  whisper alignment -> SRT/VTT/JSON
