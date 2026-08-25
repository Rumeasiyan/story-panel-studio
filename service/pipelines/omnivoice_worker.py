"""Standalone OmniVoice worker, run inside .venv-omnivoice.

OmniVoice pins torch 2.9.1+cu128 and transformers 5.15.1, which conflict with both
ComfyUI's environment and Chatterbox's, so it gets its own virtualenv and is driven
as a subprocess.

Contract: a JSON request on stdin, a JSON result on stdout.

    {"segments": [{"text": "...", "speed": 1.0, "pause_after": 0.4}],
     "language": "Tamil",
     "reference_audio": "/path/ref.wav" | null,
     "reference_text": "..." | null,
     "instruct": "male, young adult, low pitch" | null,
     "output": "/path/out.wav"}
 -> {"ok": true, "seconds": 82.0, "sample_rate": 24000, "segments": 10,
     "mode": "clone"}
 -> {"ok": false, "error": "..."}

Three modes, in the order the model resolves them:
  clone   reference_audio + reference_text — the only mode that repeats a speaker
  design  instruct tags (gender, age band, pitch, accent); a controlled vocabulary,
          not free text, and the speaker still varies between calls
  auto    neither; the model invents a speaker per call

OmniVoice exposes no emotion parameter. `speed` is the only prosody lever, so
per-segment emotion is expressed as pacing.
"""

from __future__ import annotations

import json
import sys

# Third-party libraries print to stdout on import and on model load — perth, the
# watermarker Chatterbox loads, announces itself there. stdout is this worker's JSON
# channel, so anything else written to it corrupts the result. Redirect stdout to
# stderr for the whole run and keep the real handle for the final message.
_RESULT = sys.stdout
sys.stdout = sys.stderr


def emit_progress(fraction: float, stage: str) -> None:
    print(f"PROGRESS {fraction:.4f} {stage}", file=sys.stderr, flush=True)


def main() -> int:
    request = json.load(sys.stdin)

    import numpy as np
    import soundfile as sf
    import torch
    from omnivoice import OmniVoice

    emit_progress(0.05, "loading OmniVoice")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = OmniVoice.from_pretrained(
        "k2-fsa/OmniVoice", device_map=device, dtype=torch.float16
    )
    sample_rate = 24000

    reference = request.get("reference_audio")
    reference_text = request.get("reference_text")
    instruct = request.get("instruct")
    language = request.get("language")

    if reference and reference_text:
        mode = "clone"
    elif instruct:
        mode = "design"
    else:
        mode = "auto"

    segments = request["segments"]
    pieces: list = []

    for index, segment in enumerate(segments):
        emit_progress(
            0.1 + 0.85 * index / max(len(segments), 1),
            f"segment {index + 1}/{len(segments)} ({mode})",
        )
        kwargs = {"text": segment["text"], "language": language}
        if mode == "clone":
            kwargs["ref_audio"] = reference
            kwargs["ref_text"] = reference_text
        elif mode == "design":
            kwargs["instruct"] = instruct
        if segment.get("speed"):
            kwargs["speed"] = segment["speed"]

        audio = np.asarray(model.generate(**kwargs)[0], dtype="float32")
        pieces.append(audio)

        pause = segment.get("pause_after", 0.0)
        if pause and index != len(segments) - 1:
            pieces.append(np.zeros(int(sample_rate * pause), dtype="float32"))

    full = np.concatenate(pieces) if pieces else np.zeros(0, dtype="float32")
    peak = float(abs(full).max()) if full.size else 0.0
    if peak > 1.0:
        full = full / peak

    sf.write(request["output"], full, sample_rate)

    json.dump({
        "ok": True,
        "seconds": len(full) / float(sample_rate),
        "sample_rate": sample_rate,
        "segments": len(segments),
        "mode": mode,
    }, _RESULT)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        json.dump({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, _RESULT)
        raise SystemExit(1)
