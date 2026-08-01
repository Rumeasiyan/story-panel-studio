"""Text to speech, in-process rather than through ComfyUI.

Two AI4Bharat models, both covering Tamil, which is the constraint that matters here:

  IndicF5           MIT, 1.4 GB. Clones a voice from a reference clip. The right choice
                    when a channel needs ONE narrator held constant forever.
  Indic Parler-TTS  Apache-2.0, 3.8 GB. Voice chosen by describing the speaker, so no
                    reference audio is needed.

Voice consistency works like character consistency: register the narrator once as a
named profile (see voices.py) and pass `voice` on every call. The alternative — sending
a reference clip per request — drifts the moment one request sends the wrong file.

Long narration is chunked on sentence boundaries and concatenated, because both models
degrade on very long inputs. Every chunk uses the same voice, so the join is seamless.
"""

from __future__ import annotations

import gc
import re
from pathlib import Path
from typing import Callable

import voices
from config import MODELS_DIR, OUTPUT_DIR

from .base import LocalPipeline, Param, register

LANGUAGES = ["ta", "en", "hi", "te", "kn", "ml", "mr", "bn", "gu", "pa", "or", "as"]

# Both models are trained on utterance-length input; long paragraphs degrade badly.
MAX_CHUNK_CHARS = 300

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


def split_text(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split on sentence ends, packing up to `limit` characters per chunk.

    Handles Latin punctuation and the Devanagari danda, which Indic scripts use.
    A sentence longer than the limit is passed through whole rather than cut
    mid-clause, since a clean join matters more than a strict bound.
    """
    text = " ".join((text or "").split())
    if not text:
        return []

    sentences = [s.strip() for s in re.split(r"(?<=[.!?।॥])\s+", text) if s.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def _write_wav(path: Path, audio, sample_rate: int) -> float:
    """Write a mono float array; returns its duration in seconds."""
    import numpy as np
    import soundfile as sf

    data = np.asarray(audio, dtype="float32").squeeze()
    peak = float(abs(data).max()) if data.size else 0.0
    if peak > 1.0:
        data = data / peak
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, sample_rate)
    return len(data) / float(sample_rate)


def _concat(pieces: list, sample_rate: int, gap_seconds: float):
    """Join chunk audio with a short silence, so sentences do not run together."""
    import numpy as np

    gap = np.zeros(int(sample_rate * gap_seconds), dtype="float32")
    joined: list = []
    for index, piece in enumerate(pieces):
        joined.append(np.asarray(piece, dtype="float32").squeeze())
        if index != len(pieces) - 1:
            joined.append(gap)
    return np.concatenate(joined) if joined else np.zeros(0, dtype="float32")


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
    reference_path: Path | None = None
    reference_text = p.get("reference_text") or ""

    if p.get("voice"):
        profile = voices.resolve(p["voice"], "indicf5")
        reference_path = profile["reference_path"]
        reference_text = profile["reference_text"]
    elif files.get("reference_audio"):
        reference_path = files["reference_audio"]

    if reference_path is None:
        raise ValueError(
            "IndicF5 clones a voice. Either register one with POST /api/voices and pass "
            "'voice', or send 'reference_audio' plus 'reference_text' inline. "
            "A registered voice is strongly preferred: it keeps a channel's narrator "
            "identical across every episode."
        )
    if not reference_text.strip():
        raise ValueError("'reference_text' is required: the transcript of the reference clip")

    chunks = split_text(p["text"])
    if not chunks:
        raise ValueError("'text' is empty")

    progress(0.05, "loading IndicF5")
    model = _indicf5()

    pieces = []
    for index, chunk in enumerate(chunks):
        progress(0.1 + 0.85 * index / len(chunks),
                 f"synthesising {index + 1}/{len(chunks)}")
        pieces.append(model(chunk, ref_audio_path=str(reference_path),
                            ref_text=reference_text))

    sample_rate = 24000
    audio = _concat(pieces, sample_rate, p["gap_seconds"])
    out = OUTPUT_DIR / "audio" / f"{p['job_id']}.wav"
    seconds = _write_wav(out, audio, sample_rate)
    progress(1.0, f"done — {seconds:.1f}s in {len(chunks)} chunk(s)")
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

    description = p.get("voice_description") or ""
    if p.get("voice"):
        description = voices.resolve(p["voice"], "indic-parler")["voice_description"]
    if not description.strip():
        raise ValueError(
            "either register a voice with POST /api/voices and pass 'voice', or supply "
            "'voice_description' inline"
        )

    chunks = split_text(p["text"])
    if not chunks:
        raise ValueError("'text' is empty")

    progress(0.05, "loading Indic Parler-TTS")
    model, tokenizer, description_tokenizer = _parler()
    device = _device()

    # Encode the description once: identical conditioning for every chunk is what keeps
    # the narrator stable across a long passage.
    desc = description_tokenizer(description, return_tensors="pt").to(device)

    pieces = []
    for index, chunk in enumerate(chunks):
        progress(0.1 + 0.85 * index / len(chunks),
                 f"synthesising {index + 1}/{len(chunks)}")
        prompt = tokenizer(chunk, return_tensors="pt").to(device)
        with torch.no_grad():
            generation = model.generate(
                input_ids=desc.input_ids,
                attention_mask=desc.attention_mask,
                prompt_input_ids=prompt.input_ids,
                prompt_attention_mask=prompt.attention_mask,
            )
        pieces.append(generation.cpu().numpy().squeeze())

    sample_rate = model.config.sampling_rate
    audio = _concat(pieces, sample_rate, p["gap_seconds"])
    out = OUTPUT_DIR / "audio" / f"{p['job_id']}.wav"
    seconds = _write_wav(out, audio, sample_rate)
    progress(1.0, f"done — {seconds:.1f}s in {len(chunks)} chunk(s)")
    return [out]


COMMON = [
    Param("text", "str", required=True,
          help="What to narrate. Long text is split on sentence boundaries and joined."),
    Param("voice", "str", default=None,
          help="Name of a registered voice (GET /api/voices). The reliable way to keep "
               "one narrator across every episode."),
    Param("language", "enum", default="ta", choices=LANGUAGES),
    Param("gap_seconds", "float", default=0.25, minimum=0.0, maximum=2.0,
          help="Silence inserted between sentence chunks."),
]

register(LocalPipeline(
    id="tts-indicf5",
    kind="audio",
    title="IndicF5 narration (voice cloning)",
    description="Clone one narrator voice and reuse it for every episode. MIT licensed. "
                "Pass a registered 'voice', or 'reference_audio' plus 'reference_text' "
                "inline.",
    accepts_files=["reference_audio"],
    params=COMMON + [
        Param("reference_text", "str", default=None,
              help="Transcript of reference_audio. Ignored when 'voice' is given."),
    ],
    run=run_indicf5,
))

register(LocalPipeline(
    id="tts-indic-parler",
    kind="audio",
    title="Indic Parler-TTS narration (described voice)",
    description="Pick a voice by describing it, no reference clip needed. Apache-2.0, "
                "21 languages including Tamil.",
    params=COMMON + [
        Param("voice_description", "str", default=None,
              help="Describe age, gender, pace and recording quality. Ignored when "
                   "'voice' is given. Keep it identical across episodes."),
    ],
    run=run_parler,
))
