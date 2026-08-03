---
name: Task or bug
about: Any unit of work, discovered bug, or open question
title: ''
labels: ''
assignees: Rumeasiyan
---

<!--
Write this for someone who has not seen the conversation it came from.
No "as discussed". If a reader cannot act on it without asking you, it is not finished.
-->

## What

<!-- One or two sentences. What is the thing? -->

## Why it matters

<!--
The concrete consequence of ignoring it. Not "this is bad practice" — what actually
breaks, gets slower, costs money, or cannot be published.
-->

## Where it surfaced

<!-- Paths, pipeline ids, model profiles, doc sections. Real ones. -->

## Options (decisions only)

<!--
Delete if this is not a decision. Otherwise: the realistic choices, what each costs,
which you recommend and why. A decision issue with no recommendation stalls.
-->

## Checklist

Tick anything this touches — these are the areas where a mistake here is expensive.

- [ ] **Security boundary** — ComfyUI binding, or user input reaching graph structure
      (`/prompt` executes arbitrary graphs; this is remote code execution, not a
      preference)
- [ ] **Dependencies** — installs into `.venv`; `transformers` and `torch` must be
      re-checked afterwards (parler-tts silently downgraded transformers once)
- [ ] **Model licence** — commercial terms unresolved or restrictive
      (`reports/MODEL_LICENSES.md`)
- [ ] **Disk** — adds weights; check free space and the manifest first
- [ ] **API contract** — changes a pipeline id, parameter, or response shape a caller
      depends on (MAJOR version bump)
- [ ] **Deletion guarantees** — touches how generations are erased
- [ ] Needs a `VERSION` bump
- [ ] Needs an entry in `docs/DECISIONS.md`
