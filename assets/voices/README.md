# Voice anchors

Reference clips for Chatterbox zero-shot cloning. Passed as `audio_prompt_path`;
they define voice identity, which no generation parameter can change.

Not committed — these are renders. Rebuild with the recipe below.

## locked/en.wav

**The locked English narrator** — see `config/generation-locks.yaml`. An 8s trim of the
calm-authoritative sample with **no formant shift**, driven per-beat by Chatterbox's
`exaggeration` and `cfg_weight`.

```bash
ffmpeg -y -i output/voice-samples-chatterbox/en-calm-authoritative.wav \
  -t 8 -ar 24000 -ac 1 assets/voices/locked/en.wav
```

## reel-narrator-v1.wav

Superseded by `locked/en.wav`; kept because earlier reels were made with it.
The +4% shift changes timbre, so swapping the two changes the narrator.


English reel narrator. Chatterbox stock speaker, formants shifted up 4% so the
voice reads younger. Resampling shifts pitch and formants together; formants track
vocal-tract length, which is what actually carries perceived age. Pitch-only
shifting sounds like a filter.

Chosen by ear over +8% and +12%, which were audibly thin.

```bash
SRC=output/voice-samples-chatterbox/en-calm-authoritative.wav
ffmpeg -y -i "$SRC" -t 8 -ar 24000 -ac 1 /tmp/_base.wav
ffmpeg -y -i /tmp/_base.wav \
  -af "asetrate=24000*1.04,aresample=24000,atempo=1/1.04" \
  -ar 24000 -ac 1 assets/voices/reel-narrator-v1.wav
```

Replacing this file changes the voice of every reel. Add a `-v2` instead.
