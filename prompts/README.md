# Prompt library

Committed plain-text prompt building blocks. Small files only — no media.

```text
prompts/
├── anime/      # style, lighting and shot fragments for the anime SDXL profile
├── cinematic/  # fragments for the realistic/cinematic SDXL profile
├── negative/   # reusable negative prompts
└── templates/  # full prompt skeletons with {placeholders}
```

Convention: one idea per `.txt` file, lowercase kebab-case filenames, comma-separated
tags on a single line so fragments can be concatenated.

Keep story text for English and Tamil productions here too, as `.md` or `.txt`.
