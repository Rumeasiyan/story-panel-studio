# Environment snapshot

- Generated: 2026-08-26T02:13:31+05:30
- Project root: `/home/sshroot/external/story-panel-studio`

## System

| Item | Value |
|---|---|
| Fedora | Fedora release 43 (Forty Three) |
| Kernel | 7.1.8-100.fc43.x86_64 |
| Session | wayland / Hyprland |
| GPU | NVIDIA GeForce RTX 3050 |
| NVIDIA driver | 580.178.04 |
| VRAM | 8192 MiB |
| RAM | 31Gi |
| Secure Boot | SecureBoot enabled |

## Software

| Item | Value |
|---|---|
| Git | 2.55.0 |
| Python (.venv) | 3.13.14 |
| pip | 26.2.1 |
| PyTorch | 2.13.0+cu130 |
| PyTorch CUDA runtime | 13.0 |
| torch.cuda.is_available() | True |
| FFmpeg | 7.1.5 |
| ComfyUI commit | `7a054eb472d4f911ad3ed1d943f6e7de4d67730f` |
| ComfyUI subject | comfy-aimdo 0.4.15 (#15886) |

## Custom nodes

_none installed_

## Model profiles

```
active profile : wan22-ti2v-5b
project root   : /home/sshroot/external/story-panel-studio
free space     : 124.16 GB

  anime-sdxl       installed
  cinematic-sdxl   installed
  wan22-ti2v-5b    not installed
      missing                  models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors (10.00 GB)
      missing                  models/vae/wan2.2_vae.safetensors (1.41 GB)
      missing                  models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors (6.74 GB)
  flux2-klein-4b   installed
  wan21-fun-inp-1.3b not installed
      missing                  models/diffusion_models/wan2.1_fun_inp_1.3B_bf16.safetensors (3.13 GB)
      missing                  models/vae/wan_2.1_vae.safetensors (253.82 MB)
      missing                  models/clip_vision/clip_vision_h.safetensors (1.26 GB)
      missing                  models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors (6.74 GB)
  sdxl-lightning   installed
  noobai-xl        installed
  illustrious-xl   installed
  z-image-turbo    installed

models/ on disk : 52.93 GB
missing/invalid : 29.53 GB would need downloading

recorded installs:
  anime-sdxl:animagine-xl-4-opt: rev 2b7c1b397761 at 2026-08-01T05:39:34+05:30
  cinematic-sdxl:realvisxl-v4: rev 26dfe4493096 at 2026-08-01T07:45:53+05:30
  flux2-klein-4b:flux2-klein-4b-fp8: rev 5b4408e59397 at 2026-08-01T08:01:41+05:30
  flux2-klein-4b:flux2-vae: rev 03d6521e6f6a at 2026-08-01T08:34:07+05:30
  flux2-klein-4b:qwen3-4b-text-encoder: rev d24c4cf2a0cd at 2026-08-01T08:32:38+05:30
  illustrious-xl:illustrious-xl-20: rev 69459c1fe6f4 at 2026-08-03T23:50:25+05:30
  sdxl-lightning:sdxl-lightning-2step: rev c9a24f48e1c0 at 2026-08-03T21:10:25+05:30
  sdxl-lightning:sdxl-lightning-4step: rev c9a24f48e1c0 at 2026-08-03T21:06:10+05:30
  wan21-fun-inp-1.3b:clip-vision-h: rev 06e001fc5104 at 2026-08-01T04:56:31+05:30
  wan21-fun-inp-1.3b:wan21-fun-inp-1.3b: rev 06e001fc5104 at 2026-08-01T04:50:21+05:30
  wan21-fun-inp-1.3b:wan21-vae: rev 06e001fc5104 at 2026-08-01T04:51:07+05:30
  wan22-ti2v-5b:umt5-xxl-fp8-scaled: rev fb1388adc906 at 2026-08-01T03:42:38+05:30
  wan22-ti2v-5b:wan22-ti2v-5b: rev fb1388adc906 at 2026-08-01T03:08:32+05:30
  wan22-ti2v-5b:wan22-vae: rev fb1388adc906 at 2026-08-01T03:14:24+05:30
  z-image-turbo:z-image-turbo-int8: rev d24c4cf2a0cd at 2026-08-04T00:07:10+05:30
  z-image-turbo:z-image-vae: rev d24c4cf2a0cd at 2026-08-04T00:11:09+05:30
```

## Disk usage

```
  models                   52.93 GB
    checkpoints            27.92 GB
    diffusion_models       10.27 GB
    text_encoders           8.04 GB
    vae                   503.43 MB
    loras                 873.13 MB
  input                           ?
  output                  168.57 MB
  temp                            ?
  cache                     1.44 MB
  logs                      3.88 MB
  user                     17.62 MB
  .venv                     6.44 GB
  engine/ComfyUI           58.68 MB

  project total            68.12 GB
  free on volume          124.16 GB
Filesystem                                             Size  Used Avail Use% Mounted on
/dev/mapper/luks-7a83c357-2176-4a75-b6c7-d56d23ad2e94  236G  113G  116G  50% /home
```

## pip freeze

```
aiohappyeyeballs==2.7.1
aiohttp==3.14.3
aiosignal==1.4.0
alembic==1.19.1
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.14.2
attrs==26.1.0
av==18.1.0
blake3==1.0.9
certifi==2026.7.22
cffi==2.1.1
chardet==7.6.0
charset-normalizer==3.5.1
click==8.4.2
comfy-aimdo==0.4.15
comfy-angle==0.1.1
comfy-kitchen==0.2.31
comfyui-embedded-docs==0.5.10
comfyui-manager==4.2.2
comfyui-workflow-templates-core==0.3.320
comfyui-workflow-templates-json==0.1.55
comfyui-workflow-templates-media-api==0.3.84
comfyui-workflow-templates-media-assets-01==0.1.33
comfyui-workflow-templates-media-image==0.3.160
comfyui-workflow-templates-media-other==0.3.229
comfyui-workflow-templates-media-video==0.3.101
comfyui_frontend_package==1.49.6
comfyui_workflow_templates==0.11.46
cryptography==50.0.1
cuda-bindings==13.3.1
cuda-pathfinder==1.6.0
cuda-toolkit==13.0.3.0
einops==0.8.2
fastapi==0.141.1
filelock==3.32.3
frozenlist==1.8.0
fsspec==2026.7.0
gitdb==4.0.12
GitPython==3.1.60
greenlet==3.5.5
h11==0.16.0
hf-xet==1.6.0
httpcore==1.0.9
httptools==0.8.0
httpx==0.28.1
huggingface_hub==1.28.0
idna==3.19
Jinja2==3.1.6
kornia==0.8.3
kornia_rs==0.1.14
Mako==1.4.1
markdown-it-py==4.2.0
MarkupSafe==3.0.3
mdurl==0.1.2
mpmath==1.3.0
multidict==6.7.1
networkx==3.6.1
numpy==2.5.2
nvidia-cublas==13.1.1.3
nvidia-cuda-cupti==13.0.85
nvidia-cuda-nvrtc==13.0.88
nvidia-cuda-runtime==13.0.96
nvidia-cudnn-cu13==9.20.0.48
nvidia-cufft==12.0.0.61
nvidia-cufile==1.15.1.6
nvidia-curand==10.4.0.35
nvidia-cusolver==12.0.4.66
nvidia-cusparse==12.6.3.3
nvidia-cusparselt-cu13==0.8.1
nvidia-nccl-cu13==2.29.7
nvidia-nvjitlink==13.3.33
nvidia-nvshmem-cu13==3.4.5
nvidia-nvtx==13.0.85
packaging==26.3
pillow==12.3.0
propcache==0.5.2
psutil==7.2.2
pycparser==3.0
pydantic==2.13.4
pydantic-settings==2.15.0
pydantic_core==2.46.4
PyGithub==2.10.0
Pygments==2.21.0
PyJWT==2.13.0
PyNaCl==1.6.2
PyOpenGL==3.1.10
python-dotenv==1.2.3
python-multipart==0.0.32
PyYAML==6.0.3
regex==2026.7.19
requests==2.34.2
rich==15.0.0
safetensors==0.8.0
scipy==1.18.1
sentencepiece==0.2.2
setuptools==84.0.0
shellingham==1.5.4
simpleeval==1.0.7
smmap==5.0.3
spandrel==0.4.2
SQLAlchemy==2.0.52
starlette==1.6.0
sympy==1.14.0
tokenizers==0.22.2
toml==0.10.2
torch==2.13.0+cu130
torchaudio==2.11.0+cu130
torchsde==0.2.6
torchvision==0.28.0+cu130
tqdm==4.70.0
trampoline==0.1.2
transformers==5.15.1
triton==3.7.1
typer==0.27.1
typing-inspection==0.4.4
typing_extensions==4.16.0
urllib3==2.7.0
uv==0.12.6
uvicorn==0.52.4
uvloop==0.22.1
watchfiles==1.2.0
websockets==17.0.1
wheel==0.48.0
yarl==1.24.5
```
