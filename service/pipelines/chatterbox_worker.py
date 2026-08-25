"""Standalone Chatterbox worker, run inside .venv-chatterbox.

Chatterbox pins torch 2.6.0+cu124 and transformers 5.2.0, which do not match the
versions ComfyUI needs, so it gets its own virtualenv and is driven as a subprocess.

Contract: a JSON request on stdin, a JSON result on stdout.

    {"segments": [{"text": "...", "exaggeration": 0.5, "cfg_weight": 0.5,
                   "pause_after": 0.3}],
     "reference_audio": "/path/ref.wav" | null,
     "output": "/path/out.wav", "gap_seconds": 0.25}
 -> {"ok": true, "seconds": 41.8, "sample_rate": 24000, "segments": 6}
 -> {"ok": false, "error": "..."}

Each segment is a separate generate() call. That is what allows emotion to change
between beats while the voice stays put, and it also keeps every call short enough
to stay inside the sampler's step budget — long single blocks were being truncated.

Progress lines go to stderr as `PROGRESS <fraction> <stage>` so they do not pollute
the JSON channel.
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
    from chatterbox.tts import ChatterboxTTS

    emit_progress(0.05, "loading Chatterbox")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ChatterboxTTS.from_pretrained(device=device)
    sample_rate = model.sr

    segments = request["segments"]
    reference = request.get("reference_audio")
    pieces: list = []

    for index, segment in enumerate(segments):
        emit_progress(
            0.1 + 0.85 * index / max(len(segments), 1),
            f"segment {index + 1}/{len(segments)}",
        )
        kwargs = {
            "exaggeration": segment["exaggeration"],
            "cfg_weight": segment["cfg_weight"],
        }
        # Without an anchor every call invents its own voice, so a multi-segment
        # narration would drift speaker between beats.
        if reference:
            kwargs["audio_prompt_path"] = reference

        wav = model.generate(segment["text"], **kwargs)
        audio = wav.squeeze(0).cpu().numpy().astype("float32")
        pieces.append(audio)

        pause = segment.get("pause_after", 0.0)
        if pause and index != len(segments) - 1:
            pieces.append(np.zeros(int(sample_rate * pause), dtype="float32"))

    full = np.concatenate(pieces) if pieces else np.zeros(0, dtype="float32")
    peak = float(abs(full).max()) if full.size else 0.0
    if peak > 1.0:
        full = full / peak

    output = request["output"]
    sf.write(output, full, sample_rate)

    json.dump({
        "ok": True,
        "seconds": len(full) / float(sample_rate),
        "sample_rate": sample_rate,
        "segments": len(segments),
    }, _RESULT)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # reported as JSON so the caller sees a real message
        json.dump({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, _RESULT)
        raise SystemExit(1)
