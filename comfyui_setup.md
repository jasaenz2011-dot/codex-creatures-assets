# ComfyUI LTX 2.3 Setup — RTX 5070 Ti

## Required Custom Nodes

Install via ComfyUI Manager:

| Package | Purpose |
|---|---|
| `comfyui-ltxvideo` | LTX-specific nodes (LTXVConditioning, LTXVScheduler, VAEDecodeLTXV, EmptyLTXVLatentVideo) |
| `ComfyUI-GGUF` | UnetLoaderGGUF for VRAM-efficient model loading |
| `ComfyUI-VideoHelperSuite` | VHS_VideoCombine for MP4 output |
| `ComfyUI_tiled_diffusion` | Tiled diffusion sampler extension |

## Required Model Files

Place in your ComfyUI `models/` folder:

```
models/
├── unet/
│   └── ltx-video-2b-v2.3.Q8_0.gguf          ← GGUF model
├── clip/
│   └── t5xxl_fp8_e4m3fn.safetensors          ← Text encoder
├── vae/
│   └── ltxv-vae.safetensors                  ← VAE
└── loras/
    └── ltxv-2b-distilled-v0.9.7.safetensors  ← Distilled LoRA (0.95 strength)
```

## Key Settings — Why They Matter on 5070 Ti

| Setting | Value | Reason |
|---|---|---|
| Tiled Diffusion | 512 | Prevents VRAM spike during temporal calc. Without this: blue-screen crash risk |
| Temporal Size | 2048 | Balances quality vs memory for 121-frame sequences |
| Resolution | 1280x736 | 720p, divisible by 32. Safe for 16GB VRAM |
| LoRA Strength | 0.95 | Max quality while maintaining render speed |
| Frames | 121 | 5 seconds @ 24fps — temporal stability sweet spot |

## If You Get OOM (Out of Memory)

1. Open `comfyui_ltx_workflow.json` in ComfyUI
2. Find node: **"Empty Latent — 121 frames @ 720p"**
3. Change width/height to `640 x 368` (also divisible by 32)
4. Re-queue

## Resolution Math Rule

Width and height must always be divisible by 32:

```python
safe_width  = (target_width  // 32) * 32   # 1280 → 1280
safe_height = (target_height // 32) * 32   # 720  → 704 (not 720!)
```

**720p safe values:**
- `1280 x 736` ✓  (not 720 — 720 is not divisible by 32)

**360p fallback:**
- `640 x 368` ✓

## Workflow Usage

1. Load `comfyui_ltx_workflow.json` via **Load** button in ComfyUI
2. Edit **"Prompt — Art Style & Camera"** with your character's visual style
3. Edit **"Prompt — Action & SFX"** with the specific move being animated
4. Queue — renders to `ComfyUI/output/animation_XXXXX.mp4`

## Connecting to Sprite Pipeline

After running `sprite_animation_pipeline.py`, point ComfyUI's
Image-to-Video node at `sprites_output/extracted/<character>/` to
animate extracted sprite sheets automatically.
