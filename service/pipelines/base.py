"""Pipeline contract.

A pipeline is one generation capability: text-to-image, image editing, video,
text-to-speech, subtitles. Each declares the parameters it accepts and knows how to
produce its outputs. The API layer stays generic — adding a capability means adding a
module here and registering it, not touching routes.

Two execution styles:

  ComfyPipeline  builds a ComfyUI API graph; the worker submits it and follows progress
                 over the WebSocket.
  LocalPipeline  runs in-process (TTS, subtitle alignment) and reports progress itself.

User input never becomes graph structure. Pipelines fill typed fields into a fixed
template, because ComfyUI's /prompt executes whatever graph it receives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

Kind = Literal["image", "video", "audio", "subtitle"]


@dataclass
class Param:
    """One accepted parameter, with the validation the API applies before use."""

    name: str
    type: Literal["str", "int", "float", "bool", "enum", "file"]
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    choices: list[Any] | None = None
    required: bool = False
    help: str = ""
    # Optional per-parameter normaliser, e.g. snapping to a multiple of 16.
    snap: Callable[[Any], Any] | None = None

    def describe(self) -> dict:
        out = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "help": self.help,
        }
        if self.default is not None:
            out["default"] = self.default
        if self.minimum is not None:
            out["min"] = self.minimum
        if self.maximum is not None:
            out["max"] = self.maximum
        if self.choices is not None:
            out["choices"] = self.choices
        return out


@dataclass
class Pipeline:
    id: str
    kind: Kind
    title: str
    description: str
    params: list[Param] = field(default_factory=list)
    # Model profile from config/model-profiles.yaml this pipeline needs installed.
    requires_profile: str | None = None
    # Files this pipeline accepts as uploads, e.g. ["image", "reference"].
    accepts_files: list[str] = field(default_factory=list)

    def describe(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "requires_profile": self.requires_profile,
            "accepts_files": self.accepts_files,
            "params": [p.describe() for p in self.params],
        }

    def param(self, name: str) -> Param | None:
        return next((p for p in self.params if p.name == name), None)


@dataclass
class ComfyPipeline(Pipeline):
    """Runs through ComfyUI."""

    build: Callable[[dict, dict[str, str]], dict] | None = None
    # Which output kinds to keep from the history entry.
    output_keys: tuple[str, ...] = ("images", "videos", "gifs", "audio")


@dataclass
class LocalPipeline(Pipeline):
    """Runs in this process. `run` returns a list of produced file paths."""

    run: Callable[[dict, dict[str, Path], Callable[[float, str], None]], list[Path]] | None = None


REGISTRY: dict[str, Pipeline] = {}


def register(pipeline: Pipeline) -> Pipeline:
    REGISTRY[pipeline.id] = pipeline
    return pipeline


def get(pipeline_id: str) -> Pipeline | None:
    return REGISTRY.get(pipeline_id)


def all_pipelines() -> list[Pipeline]:
    return list(REGISTRY.values())
