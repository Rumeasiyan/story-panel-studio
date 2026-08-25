# Virtualenv locks

`pip freeze` of each isolated venv. These exist because the venvs are large (~25 GB
total) and get deleted during disk cleanups, and until now two of them had **no
rebuild path at all** — `.venv-parler` and `.venv-chatterbox` were built by hand.

`.venv` is rebuilt by `bootstrap.sh --core-only`; `.venv-trainer` by
`./scripts/train-lora --check`. Those two do not depend on the locks here.
`.venv-omnivoice` is locked here as well.

Rebuild any of the others:

```bash
python3 -m venv .venv-<name>
.venv-<name>/bin/pip install --upgrade pip
.venv-<name>/bin/pip install -r config/venv-locks/<name>.lock.txt
```

## Gotchas that cost time before

- **chatterbox** — `perth.PerthImplicitWatermarker` comes back as `None` and generation
  dies with `TypeError: 'NoneType' object is not callable` on setuptools >= 81, which
  dropped `pkg_resources`. The lock pins `setuptools==80.10.2`. Keep it there.
- **chatterbox** — the first lock pinned `torch==2.6.0+cu124`, and that turned out to be
  unreconstructable: no cu124 build of 2.6.0 is published for cp313 on either the default
  index or the cu124 index, so `pip install -r` failed outright. The lock now records
  torch 2.13.0+cu130, which chatterbox-tts resolves to on its own and which is verified
  working here. **A pip freeze is not automatically reproducible** — it pins versions that
  the index may later stop serving. If this lock stops resolving too, install
  `chatterbox-tts soundfile` unpinned, then re-pin `setuptools<81` and refreeze.
- **Downloading weights** — set `HF_HUB_DISABLE_XET=1`. The xet transport stalls at
  ~1.3 KB/s here; disabling it gives ~2.7 MB/s. Hit twice, on two different models.
- **Never install any of these into `.venv`.** parler pins `transformers==4.46.1` and the
  trainer pins `4.54.1`; ComfyUI needs `>=4.50.3`. That is what the isolation is for.
