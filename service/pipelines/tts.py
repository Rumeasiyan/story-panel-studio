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
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

import voices
from config import MODELS_DIR, OUTPUT_DIR, ROOT

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

INDICF5_UNAVAILABLE = (
    "IndicF5 does not currently load on this stack. Its bundled remote code targets an "
    "older f5-tts and an older transformers: on transformers 5.x it dies constructing "
    "the model on a meta device, and pinning transformers to 4.46.1 exposes a "
    "load_model() signature mismatch against every published f5-tts release. Its "
    "dependencies also conflict directly with parler-tts, so the two cannot share an "
    "environment.\n\n"
    "Use 'tts-indic-parler' instead — it is verified working and covers Tamil. For a "
    "stable narrator, put a named speaker in the voice description; see service/API.md."
)


def _indicf5():
    """Load IndicF5. Currently raises: see INDICF5_UNAVAILABLE.

    Kept registered rather than deleted because the model is the better fit for this
    project — true voice cloning from a reference clip — and only its packaging is
    broken. When upstream ships remote code matching a current f5-tts, this becomes a
    working path again with no API change.
    """
    if "indicf5" not in _cache:
        from transformers import AutoModel
        local = MODELS_DIR / "tts" / "IndicF5"
        source = str(local) if local.exists() else "ai4bharat/IndicF5"
        try:
            _cache["indicf5"] = AutoModel.from_pretrained(
                source, trust_remote_code=True
            ).to(_device())
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"{INDICF5_UNAVAILABLE}\n\nunderlying error: {exc}") from exc
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

# parler-tts pins transformers==4.46.1 while ComfyUI needs >=4.50.3, so it lives in its
# own virtualenv and runs as a subprocess. Installing it into the shared environment
# downgrades transformers and puts the image engine at risk.
PARLER_VENV = ROOT / ".venv-parler" / "bin" / "python"
PARLER_WORKER = Path(__file__).resolve().parent / "parler_worker.py"


def parler_available() -> bool:
    return PARLER_VENV.exists() and PARLER_WORKER.exists()


def run_parler(p: dict, files: dict[str, Path],
               progress: Callable[[float, str], None]) -> list[Path]:
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

    if not parler_available():
        raise RuntimeError(
            "Indic Parler-TTS is not installed. It needs its own virtualenv because it "
            "pins transformers 4.46.1, which would break ComfyUI. Create it with:\n"
            "  python3.13 -m venv .venv-parler\n"
            "  .venv-parler/bin/pip install torch --index-url "
            "https://download.pytorch.org/whl/cu130\n"
            "  .venv-parler/bin/pip install "
            "git+https://github.com/huggingface/parler-tts.git soundfile"
        )

    model_dir = MODELS_DIR / "tts" / "indic-parler-tts"
    if not model_dir.exists():
        raise RuntimeError(
            f"missing {model_dir}. Fetch it with ./scripts/fetch-tts indic-parler"
        )

    out = OUTPUT_DIR / "audio" / f"{p['job_id']}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)

    request = {
        "model_dir": str(model_dir),
        "description": description,
        "chunks": chunks,
        "output": str(out),
        "gap_seconds": p["gap_seconds"],
    }

    progress(0.05, "starting Indic Parler-TTS")
    process = subprocess.Popen(
        [str(PARLER_VENV), str(PARLER_WORKER)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    process.stdin.write(json.dumps(request))
    process.stdin.close()

    # Relay the worker's progress lines while it runs.
    stderr_tail: list[str] = []
    for line in process.stderr:
        line = line.rstrip()
        if line.startswith("PROGRESS "):
            _, fraction, stage = line.split(" ", 2)
            progress(float(fraction), stage)
        else:
            stderr_tail.append(line)
            del stderr_tail[:-20]

    stdout = process.stdout.read()
    process.wait()

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            "Indic Parler-TTS worker produced no result. "
            + (" / ".join(stderr_tail[-5:]) or f"exit {process.returncode}")
        ) from None

    if not result.get("ok"):
        raise RuntimeError(result.get("error", "Indic Parler-TTS failed"))

    progress(1.0, f"done — {result['seconds']:.1f}s in {result['chunks']} chunk(s)")
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
