"""Text to speech, in-process rather than through ComfyUI.

Two AI4Bharat models, both small and both covering Tamil, which is the constraint that
matters here:

  IndicF5           MIT, 1.4 GB. Clones a voice from a reference clip. The right choice
                    when a channel needs ONE narrator voice held constant forever.
  Indic Parler-TTS  Apache-2.0, 3.8 GB. Voice chosen by describing the speaker, so no
                    reference audio is needed.

Models load lazily and stay cached, because loading dominates the cost of a short line.
"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Callable

from config import MODELS_DIR, OUTPUT_DIR

from .base import LocalPipeline, Param, register

# Languages both models cover. Tamil and English are the two this project needs.
LANGUAGES = ["ta", "en", "hi", "te", "kn", "ml", "mr", "bn", "gu", "pa", "or", "as"]

_cache: dict[str, object] = {}


def _device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def unload_all() -> None:
    """Free the TTS models so a big image or video render gets the VRAM back."""
    _cache.clear()
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass


def _write_wav(path: Path, audio, sample_rate: int) -> None:
    import numpy as np
    import soundfile as sf

    data = np.asarray(audio, dtype="float32").squeeze()
    peak = float(abs(data).max()) if data.size else 0.0
    if peak > 1.0:
        data = data / peak
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, sample_rate)


# --------------------------------------------------------------------- IndicF5

def _indicf5():
    if "indicf5" not in _cache:
        from transformers import AutoModel
        local = MODELS_DIR / "tts" / "IndicF5"
        source = str(local) if local.exists() else "ai4bharat/IndicF5"
        _cache["indicf5"] = AutoModel.from_pretrained(
            source, trust_remote_code=True
        ).to(_device())
    return _cache["indicf5"]


def run_indicf5(p: dict, files: dict[str, Path],
                progress: Callable[[float, str], None]) -> list[Path]:
    progress(0.05, "loading IndicF5")
    model = _indicf5()

    reference = files.get("reference_audio")
    if reference is None:
        raise ValueError(
            "IndicF5 clones a voice, so it needs 'reference_audio' (a few seconds of "
            "clean speech) and 'reference_text' (exactly what is said in it). "
            "Use the indic-parler-tts pipeline if you have no reference clip."
        )
    if not p.get("reference_text"):
        raise ValueError("reference_text is required: the transcript of reference_audio")

    progress(0.3, "synthesising")
    audio = model(
        p["text"],
        ref_audio_path=str(reference),
        ref_text=p["reference_text"],
    )

    out = OUTPUT_DIR / "audio" / f"{p['job_id']}.wav"
    _write_wav(out, audio, 24000)
    progress(1.0, "done")
    return [out]


# ------------------------------------------------------------- Indic Parler-TTS

def _parler():
    if "parler" not in _cache:
        from transformers import AutoTokenizer
        from parler_tts import ParlerTTSForConditionalGeneration
        local = MODELS_DIR / "tts" / "indic-parler-tts"
        source = str(local) if local.exists() else "ai4bharat/indic-parler-tts"
        model = ParlerTTSForConditionalGeneration.from_pretrained(source).to(_device())
        _cache["parler"] = (
            model,
            AutoTokenizer.from_pretrained(source),
            AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path),
        )
    return _cache["parler"]


def run_parler(p: dict, files: dict[str, Path],
               progress: Callable[[float, str], None]) -> list[Path]:
    import torch

    progress(0.05, "loading Indic Parler-TTS")
    model, tokenizer, description_tokenizer = _parler()
    device = _device()

    progress(0.3, "synthesising")
    desc = description_tokenizer(p["voice_description"], return_tensors="pt").to(device)
    prompt = tokenizer(p["text"], return_tensors="pt").to(device)

    with torch.no_grad():
        generation = model.generate(
            input_ids=desc.input_ids,
            attention_mask=desc.attention_mask,
            prompt_input_ids=prompt.input_ids,
            prompt_attention_mask=prompt.attention_mask,
        )

    out = OUTPUT_DIR / "audio" / f"{p['job_id']}.wav"
    _write_wav(out, generation.cpu().numpy().squeeze(), model.config.sampling_rate)
    progress(1.0, "done")
    return [out]


register(LocalPipeline(
    id="tts-indicf5",
    kind="audio",
    title="IndicF5 narration (voice cloning)",
    description="Clone one narrator voice from a reference clip and reuse it for every "
                "episode. MIT licensed. Needs reference_audio plus reference_text.",
    requires_profile="tts-indicf5",
    accepts_files=["reference_audio"],
    params=[
        Param("text", "str", required=True, help="What to narrate."),
        Param("language", "enum", default="ta", choices=LANGUAGES),
        Param("reference_text", "str", required=True,
              help="Exact transcript of the reference clip."),
    ],
    run=run_indicf5,
))

register(LocalPipeline(
    id="tts-indic-parler",
    kind="audio",
    title="Indic Parler-TTS narration (described voice)",
    description="Pick a voice by describing it, no reference clip needed. "
                "Apache-2.0, 21 languages including Tamil.",
    requires_profile="tts-indic-parler",
    params=[
        Param("text", "str", required=True, help="What to narrate."),
        Param("language", "enum", default="ta", choices=LANGUAGES),
        Param("voice_description", "str",
              default="A clear, expressive male narrator with a moderate pace and "
                      "very high recording quality.",
              help="Describe age, gender, pace, emotion and recording quality. "
                   "Keep it identical across episodes to keep the voice stable."),
    ],
    run=run_parler,
))
