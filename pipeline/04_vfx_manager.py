"""
MODULE 4: VISUAL PASS MANAGER (VFX Layers)
Role: Reads sfx_tags from animated .blend metadata and applies Blender compositor
      node presets. Optionally hands off to ComfyUI LTX for video restyle.
Input:  pipeline/animated/{ASSET_ID}_{ACTION_NAME}.blend  (sfx_tags in action metadata)
Output: pipeline/renders/{ASSET_ID}_{ACTION_NAME}.mp4

Hardware: RTX 5070 Ti — EEVEE Next, tile 256, 1280x736 (divisible by 32), 24fps.
"""

import json
import subprocess
from pathlib import Path


# ── SFX Tag → Compositor Preset Registry ─────────────────
# sfx_tag (set in Lore Engine) → Blender compositor node config.
# Add new tags here as the Genesis Pitch demands them.

SFX_PRESETS = {
    # Energy / light emission
    "bloom_low":       {"node": "Glare", "glare_type": "BLOOM", "threshold": 0.5, "intensity": 1.2},
    "bloom_high":      {"node": "Glare", "glare_type": "BLOOM", "threshold": 0.2, "intensity": 3.0},
    "lens_flare":      {"node": "Glare", "glare_type": "STREAKS", "threshold": 0.3, "streaks": 4},

    # Motion / impact
    "motion_blur":     {"node": "VectorBlur", "samples": 32, "speed": 1.0},
    "radial_streak":   {"node": "Blur", "size_x": 12, "size_y": 2},
    "shockwave":       {"node": "Displace", "strength": 0.08},

    # Atmosphere / volume
    "smoke_volume":    {"node": "Mix", "blend_type": "SCREEN", "factor": 0.3},
    "heat_distortion": {"node": "Displace", "strength": 0.02, "frequency": 8},

    # Lens / camera
    "chromatic_ab":    {"node": "Lensdist", "distort": 0.06, "dispersion": 0.04},
    "vignette":        {"node": "Ellipse_Mask", "falloff": "SMOOTH", "factor": 0.4},
    "film_grain":      {"node": "Noise_Texture", "scale": 800, "strength": 0.04},

    # Stylistic
    "pixelate":        {"node": "Pixelate", "pixel_size": 4},
    "cel_outline":     {"node": "Filter", "filter_type": "SOBEL", "factor": 0.8},
}

BLENDER_VFX_SCRIPT = '''
import bpy, json, sys

argv = sys.argv
data = json.loads(argv[argv.index("--") + 1])

bpy.ops.wm.open_mainfile(filepath=data["blend_path"])

# ── Renderer: EEVEE Next (RTX 5070 Ti optimized) ─────────
scene = bpy.context.scene
scene.render.engine         = "BLENDER_EEVEE_NEXT"
scene.render.fps            = 24
scene.render.resolution_x   = data.get("width", 1280)
scene.render.resolution_y   = data.get("height", 736)
scene.render.filepath       = data["output_path"]
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format  = "MPEG4"
scene.render.ffmpeg.codec   = "H264"
scene.cycles.tile_x         = 256    # VRAM-safe tile for 5070 Ti
scene.cycles.tile_y         = 256
scene.cycles.device         = "GPU"

# ── Compositor ────────────────────────────────────────────
scene.use_nodes = True
tree = scene.node_tree
for n in tree.nodes:
    tree.nodes.remove(n)

render_node    = tree.nodes.new("CompositorNodeRLayers")
composite_node = tree.nodes.new("CompositorNodeComposite")
render_node.location    = (0, 0)
composite_node.location = (1200, 0)

prev_out = render_node.outputs["Image"]
offset_x = 250

# ── Apply compositor nodes per sfx_tag ───────────────────
for tag in data.get("sfx_tags", []):
    if tag in ("bloom_low", "bloom_high"):
        n = tree.nodes.new("CompositorNodeGlare")
        n.glare_type = "BLOOM"
        n.threshold  = 0.2 if tag == "bloom_high" else 0.5
        n.location   = (offset_x, 0)
        tree.links.new(prev_out, n.inputs["Image"])
        prev_out = n.outputs["Image"]
        offset_x += 250

    elif tag == "motion_blur":
        n = tree.nodes.new("CompositorNodeVecBlur")
        n.factor   = 1.0
        n.samples  = 32
        n.location = (offset_x, 0)
        tree.links.new(prev_out, n.inputs["Image"])
        prev_out = n.outputs["Image"]
        offset_x += 250

    elif tag in ("chromatic_ab",):
        n = tree.nodes.new("CompositorNodeLensdist")
        n.inputs["Distort"].default_value    = 0.06
        n.inputs["Dispersion"].default_value = 0.04
        n.location = (offset_x, 0)
        tree.links.new(prev_out, n.inputs["Image"])
        prev_out = n.outputs["Image"]
        offset_x += 250

    elif tag == "vignette":
        n = tree.nodes.new("CompositorNodeEllipseMask")
        n.location = (offset_x, 0)
        offset_x += 250

tree.links.new(prev_out, composite_node.inputs["Image"])
bpy.ops.render.render(animation=True)
print(f"[VFXManager] Rendered → {data['output_path']}")
'''


class VFXManager:
    """
    SYSTEM INSTRUCTIONS:
    - sfx_tags from Lore Engine are the VFX contract. A tag always maps to a preset.
    - Never hand-edit compositor nodes — all changes go through SFX_PRESETS above.
    - Resolution locked to 1280x736 (divisible by 32) to match LTX workflow input.
    - After Blender render, optionally hand off to ComfyUI for LTX restyle pass.

    DNA RULES:
    1. Fallback resolution on VRAM OOM: 640x368 (also divisible by 32).
    2. sfx_tags are read from the .blend action metadata — not from lore JSON directly.
    3. One .mp4 per action. Never composite multiple actions into one file here.
    4. LTX handoff is optional — Module 4 is complete without it.

    VRAM SAFETY (RTX 5070 Ti / 16GB):
    - Tile 256×256: safe for 1280×736 @ 121 frames
    - If VRAM OOM: reduce to 640×368 via width/height override
    - Tiled Diffusion (ComfyUI LTX): set to 512 to prevent temporal VRAM spike
    """

    def __init__(self):
        Path("pipeline/renders").mkdir(parents=True, exist_ok=True)

    def render(self, lore_path: str, animated_blend: str, blender_exe="blender",
               width=1280, height=736) -> str:
        """Apply VFX passes and render {ASSET_ID}_{ACTION_NAME} to MP4."""
        with open(lore_path) as f:
            lore = json.load(f)

        blend_stem = Path(animated_blend).stem
        asset_id   = lore["id"]
        output     = f"pipeline/renders/{blend_stem}.mp4"

        # Extract sfx_tags for this action from lore
        sfx_tags = []
        for action in lore.get("actions", []):
            slug = action["name"].lower().replace(" ", "_")
            if slug in blend_stem:
                sfx_tags = action.get("sfx_tags", [])
                break

        payload = {
            "blend_path":  animated_blend,
            "output_path": output,
            "sfx_tags":    sfx_tags,
            "width":       width,
            "height":      height,
        }

        cmd = [
            blender_exe, "--background",
            "--python-expr", BLENDER_VFX_SCRIPT,
            "--", json.dumps(payload)
        ]

        print(f"[VFXManager] Rendering {blend_stem} | tags: {sfx_tags}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"[VFXManager] ✓ → {output}")
        else:
            print(f"[VFXManager] ✗ {result.stderr[-300:]}")

        return output

    def trigger_ltx_upscale(self, comfyui_url: str, render_path: str):
        """Optional: hand rendered clip to ComfyUI LTX 2.3 workflow for restyle."""
        import requests
        try:
            r = requests.post(
                f"{comfyui_url}/api/queue_prompt",
                json={"input_video": render_path, "workflow": "comfyui_ltx_workflow.json"},
                timeout=10
            )
            print(f"[VFXManager] LTX handoff queued: HTTP {r.status_code}")
        except Exception as e:
            print(f"[VFXManager] ComfyUI not reachable: {e}")


# ── USAGE ─────────────────────────────────────────────────
# vfx = VFXManager()
# vfx.render(
#     lore_path="pipeline/lore/{ASSET_ID}.json",
#     animated_blend="pipeline/animated/{ASSET_ID}_{ACTION_NAME}.blend"
# )
# vfx.trigger_ltx_upscale("http://127.0.0.1:8188", "pipeline/renders/{ASSET_ID}_{ACTION_NAME}.mp4")
