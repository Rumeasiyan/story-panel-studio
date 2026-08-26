"""Render subtitle cues to PNG overlays instead of burning them with libass.

libass mis-shapes Sinhala: vowel signs detach and reposition, while Pango and PIL+raqm
render the identical string and font correctly, so it is a shaping bug rather than a
missing font. ffmpeg's subtitles filter exposes no shaper control, so the text is
rendered outside libass and overlaid as images. Used for every language so all three
channels look identical.
"""
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONTS = {
    "en": "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    "ta": "assets/fonts/NotoSansTamil-Regular.ttf",
    "si": "assets/fonts/NotoSansSinhala-Regular.ttf",
}

def parse_srt(path: Path):
    cues, block = [], []
    for raw in path.read_text(encoding="utf-8").splitlines() + [""]:
        if raw.strip():
            block.append(raw)
            continue
        if len(block) >= 3:
            m = re.match(r"(\d\d):(\d\d):(\d\d,\d\d\d) --> (\d\d):(\d\d):(\d\d,\d\d\d)", block[1])
            if m:
                g = [float(x.replace(",", ".")) for x in m.groups()]
                cues.append((g[0]*3600+g[1]*60+g[2], g[3]*3600+g[4]*60+g[5],
                             " ".join(block[2:]).strip()))
        block = []
    return cues

def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines[:3]

def render(lang, srt, outdir, size=54):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(FONTS[lang], size)
    cues = parse_srt(Path(srt))
    made = []
    for i, (s, e, text) in enumerate(cues):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        lines = wrap(d, text, font, W - 120)
        lh = int(size * 1.35)
        y = H - 200 - lh*len(lines)
        for ln in lines:
            tw = d.textlength(ln, font=font)
            x = (W - tw) / 2
            d.text((x, y), ln, font=font, fill=(255, 255, 255, 255),
                   stroke_width=4, stroke_fill=(0, 0, 0, 255))
            y += lh
        p = outdir / f"{lang}-{i:03d}.png"
        img.save(p)
        made.append((p, s, e))
    return made

if __name__ == "__main__":
    import sys
    lang = sys.argv[1]
    made = render(lang, f"output/e2e/subs-{lang}.srt", f"/tmp/subs-{lang}")
    print(f"  {lang}: {len(made)} cue images")
