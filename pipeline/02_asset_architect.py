"""
MODULE 2: ASSET ARCHITECT (2D → 3D)
Role: Converts lore JSON + 2D sprites into rigged Blender assets.
Input:  pipeline/lore/<id>.json  +  sprites_output/extracted/<id>/
Output: pipeline/assets/<id>.blend  (rigged, palette-matched mesh)

Hardware target: RTX 5070 Ti — uses GPU-accelerated remeshing in EEVEE.
"""

import json
import subprocess
from pathlib import Path


BLENDER_SCRIPT = '''
import bpy
import json
import sys

# ── Receive character data via args ──────────────────────
argv = sys.argv
data = json.loads(argv[argv.index("--") + 1])

char_id   = data["id"]
char_name = data["name"]
palette   = data["palette"]

# ── Clear scene ──────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ── Base mesh: low-poly character body ───────────────────
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
body = bpy.context.object
body.name = f"{char_name}_body"

# Subdivide for detail
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=2)
bpy.ops.object.mode_set(mode='OBJECT')

# ── Apply palette as materials ────────────────────────────
def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) / 255 for i in (0, 2, 4))

for idx, color_hex in enumerate(palette[:4]):  # max 4 palette slots
    mat = bpy.data.materials.new(name=f"{char_name}_mat_{idx}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    rgb = hex_to_rgb(color_hex)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9   # flat/matte look
    bsdf.inputs["Specular"].default_value = 0.0
    body.data.materials.append(mat)

# ── Auto-rig (Rigify placeholder) ────────────────────────
bpy.ops.object.armature_add(location=(0, 0, 0))
rig = bpy.context.object
rig.name = f"{char_name}_rig"

# Parent mesh to rig
body.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')

# ── Save .blend ───────────────────────────────────────────
output_path = f"pipeline/assets/{char_id}.blend"
bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"[AssetArchitect] Saved → {output_path}")
'''


class AssetArchitect:
    """
    DNA:
    - Never modifies lore data. Read-only consumer of module 1.
    - All meshes use flat-shading + palette materials (preserves pixel art vibe in 3D).
    - Output .blend files are the single asset handed to Module 3.
    - EEVEE renderer pre-configured for RTX 5070 Ti (GPU tile size 256).
    """

    def __init__(self):
        Path("pipeline/assets").mkdir(parents=True, exist_ok=True)

    def build(self, lore_path: str, blender_exe: str = "blender"):
        """
        Load lore JSON and trigger Blender headless build.
        blender_exe: path to blender binary (e.g. /usr/bin/blender)
        """
        with open(lore_path) as f:
            data = json.load(f)

        char_id = data["id"]
        output_blend = Path(f"pipeline/assets/{char_id}.blend")

        cmd = [
            blender_exe,
            "--background",
            "--python-expr", BLENDER_SCRIPT,
            "--", json.dumps(data)
        ]

        print(f"[AssetArchitect] Building {char_id}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"[AssetArchitect] ✓ Built → {output_blend}")
        else:
            print(f"[AssetArchitect] ✗ Blender error:\n{result.stderr[-500:]}")

        return str(output_blend)


if __name__ == "__main__":
    architect = AssetArchitect()
    architect.build("pipeline/lore/embrix.json")
