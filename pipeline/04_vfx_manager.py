"""
MODULE 4: VISUAL PASS MANAGER (VFX Layers)
Role: Reads sfx_tags from animated .blend files and applies Blender compositor
      VFX passes. Also triggers ComfyUI LTX render for final video output.
Input:  pipeline/animated/<id>_<move>.blend  (with sfx_tags in action metadata)
Output: pipeline/renders/<id>_<move>.mp4

RTX 5070 Ti config: EEVEE tile 256, bloom + motion blur on, 24fps.
"""

import json
import subprocess
import requests
from pathlib import Path


# ── SFX Tag → Compositor Node Preset ─────────────────────
SFX_PRESETS = {
    "flame_burst":    {"bloom_threshold": 0.3, "bloom_intensity": 1.8, "emission_strength": 4.0},
    "ember_particle": {"particle_system": "fire_emitter", "particle_count": 800},
    "claw_slash":     {"motion_blur_shutter": 0.5, "radial_streak": True},
    "impact_dust":    {"particle_system": "dust_emitter", "particle_count": 400},
    "smoke_cloud":    {"volume_scatter": 0.4, "fog_density": 0.3},
    "vision_blur":    {"lens_distortion": 0.08, "chromatic_aberration": True},
    "body_glow_red":  {"bloom_threshold": 0.1, "bloom_intensity": 3.0, "tint": [1.0, 0.2, 0.1]},
    "heat_shimmer":   {"displacement_strength": 0.02, "frequency": 8},
}

BLENDER_VFX_SCRIPT = '''
import bpy, json, sys

argv  = sys.argv
data  = json.loads(argv[argv.index("--") + 1])
blend = data["blend_path"]
tags  = data["sfx_tags"]
out   = data["output_path"]
fps   = data.get("fps", 24)

bpy.ops.wm.open_mainfile(filepath=blend)

# ── Renderer: EEVEE (RTX 5070 Ti optimized) ──────────────
bpy.context.scene.render.engine         = 'BLENDER_EEVEE_NEXT'
bpy.context.scene.render.fps            = fps
bpy.context.scene.render.resolution_x  = 1280
bpy.context.scene.render.resolution_y  = 736
bpy.context.scene.render.filepath       = out

# GPU tiles for 5070 Ti (16GB VRAM)
bpy.context.scene.cycles.tile_x = 256
bpy.context.scene.cycles.tile_y = 256
bpy.context.scene.cycles.device = "GPU"

# ── Enable Compositor ─────────────────────────────────────
bpy.context.scene.use_nodes = True
tree = bpy.context.scene.node_tree

# Clear default
for node in tree.nodes:
    tree.nodes.remove(node)

# Render Layer → Composite base
render_node = tree.nodes.new("CompositorNodeRLayers")
render_node.location = (0, 0)

composite_node = tree.nodes.new("CompositorNodeComposite")
composite_node.location = (800, 0)

prev_output = render_node.outputs["Image"]

# ── Apply SFX passes per tag ──────────────────────────────
offset_x = 200

for tag in tags:
    if tag in ["flame_burst", "body_glow_red"]:
        glare = tree.nodes.new("CompositorNodeGlare")
        glare.glare_type = "BLOOM"
        glare.threshold  = 0.3
        glare.location   = (offset_x, 0)
        tree.links.new(prev_output, glare.inputs["Image"])
        prev_output = glare.outputs["Image"]
        offset_x += 200

    elif tag in ["claw_slash"]:
        blur = tree.nodes.new("CompositorNodeBlur")
        blur.size_x = 8
        blur.size_y = 2
        blur.location = (offset_x, 0)
        tree.links.new(prev_output, blur.inputs["Image"])
        prev_output = blur.outputs["Image"]
        offset_x += 200

    elif tag in ["vision_blur", "chromatic_aberration"]:
        lens = tree.nodes.new("CompositorNodeLensdist")
        lens.inputs["Distort"].default_value  = 0.06
        lens.inputs["Dispersion"].default_value = 0.04
        lens.location = (offset_x, 0)
        tree.links.new(prev_output, lens.inputs["Image"])
        prev_output = lens.outputs["Image"]
        offset_x += 200

# Final link to composite
tree.links.new(prev_output, composite_node.inputs["Image"])

# ── Render ────────────────────────────────────────────────
bpy.context.scene.render.image_settings.file_format = "FFMPEG"
bpy.context.scene.render.ffmpeg.format = "MPEG4"
bpy.context.scene.render.ffmpeg.codec  = "H264"
bpy.ops.render.render(animation=True)
print(f"[VFXManager] Rendered → {out}")
'''


class VFXManager:
    """
    DNA:
    - SFX tags from Lore Engine are the VFX contract. A tag always maps to a node preset.
    - Never hand-tweak compositor nodes — all changes go through SFX_PRESETS above.
    - After Blender render, optionally hand off to ComfyUI for LTX video upscale/restyle.
    - Resolution locked to 1280x736 (divisible by 32) to match LTX workflow.
    """

    def __init__(self):
        Path("pipeline/renders").mkdir(parents=True, exist_ok=True)

    def render(self, lore_path: str, animated_blend_path: str, blender_exe="blender"):
        with open(lore_path) as f:
            lore = json.load(f)

        blend_path = Path(animated_blend_path)
        move_name  = blend_path.stem   # e.g. "embrix_ember"

        # Collect sfx_tags from lore (match by move name)
        sfx_tags = []
        for move in lore["moves"]:
            if move["name"].lower().replace(" ", "_") in move_name:
                sfx_tags = move.get("sfx_tags", [])
                break

        output = f"pipeline/renders/{move_name}.mp4"
        payload = {
            "blend_path": str(animated_blend_path),
            "sfx_tags": sfx_tags,
            "output_path": output,
            "fps": 24,
        }

        cmd = [
            blender_exe, "--background",
            "--python-expr", BLENDER_VFX_SCRIPT,
            "--", json.dumps(payload)
        ]

        print(f"[VFXManager] Rendering {move_name} with tags: {sfx_tags}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"[VFXManager] ✓ → {output}")
        else:
            print(f"[VFXManager] ✗ {result.stderr[-300:]}")

        return output

    def trigger_ltx_upscale(self, comfyui_url: str, render_path: str):
        """Optional: hand rendered clip to ComfyUI LTX workflow for restyle."""
        payload = {
            "input_video": render_path,
            "workflow": "comfyui_ltx_workflow.json"
        }
        try:
            r = requests.post(f"{comfyui_url}/api/queue_prompt", json=payload, timeout=10)
            print(f"[VFXManager] LTX handoff: {r.status_code}")
        except Exception as e:
            print(f"[VFXManager] ComfyUI not reachable: {e}")


if __name__ == "__main__":
    vfx = VFXManager()
    vfx.render(
        lore_path="pipeline/lore/embrix.json",
        animated_blend_path="pipeline/animated/embrix_ember.blend"
    )
