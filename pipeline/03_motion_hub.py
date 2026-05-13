"""
MODULE 3: MOTION & PERFORMANCE HUB
Role: Applies animations to rigged .blend assets using move data from Lore Engine.
Input:  pipeline/assets/<id>.blend  +  lore move list (motion_tags)
Output: pipeline/animated/<id>_<move>.blend  (keyed animation per move)

Motion tags from Lore Engine map to animation templates defined here.
"""

import json
import subprocess
from pathlib import Path


# ── Motion Tag → Keyframe Template Mapping ───────────────
MOTION_TEMPLATES = {
    "projectile_forward": {
        "description": "Wind-up → release → follow-through",
        "keyframes": [
            {"frame": 1,   "pose": "idle"},
            {"frame": 6,   "pose": "wind_up"},
            {"frame": 12,  "pose": "release"},
            {"frame": 18,  "pose": "follow_through"},
            {"frame": 24,  "pose": "idle"},
        ],
        "root_motion": {"x": 0.2, "y": 0, "z": 0},
    },
    "melee_swipe": {
        "description": "Dash → strike → recoil",
        "keyframes": [
            {"frame": 1,   "pose": "idle"},
            {"frame": 4,   "pose": "dash_start"},
            {"frame": 8,   "pose": "strike_peak"},
            {"frame": 14,  "pose": "recoil"},
            {"frame": 20,  "pose": "idle"},
        ],
        "root_motion": {"x": 0.6, "y": 0, "z": 0},
    },
    "area_emit": {
        "description": "Charge → burst → sustain",
        "keyframes": [
            {"frame": 1,   "pose": "idle"},
            {"frame": 8,   "pose": "charge"},
            {"frame": 16,  "pose": "burst"},
            {"frame": 30,  "pose": "sustain"},
            {"frame": 36,  "pose": "idle"},
        ],
        "root_motion": {"x": 0, "y": 0, "z": 0},
    },
    "self_buff_pose": {
        "description": "Stand tall → energy surge → settle",
        "keyframes": [
            {"frame": 1,  "pose": "idle"},
            {"frame": 6,  "pose": "crouch"},
            {"frame": 12, "pose": "surge"},
            {"frame": 20, "pose": "tall"},
            {"frame": 28, "pose": "idle"},
        ],
        "root_motion": {"x": 0, "y": 0, "z": 0.1},
    },
}

BLENDER_ANIMATE_SCRIPT = '''
import bpy
import json
import sys

argv  = sys.argv
data  = json.loads(argv[argv.index("--") + 1])
blend = data["blend_path"]
move  = data["move"]
tmpl  = data["template"]

bpy.ops.wm.open_mainfile(filepath=blend)

# Create a new NLA action per move
action_name = f"{move['name']}_action"
action = bpy.data.actions.new(name=action_name)

# Tag the action in custom properties for the VFX module
action["move_type"]  = move["type"]
action["sfx_tags"]   = json.dumps(move["sfx_tags"])
action["motion_tag"] = move["motion_tag"]

# Key basic bone transforms per template frame
armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
if armatures:
    rig = armatures[0]
    rig.animation_data_create()
    rig.animation_data.action = action

    for kf in tmpl["keyframes"]:
        bpy.context.scene.frame_set(kf["frame"])
        for bone in rig.pose.bones:
            bone.keyframe_insert(data_path="location",   frame=kf["frame"])
            bone.keyframe_insert(data_path="rotation_euler", frame=kf["frame"])

output = data["output_path"]
bpy.ops.wm.save_as_mainfile(filepath=output)
print(f"[MotionHub] Saved → {output}")
'''


class MotionHub:
    """
    DNA:
    - One .blend output per move. Never bakes multiple moves into one file.
    - Motion tags are the contract between Lore Engine and this module.
    - Adding a new motion_tag = adding one entry to MOTION_TEMPLATES. No other change needed.
    - Frame counts target 24fps: 24 frames = 1s, 121 frames = 5s (LTX render window).
    """

    def __init__(self):
        Path("pipeline/animated").mkdir(parents=True, exist_ok=True)

    def animate_all(self, lore_path: str, blend_path: str, blender_exe="blender"):
        with open(lore_path) as f:
            lore = json.load(f)

        char_id = lore["id"]
        results = []

        for move in lore["moves"]:
            tag   = move.get("motion_tag", "")
            tmpl  = MOTION_TEMPLATES.get(tag)
            if not tmpl:
                print(f"[MotionHub] ⚠ No template for motion_tag '{tag}' — skipping {move['name']}")
                continue

            output = f"pipeline/animated/{char_id}_{move['name'].lower().replace(' ', '_')}.blend"
            payload = {
                "blend_path": blend_path,
                "move": move,
                "template": tmpl,
                "output_path": output,
            }

            cmd = [
                blender_exe, "--background",
                "--python-expr", BLENDER_ANIMATE_SCRIPT,
                "--", json.dumps(payload)
            ]

            print(f"[MotionHub] Animating {char_id} → {move['name']}...")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                results.append(output)
            else:
                print(f"[MotionHub] ✗ Error: {result.stderr[-300:]}")

        return results


if __name__ == "__main__":
    hub = MotionHub()
    hub.animate_all(
        lore_path="pipeline/lore/embrix.json",
        blend_path="pipeline/assets/embrix.blend"
    )
