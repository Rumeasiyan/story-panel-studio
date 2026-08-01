"""Subtitle generation: align narration audio to text and emit SRT, VTT and JSON.

Uses faster-whisper. Two modes:

  transcribe  whisper decides the words. Fine when there is no script to hand.
  align       you supply the exact script text, and whisper's word timings are mapped
              onto it. Preferred here: the narration was generated FROM a script, so
              the words are already known and only the timing is missing. This avoids
              transcription errors silently rewriting the subtitles — which matters
              most for Tamil, where ASR is weaker than for English.

Word-level timings are always emitted in the JSON output, so a downstream editor can
do karaoke-style highlighting without re-running anything.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from config import MODELS_DIR, OUTPUT_DIR

from .base import LocalPipeline, Param, register

_model_cache: dict[str, object] = {}

WHISPER_SIZES = ["tiny", "base", "small", "medium", "large-v3"]


def _has_cuda12_runtime() -> bool:
    """Is the CUDA 12 runtime CTranslate2 needs actually loadable?

    Constructing WhisperModel on "cuda" succeeds even when it is not, and only blows up
    on the first transcribe, so probe the library up front instead.
    """
    import ctypes

    for name in ("libcublas.so.12", "libcudnn_ops_infer.so.8"):
        try:
            ctypes.CDLL(name)
        except OSError:
            return False
    return True


def _model(size: str):
    """Load whisper, preferring CUDA but falling back to CPU.

    faster-whisper runs on CTranslate2, which links against the CUDA 12 runtime
    (libcublas.so.12). This project installs CUDA 13 torch wheels, so the GPU path is
    often unavailable. Alignment is cheap enough on CPU that downgrading torch to suit
    it would be the wrong trade.
    """
    if size in _model_cache:
        return _model_cache[size]

    from faster_whisper import WhisperModel
    import torch

    root = str(MODELS_DIR / "whisper")
    attempts = []
    if torch.cuda.is_available() and _has_cuda12_runtime():
        attempts.append(("cuda", "float16"))
    attempts.append(("cpu", "int8"))

    last_error: Exception | None = None
    for device, compute_type in attempts:
        try:
            _model_cache[size] = WhisperModel(
                size, device=device, compute_type=compute_type, download_root=root
            )
            return _model_cache[size]
        except Exception as exc:  # noqa: BLE001 - try the next device
            last_error = exc
    raise RuntimeError(f"could not load whisper '{size}': {last_error}")


def unload_all() -> None:
    _model_cache.clear()


def _timestamp(seconds: float, comma: bool = True) -> str:
    if seconds < 0:
        seconds = 0.0
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    whole, frac = divmod(secs, 1)
    ms = int(round(frac * 1000))
    sep = "," if comma else "."
    return f"{int(hours):02d}:{int(minutes):02d}:{int(whole):02d}{sep}{ms:03d}"


def _to_srt(cues: list[dict]) -> str:
    out = []
    for i, cue in enumerate(cues, 1):
        out.append(str(i))
        out.append(f"{_timestamp(cue['start'])} --> {_timestamp(cue['end'])}")
        out.append(cue["text"].strip())
        out.append("")
    return "\n".join(out)


def _to_vtt(cues: list[dict]) -> str:
    out = ["WEBVTT", ""]
    for cue in cues:
        out.append(f"{_timestamp(cue['start'], False)} --> {_timestamp(cue['end'], False)}")
        out.append(cue["text"].strip())
        out.append("")
    return "\n".join(out)


def _group_words(words: list[dict], max_chars: int, max_secs: float) -> list[dict]:
    """Pack word timings into readable cues."""
    cues: list[dict] = []
    current: list[dict] = []

    def flush():
        if current:
            cues.append({
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "text": "".join(w["word"] for w in current).strip(),
                "words": list(current),
            })
            current.clear()

    for word in words:
        if current:
            span = word["end"] - current[0]["start"]
            length = sum(len(w["word"]) for w in current) + len(word["word"])
            # Break on sentence punctuation too, so cues follow the narration's phrasing.
            if length > max_chars or span > max_secs:
                flush()
        current.append(word)
        if re.search(r"[.!?।॥]\s*$", word["word"]):
            flush()
    flush()
    return cues


def _redistribute(cues: list[dict], script: str) -> list[dict]:
    """Map whisper's timings onto the caller's exact script text.

    Whisper's word count rarely matches the script exactly, so words are assigned
    proportionally across the recognised timeline rather than one-to-one. Timing drifts
    slightly; the text stays exactly what was written, which is the important half.
    """
    script_words = script.split()
    if not script_words or not cues:
        return cues

    timed = [w for cue in cues for w in cue["words"]]
    if not timed:
        return cues

    total = len(script_words)
    count = len(timed)
    out_words = []
    for index, token in enumerate(script_words):
        source = timed[min(count - 1, int(index * count / total))]
        out_words.append({"word": " " + token, "start": source["start"],
                          "end": source["end"]})
    # Keep timings monotonic after the remap.
    for i in range(1, len(out_words)):
        if out_words[i]["start"] < out_words[i - 1]["start"]:
            out_words[i]["start"] = out_words[i - 1]["start"]
        if out_words[i]["end"] < out_words[i]["start"]:
            out_words[i]["end"] = out_words[i]["start"]
    return out_words


def run(p: dict, files: dict[str, Path],
        progress: Callable[[float, str], None]) -> list[Path]:
    audio = files.get("audio")
    if audio is None:
        raise ValueError("an 'audio' file is required")

    progress(0.05, f"loading whisper {p['model_size']}")
    model = _model(p["model_size"])

    progress(0.2, "transcribing")
    language = p.get("language") or None
    segments, info = model.transcribe(
        str(audio),
        language=None if language in (None, "auto") else language,
        word_timestamps=True,
        vad_filter=True,
    )

    words: list[dict] = []
    for segment in segments:
        for word in (segment.words or []):
            words.append({"word": word.word, "start": word.start, "end": word.end})

    if not words:
        raise ValueError("no speech detected in the audio")

    progress(0.8, "building cues")
    if p.get("script"):
        # Trust the script for the text; use whisper only for timing.
        words = _redistribute(_group_words(words, 10**9, 10**9), p["script"])

    cues = _group_words(words, p["max_chars"], p["max_seconds"])

    stem = OUTPUT_DIR / "subtitles" / p["job_id"]
    stem.parent.mkdir(parents=True, exist_ok=True)
    outputs = []

    srt = stem.with_suffix(".srt")
    srt.write_text(_to_srt(cues), encoding="utf-8")
    outputs.append(srt)

    vtt = stem.with_suffix(".vtt")
    vtt.write_text(_to_vtt(cues), encoding="utf-8")
    outputs.append(vtt)

    data = stem.with_suffix(".json")
    data.write_text(json.dumps({
        "language": getattr(info, "language", language),
        "duration": getattr(info, "duration", None),
        "source": "script-aligned" if p.get("script") else "transcribed",
        "cues": cues,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    outputs.append(data)

    progress(1.0, "done")
    return outputs


register(LocalPipeline(
    id="subtitles",
    kind="subtitle",
    title="Subtitles from narration audio",
    description="Word-level timings for narration. Pass the original script to keep the "
                "exact wording and use whisper only for timing — strongly preferred for "
                "Tamil. Emits SRT, VTT and JSON with per-word timings.",
    accepts_files=["audio"],
    params=[
        Param("script", "str", default=None,
              help="The exact narration text. Omit to let whisper transcribe instead."),
        Param("language", "enum", default="auto",
              choices=["auto", "ta", "en", "hi", "te", "kn", "ml", "mr", "bn"]),
        Param("model_size", "enum", default="small", choices=WHISPER_SIZES,
              help="Larger is more accurate and slower. 'small' is a good default; "
                   "use 'large-v3' for Tamil transcription without a script."),
        Param("max_chars", "int", default=42, minimum=10, maximum=200,
              help="Maximum characters per subtitle cue."),
        Param("max_seconds", "float", default=5.0, minimum=1.0, maximum=15.0,
              help="Maximum duration of a single cue."),
    ],
    run=run,
))
