"""Narration engines that are not AI4Bharat's.

`tts.py` covers the Indic models. This module covers the two that were chosen by
listening rather than by language coverage:

  Chatterbox  MIT, Resemble AI. English. The only engine here that sounds human
              enough to publish, and the only one with a real emotion control
              (`exaggeration`). No Tamil.
  OmniVoice   Apache-2.0, k2-fsa. 646 languages including Tamil and Sinhala, plus
              three ways to pick a speaker. No emotion parameter at all.

**Segmented narration is the point of this module.** A story beat that is angry and
one that is grief-stricken cannot share a delivery setting, and generating a whole
script in one call produces exactly that flatness — it also truncates, because a
long block overruns the sampler's step budget. So callers pass `segments`: each gets
its own generate() call with its own emotion, and the results are concatenated with
per-segment pauses. The voice is held constant across segments by an anchor clip,
since without one every call invents a new speaker.

That is still generation, not orchestration: one request produces one audio file.
Deciding what the beats are belongs to the caller.

Both engines need their own virtualenv — Chatterbox pins torch 2.6.0+cu124 and
OmniVoice 2.9.1+cu128, neither of which matches ComfyUI's — so both run as
subprocess workers. `config/venv-locks/` rebuilds them.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

import voices
from config import OUTPUT_DIR, ROOT

from .base import LocalPipeline, Param, register
from .tts import split_text

CHATTERBOX_PYTHON = ROOT / ".venv-chatterbox" / "bin" / "python"
CHATTERBOX_WORKER = Path(__file__).resolve().parent / "chatterbox_worker.py"
OMNIVOICE_PYTHON = ROOT / ".venv-omnivoice" / "bin" / "python"
OMNIVOICE_WORKER = Path(__file__).resolve().parent / "omnivoice_worker.py"

# OmniVoice's instruct vocabulary is a fixed tag list, not free text. Anything
# outside it raises rather than being quietly ignored, so it is validated here to
# fail at request time with a useful message instead of inside the worker.
INSTRUCT_TAGS = {
    "american accent", "australian accent", "british accent", "canadian accent",
    "child", "chinese accent", "elderly", "female", "high pitch", "indian accent",
    "japanese accent", "korean accent", "low pitch", "male", "middle-aged",
    "moderate pitch", "portuguese accent", "russian accent", "teenager",
    "very high pitch", "very low pitch", "whisper", "young adult",
}

MAX_SEGMENTS = 64


def _drive_worker(python: Path, worker: Path, request: dict, engine: str,
                  progress: Callable[[float, str], None]) -> dict:
    """Run a worker in its own virtualenv, relaying progress, returning its result."""
    process = subprocess.Popen(
        [str(python), str(worker)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    process.stdin.write(json.dumps(request))
    process.stdin.close()

    stderr_tail: list[str] = []
    for line in process.stderr:
        line = line.rstrip()
        if line.startswith("PROGRESS "):
            _, fraction, stage = line.split(" ", 2)
            progress(float(fraction), stage)
        elif line and "it/s]" not in line and "s/it]" not in line:
            # Progress bars would otherwise fill the tail and hide the real error.
            stderr_tail.append(line)
            del stderr_tail[:-20]

    stdout = process.stdout.read()
    process.wait()

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"{engine} worker produced no result. "
            + (" / ".join(stderr_tail[-5:]) or f"exit {process.returncode}")
        ) from None

    if not result.get("ok"):
        raise RuntimeError(result.get("error", f"{engine} failed"))
    return result


def _segments(p: dict, defaults: dict) -> list[dict]:
    """Build the segment list from either `segments` JSON or plain `text`.

    Plain text is still split on sentence boundaries, so a caller who does not care
    about emotion gets chunking for free and never hits the truncation ceiling.
    """
    raw = (p.get("segments") or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"'segments' is not valid JSON: {exc}") from None
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("'segments' must be a non-empty JSON array")
        if len(parsed) > MAX_SEGMENTS:
            raise ValueError(f"'segments' accepts at most {MAX_SEGMENTS} entries")

        out = []
        for index, item in enumerate(parsed):
            if not isinstance(item, dict) or not str(item.get("text", "")).strip():
                raise ValueError(f"segment {index + 1} needs a non-empty 'text'")
            segment = {"text": str(item["text"]).strip(),
                       "pause_after": float(item.get("pause_after",
                                                     p.get("gap_seconds", 0.25)))}
            for key, default in defaults.items():
                segment[key] = float(item.get(key, p.get(key, default)))
            out.append(segment)
        return out

    chunks = split_text(p.get("text", ""))
    if not chunks:
        raise ValueError("supply either 'text' or 'segments'")
    base = {key: float(p.get(key, default)) for key, default in defaults.items()}
    return [dict(base, text=chunk, pause_after=p.get("gap_seconds", 0.25))
            for chunk in chunks]


def _reference(p: dict, files: dict[str, Path], engine: str) -> tuple[str | None, str]:
    """Resolve the anchor clip and its transcript from a voice profile or an upload."""
    if p.get("voice"):
        meta = voices.resolve(p["voice"], engine)
        stored = meta.get("reference_audio")
        path = str(voices.VOICE_DIR / stored) if stored else None
        return path, meta.get("reference_text", "")
    uploaded = files.get("reference_audio")
    return (str(uploaded) if uploaded else None), (p.get("reference_text") or "")


# ------------------------------------------------------------------ Chatterbox

def run_chatterbox(p: dict, files: dict[str, Path],
                   progress: Callable[[float, str], None]) -> list[Path]:
    if not CHATTERBOX_PYTHON.exists():
        raise RuntimeError(
            "Chatterbox is not installed. It needs its own virtualenv because it pins "
            "torch 2.6.0+cu124, which would break ComfyUI. Rebuild it with:\n"
            "  python3 -m venv .venv-chatterbox\n"
            "  .venv-chatterbox/bin/pip install -r config/venv-locks/chatterbox.lock.txt\n"
            "Keep setuptools below 81 or its watermarker resolves to None at runtime."
        )

    segments = _segments(p, {"exaggeration": 0.5, "cfg_weight": 0.5})
    reference, _ = _reference(p, files, "chatterbox")

    out = OUTPUT_DIR / "audio" / f"{p['job_id']}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)

    progress(0.02, "starting Chatterbox")
    result = _drive_worker(CHATTERBOX_PYTHON, CHATTERBOX_WORKER, {
        "segments": segments,
        "reference_audio": reference,
        "output": str(out),
    }, "Chatterbox", progress)

    progress(1.0, f"done — {result['seconds']:.1f}s in {result['segments']} segment(s)")
    return [out]


# ------------------------------------------------------------------- OmniVoice

def run_omnivoice(p: dict, files: dict[str, Path],
                  progress: Callable[[float, str], None]) -> list[Path]:
    if not OMNIVOICE_PYTHON.exists():
        raise RuntimeError(
            "OmniVoice is not installed. It needs its own virtualenv because it pins "
            "torch 2.9.1+cu128. Rebuild it with:\n"
            "  python3 -m venv .venv-omnivoice\n"
            "  .venv-omnivoice/bin/pip install torch==2.9.1 torchaudio==2.9.1 "
            "--index-url https://download.pytorch.org/whl/cu128\n"
            "  .venv-omnivoice/bin/pip install omnivoice soundfile"
        )

    segments = _segments(p, {"speed": 1.0})
    reference, reference_text = _reference(p, files, "omnivoice")

    instruct = (p.get("instruct") or "").strip()
    if p.get("voice") and not reference:
        instruct = instruct or voices.resolve(p["voice"], "omnivoice").get(
            "voice_description", "")
    if instruct:
        unknown = [t.strip() for t in instruct.split(",")
                   if t.strip() and t.strip().lower() not in INSTRUCT_TAGS]
        if unknown:
            raise ValueError(
                f"unsupported instruct tag(s): {', '.join(unknown)}. 'instruct' is a "
                f"fixed vocabulary, not free text — choose from: "
                f"{', '.join(sorted(INSTRUCT_TAGS))}"
            )

    if reference and not reference_text.strip():
        raise ValueError(
            "cloning needs 'reference_text': the exact transcript of the reference "
            "clip. A mismatch degrades the clone."
        )

    out = OUTPUT_DIR / "audio" / f"{p['job_id']}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)

    progress(0.02, "starting OmniVoice")
    result = _drive_worker(OMNIVOICE_PYTHON, OMNIVOICE_WORKER, {
        "segments": segments,
        "language": p.get("language") or None,
        "reference_audio": reference,
        "reference_text": reference_text or None,
        "instruct": instruct or None,
        "output": str(out),
    }, "OmniVoice", progress)

    progress(1.0, f"done — {result['seconds']:.1f}s in {result['segments']} "
                  f"segment(s), {result['mode']} mode")
    return [out]


SEGMENTS_HELP = (
    "JSON array of beats, each generated separately so emotion can change between "
    "them while the voice does not. Overrides 'text'. Every entry needs 'text'; the "
    "engine's own controls and 'pause_after' are optional per entry."
)

register(LocalPipeline(
    id="tts-chatterbox",
    kind="audio",
    title="Chatterbox narration (English, per-beat emotion)",
    description="English narration that sounds human. MIT licensed. Clones a voice "
                "from a few seconds of reference audio, and varies emotion per beat "
                "via 'exaggeration'. No Tamil — use tts-omnivoice for that.",
    accepts_files=["reference_audio"],
    params=[
        Param("text", "str", default=None,
              help="What to narrate. Split on sentence boundaries when 'segments' is "
                   "not given."),
        Param("segments", "str", default=None, help=SEGMENTS_HELP),
        Param("voice", "str", default=None,
              help="Name of a registered voice (GET /api/voices). The reliable way to "
                   "hold one narrator across every episode."),
        Param("exaggeration", "float", default=0.5, minimum=0.0, maximum=2.0,
              help="Emotional intensity. ~0.3 calm, 0.5 neutral, 0.85 peak. Default "
                   "for segments that do not set their own."),
        Param("cfg_weight", "float", default=0.5, minimum=0.0, maximum=1.0,
              help="Pacing. Lower is slower and heavier."),
        Param("gap_seconds", "float", default=0.25, minimum=0.0, maximum=3.0,
              help="Default silence after a segment."),
    ],
    run=run_chatterbox,
))

register(LocalPipeline(
    id="tts-omnivoice",
    kind="audio",
    title="OmniVoice narration (646 languages, incl. Tamil)",
    description="Apache-2.0, 646 languages. Three ways to pick a speaker: clone a "
                "reference clip, describe one with 'instruct' tags, or let the model "
                "invent one. No emotion control — 'speed' is the only prosody lever.",
    accepts_files=["reference_audio"],
    params=[
        Param("text", "str", default=None, help="What to narrate."),
        Param("segments", "str", default=None, help=SEGMENTS_HELP),
        Param("voice", "str", default=None, help="Name of a registered voice."),
        Param("language", "str", default=None,
              help="Language name or code, e.g. 'Tamil' or 'ta'. Optional, but "
                   "upstream reports better results when set."),
        Param("instruct", "str", default=None,
              help="Comma-separated tags describing the speaker, e.g. "
                   "'male, young adult, low pitch'. A fixed vocabulary, not free "
                   "text. Ignored when a reference clip is supplied."),
        Param("reference_text", "str", default=None,
              help="Exact transcript of reference_audio. Required when cloning."),
        Param("speed", "float", default=1.0, minimum=0.5, maximum=2.0,
              help="Pacing. Below 1.0 is slower. The only prosody control OmniVoice "
                   "exposes, so emotion has to be expressed as pacing."),
        Param("gap_seconds", "float", default=0.25, minimum=0.0, maximum=3.0,
              help="Default silence after a segment."),
    ],
    run=run_omnivoice,
))
