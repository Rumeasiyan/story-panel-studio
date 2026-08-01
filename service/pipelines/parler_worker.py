"""Standalone Indic Parler-TTS worker, run inside .venv-parler.

parler-tts hard-pins transformers==4.46.1, while ComfyUI needs >=4.50.3. Installing it
into the main environment downgrades transformers and puts the image engine at risk, so
it gets its own virtualenv and is driven as a subprocess instead.

Contract: a JSON request on stdin, a JSON result on stdout.

    {"model_dir": "...", "description": "...", "chunks": ["..."],
     "output": "/path/out.wav", "gap_seconds": 0.25}
 -> {"ok": true, "seconds": 12.3, "sample_rate": 44100, "chunks": 3}
 -> {"ok": false, "error": "..."}

Progress lines are written to stderr as `PROGRESS <fraction> <stage>` so the caller can
report them without polluting the JSON channel.
"""

from __future__ import annotations

import json
import sys


def emit_progress(fraction: float, stage: str) -> None:
    print(f"PROGRESS {fraction:.4f} {stage}", file=sys.stderr, flush=True)


def main() -> int:
    request = json.load(sys.stdin)

    import numpy as np
    import soundfile as sf
    import torch
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer

    emit_progress(0.05, "loading Indic Parler-TTS")
    source = request["model_dir"]
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = ParlerTTSForConditionalGeneration.from_pretrained(source).to(device)
    tokenizer = AutoTokenizer.from_pretrained(source)
    description_tokenizer = AutoTokenizer.from_pretrained(
        model.config.text_encoder._name_or_path
    )

    # Encode the description once: identical conditioning for every chunk is what keeps
    # the narrator stable across a long passage.
    desc = description_tokenizer(request["description"], return_tensors="pt").to(device)

    chunks = request["chunks"]
    pieces = []
    for index, chunk in enumerate(chunks):
        emit_progress(0.1 + 0.85 * index / len(chunks),
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

    sample_rate = int(model.config.sampling_rate)
    gap = np.zeros(int(sample_rate * request.get("gap_seconds", 0.25)), dtype="float32")

    joined = []
    for index, piece in enumerate(pieces):
        joined.append(np.asarray(piece, dtype="float32").squeeze())
        if index != len(pieces) - 1:
            joined.append(gap)
    audio = np.concatenate(joined) if joined else np.zeros(0, dtype="float32")

    peak = float(abs(audio).max()) if audio.size else 0.0
    if peak > 1.0:
        audio = audio / peak

    sf.write(request["output"], audio, sample_rate)
    json.dump({"ok": True, "seconds": len(audio) / sample_rate,
               "sample_rate": sample_rate, "chunks": len(chunks)}, sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - the caller only sees this channel
        json.dump({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, sys.stdout)
        sys.exit(1)
