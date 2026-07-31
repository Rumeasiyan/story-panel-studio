# Characters

Committed **metadata only**. No large source image sets, no LoRA weights.

```text
characters/
├── bibles/     # character bibles: appearance, wardrobe, personality, canon rules
└── manifests/  # machine-readable YAML: prompt fragments, seeds, LoRA references
```

A manifest references a LoRA by filename and licence; the weight itself lives in
`models/loras/` (gitignored) or, for private character LoRAs, `models/private/`.
Private LoRAs should eventually live in a private model registry — never in this
repository.
