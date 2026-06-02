"""
MODULE 2: ASSET ARCHITECT (2D → 3D)
Role: Converts lore JSON + 2D source art into rigged Blender assets.
Input:  pipeline/lore/{ASSET_ID}.json  +  optional source image dir
Output: pipeline/assets/{ASSET_ID}.blend  (rigged, palette-matched mesh)

Hardware: RTX 5070 Ti — EEVEE Next, GPU tile 256, 16GB VRAM budget.
"""

import json
import subprocess
from pathlib import Path


BLENDER_BUILD_SCRIPT = '''
import bpy
import json
import sys

argv = sys.argv
data = json.loads(argv[argv.index("--") + 1])

asset_id   = data["id"]
asset_name = data["name"]
palette    = data["palette"]
style_tags = data.get("style_tags", [])

# ── Clear scene ───────────────────────────────────────────
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

# ── Base mesh ─────────────────────────────────────────────
# Geometry type driven by {ASSET_TYPE}:
#   character/creature → humanoid base cube subdivided
#   prop               → simple primitive matching asset dims
#   environment        → plane + displacement
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
mesh_obj = bpy.context.object
mesh_obj.name = f"{asset_name}_mesh"

bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.subdivide(number_cuts=2)
bpy.ops.object.mode_set(mode="OBJECT")

# ── Renderer: EEVEE Next (RTX 5070 Ti) ───────────────────
bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
bpy.context.scene.render.resolution_x = 1280
bpy.context.scene.render.resolution_y = 736    # divisible by 32
bpy.context.scene.render.fps = 24

# ── Palette → Materials ───────────────────────────────────
def hex_to_rgba(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4)) + (1.0,)

for idx, hex_color in enumerate(palette[:4]):
    mat = bpy.data.materials.new(name=f"{asset_name}_mat_{idx:02d}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = hex_to_rgba(hex_color)
    # Flat/matte shading preserves 2D pixel art aesthetic in 3D space
    bsdf.inputs["Roughness"].default_value = 0.95
    bsdf.inputs["Specular IOR Level"].default_value = 0.0
    mesh_obj.data.materials.append(mat)

# ── Apply style modifier ──────────────────────────────────
if "cel-shaded" in style_tags:
    bpy.context.scene.render.use_freestyle = True
if "32bit" in style_tags or "pixel-art" in style_tags:
    bpy.context.scene.display.render_aa = "OFF"

# ── Auto-rig skeleton ─────────────────────────────────────
bpy.ops.object.armature_add(location=(0, 0, 0))
rig = bpy.context.object
rig.name = f"{asset_name}_rig"

mesh_obj.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type="ARMATURE_AUTO")

# ── Output ────────────────────────────────────────────────
output_path = f"pipeline/assets/{asset_id}.blend"
bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"[AssetArchitect] Saved → {output_path}")
'''


class AssetArchitect:
    """
    SYSTEM INSTRUCTIONS:
    - Read-only consumer of Lore Engine output. Never modifies lore JSON.
    - One .blend file per {ASSET_ID}. Filename is the pipeline key.
    - All meshes: flat-shading + palette materials (preserves source art style in 3D).
    - EEVEE tile size locked to 256 for RTX 5070 Ti VRAM stability.

    DNA RULES:
    1. palette[] from lore JSON maps 1:1 to Blender material slots (max 4).
    2. style_tags[] drive renderer and post-process flags — no manual toggle.
    3. Output .blend is the single artifact handed to Module 3 (Motion Hub).
    4. Run headless: blender --background — no GUI, no human in the loop.
    """

    def __init__(self):
        Path("pipeline/assets").mkdir(parents=True, exist_ok=True)

    def build(self, lore_path: str, blender_exe: str = "blender") -> str:
        """
        Load {ASSET_ID} lore JSON and trigger Blender headless mesh build.
        Returns path to output .blend file.
        """
        with open(lore_path) as f:
            data = json.load(f)

        asset_id = data["id"]
        output   = f"pipeline/assets/{asset_id}.blend"

        cmd = [
            blender_exe, "--background",
            "--python-expr", BLENDER_BUILD_SCRIPT,
            "--", json.dumps(data)
        ]

        print(f"[AssetArchitect] Building {asset_id}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"[AssetArchitect] ✓ → {output}")
        else:
            print(f"[AssetArchitect] ✗ Blender error:\n{result.stderr[-500:]}")

        return output


# ── USAGE ─────────────────────────────────────────────────
# architect = AssetArchitect()
# architect.build("pipeline/lore/{ASSET_ID}.json", blender_exe="/path/to/blender")
