# Fonts

Static instances of the system Noto variable fonts, generated because libass mis-shapes
Sinhala and the assembly preview renders subtitles with PIL+raqm instead. Assembly lives
in the orchestrator, so these are a convenience, not a dependency of the service.

Regenerate:

```bash
.venv/bin/pip install fonttools
.venv/bin/python - <<'PY'
from fontTools import ttLib
from fontTools.varLib import instancer
for src, name in [("/usr/share/fonts/google-noto-vf/NotoSansSinhala[wght].ttf",
                   "NotoSansSinhala-Regular.ttf"),
                  ("/usr/share/fonts/google-noto-vf/NotoSansTamil[wght].ttf",
                   "NotoSansTamil-Regular.ttf")]:
    f = ttLib.TTFont(src)
    instancer.instantiateVariableFont(f, {"wght": 400}, inplace=False).save(f"assets/fonts/{name}")
PY
```

Upstream Noto is SIL Open Font License 1.1. Instancing does not change that.

The instances were **not** the fix for Sinhala — libass mis-shapes it with the variable
font and the static instance alike. They exist only so the PIL renderer has a stable
file to load.
