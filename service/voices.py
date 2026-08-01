"""Voice profiles: the narration equivalent of a character LoRA.

A channel needs ONE narrator whose voice never drifts across hundreds of episodes.
Passing a reference clip on every request makes that fragile — one wrong file and the
narrator changes mid-series. So a voice is registered once, given a name, and every
later request refers to it by name.

Two engines, one concept:

  indicf5        stores a reference clip plus its exact transcript, and clones it
  indic-parler   stores a speaker description, kept byte-identical between calls

Profiles live in service/data/voices/ with a JSON manifest beside the audio, so they
survive restarts and can be copied to another machine with the repository.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from config import DATA_DIR

VOICE_DIR = DATA_DIR / "voices"
MANIFEST = VOICE_DIR / "voices.json"

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

ENGINES = ("indicf5", "indic-parler")


class VoiceError(ValueError):
    pass


def _load() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    try:
        return json.loads(MANIFEST.read_text())
    except json.JSONDecodeError:
        return {}


def _save(data: dict[str, dict]) -> None:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def validate_name(name: str) -> str:
    name = (name or "").strip().lower()
    if not NAME_PATTERN.match(name):
        raise VoiceError(
            "voice name must be lowercase letters, digits, dot, dash or underscore, "
            "1-64 characters — e.g. 'narrator-tamil-anime'"
        )
    return name


def list_voices() -> list[dict[str, Any]]:
    voices = []
    for name, meta in sorted(_load().items()):
        entry = dict(meta, name=name)
        entry["has_reference"] = bool(meta.get("reference_audio"))
        voices.append(entry)
    return voices


def get(name: str) -> dict | None:
    meta = _load().get(name)
    return dict(meta, name=name) if meta else None


def register(name: str, engine: str, *, language: str = "ta",
             reference_audio: Path | None = None, reference_text: str = "",
             voice_description: str = "", notes: str = "") -> dict:
    """Create or replace a voice profile."""
    name = validate_name(name)
    if engine not in ENGINES:
        raise VoiceError(f"engine must be one of: {', '.join(ENGINES)}")

    if engine == "indicf5":
        if reference_audio is None:
            raise VoiceError(
                "indicf5 clones a voice, so 'reference_audio' is required — a few "
                "seconds of clean speech from the narrator you want"
            )
        if not reference_text.strip():
            raise VoiceError(
                "'reference_text' is required: the exact transcript of the reference "
                "clip. Cloning quality depends on it matching the audio."
            )
    elif not voice_description.strip():
        raise VoiceError(
            "indic-parler picks a voice from a description, so 'voice_description' is "
            "required — e.g. 'A calm middle-aged male narrator, measured pace, very "
            "high recording quality.'"
        )

    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    data = _load()

    stored_audio = None
    if reference_audio is not None:
        stored_audio = f"{name}{reference_audio.suffix or '.wav'}"
        shutil.copyfile(reference_audio, VOICE_DIR / stored_audio)

    # Replacing a profile should not leave the previous clip behind.
    previous = data.get(name, {}).get("reference_audio")
    if previous and previous != stored_audio:
        (VOICE_DIR / previous).unlink(missing_ok=True)

    data[name] = {
        "engine": engine,
        "language": language,
        "reference_audio": stored_audio,
        "reference_text": reference_text.strip(),
        "voice_description": voice_description.strip(),
        "notes": notes.strip(),
        "created_at": data.get(name, {}).get("created_at", time.time()),
        "updated_at": time.time(),
    }
    _save(data)
    return dict(data[name], name=name)


def delete(name: str) -> bool:
    data = _load()
    meta = data.pop(name, None)
    if meta is None:
        return False
    if meta.get("reference_audio"):
        (VOICE_DIR / meta["reference_audio"]).unlink(missing_ok=True)
    _save(data)
    return True


def resolve(name: str, engine: str) -> dict:
    """Return a voice profile, checking it suits the engine being called."""
    meta = get(name)
    if meta is None:
        known = ", ".join(v["name"] for v in list_voices()) or "none registered"
        raise VoiceError(f"unknown voice '{name}'. Registered: {known}")
    if meta["engine"] != engine:
        raise VoiceError(
            f"voice '{name}' was registered for {meta['engine']}, not {engine}"
        )
    if meta.get("reference_audio"):
        path = VOICE_DIR / meta["reference_audio"]
        if not path.exists():
            raise VoiceError(f"voice '{name}' has a missing reference clip")
        meta["reference_path"] = path
    return meta
