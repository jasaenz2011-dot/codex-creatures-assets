"""
MODULE 3: MOTION & PERFORMANCE HUB
Role: Applies keyed animations to rigged .blend assets using motion_tag data
      from the Lore Engine. One output file per action.
Input:  pipeline/assets/{ASSET_ID}.blend  +  lore actions[].motion_tag
Output: pipeline/animated/{ASSET_ID}_{ACTION_NAME}.blend

All frame counts target 24fps. 121 frames = 5 seconds (LTX render window).
"""

import json
import subprocess
from pathlib import Path


# ── Motion Tag Registry ───────────────────────────────────
# motion_tag (set in Lore Engine) → keyframe template
# Add new tags here as the Genesis Pitch demands them.
# No other file needs to change.

MOTION_TEMPLATES = {
    "projectile_forward": {
        "description": "Wind-up → release → follow-through",
        "keyframes": [
            {"frame": 1,  "pose": "idle"},
            {"frame": 6,  "pose": "wind_up"},
            {"frame": 12, "pose": "release"},
            {"frame": 18, "pose": "follow_through"},
            {"frame": 24, "pose": "idle"},
        ],
        "root_delta": {"x": 0.2, "y": 0.0, "z": 0.0},
    },
    "melee_swipe": {
        "description": "Dash → strike → recoil",
        "keyframes": [
            {"frame": 1,  "pose": "idle"},
            {"frame": 4,  "pose": "dash_start"},
            {"frame": 8,  "pose": "strike_peak"},
            {"frame": 14, "pose": "recoil"},
            {"frame": 20, "pose": "idle"},
        ],
        "root_delta": {"x": 0.6, "y": 0.0, "z": 0.0},
    },
    "area_emit": {
        "description": "Charge → burst → sustain",
        "keyframes": [
            {"frame": 1,  "pose": "idle"},
            {"frame": 8,  "pose": "charge"},
            {"frame": 16, "pose": "burst"},
            {"frame": 30, "pose": "sustain"},
            {"frame": 36, "pose": "idle"},
        ],
        "root_delta": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "self_buff": {
        "description": "Crouch → energy surge → recover",
        "keyframes": [
            {"frame": 1,  "pose": "idle"},
            {"frame": 6,  "pose": "crouch"},
            {"frame": 12, "pose": "surge"},
            {"frame": 20, "pose": "tall"},
            {"frame": 28, "pose": "idle"},
        ],
        "root_delta": {"x": 0.0, "y": 0.0, "z": 0.1},
    },
    "idle_loop": {
        "description": "Breathing cycle — seamless 24-frame loop",
        "keyframes": [
            {"frame": 1,  "pose": "idle_a"},
            {"frame": 12, "pose": "idle_b"},
            {"frame": 24, "pose": "idle_a"},
        ],
        "root_delta": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "knockback": {
        "description": "Impact → stagger → recover",
        "keyframes": [
            {"frame": 1,  "pose": "idle"},
            {"frame": 3,  "pose": "impact"},
            {"frame": 10, "pose": "stagger"},
            {"frame": 18, "pose": "recover"},
            {"frame": 24, "pose": "idle"},
        ],
        "root_delta": {"x": -0.4, "y": 0.0, "z": 0.0},
    },
}

BLENDER_ANIMATE_SCRIPT = '''
import bpy, json, sys

argv = sys.argv
data = json.loads(argv[argv.index("--") + 1])

bpy.ops.wm.open_mainfile(filepath=data["blend_path"])

action = bpy.data.actions.new(name=data["action_name"])
# Tag action metadata for VFX module consumption
action["sfx_tags"]   = json.dumps(data["sfx_tags"])
action["motion_tag"] = data["motion_tag"]
action["asset_id"]   = data["asset_id"]

armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
if armatures:
    rig = armatures[0]
    rig.animation_data_create()
    rig.animation_data.action = action
    for kf in data["keyframes"]:
        bpy.context.scene.frame_set(kf["frame"])
        for bone in rig.pose.bones:
            bone.keyframe_insert(data_path="location",       frame=kf["frame"])
            bone.keyframe_insert(data_path="rotation_euler", frame=kf["frame"])

bpy.ops.wm.save_as_mainfile(filepath=data["output_path"])
print(f"[MotionHub] Saved → {data['output_path']}")
'''


class MotionHub:
    """
    SYSTEM INSTRUCTIONS:
    - One .blend output per action. Never batch multiple actions in one file.
    - motion_tag is the binding contract between Lore Engine and this module.
    - Adding a new motion = one new entry in MOTION_TEMPLATES. Nothing else changes.
    - sfx_tags are passed through (not consumed here) for Module 4 to read.

    DNA RULES:
    1. Frame counts: 24fps baseline. 24f = 1s, 48f = 2s, 121f = 5s (LTX max).
    2. root_delta drives root motion — keep values small to avoid clipping.
    3. Unknown motion_tags are skipped with a warning, not an error.
    4. Output naming: {ASSET_ID}_{ACTION_NAME}.blend (slugified, lowercase).
    """

    def __init__(self):
        Path("pipeline/animated").mkdir(parents=True, exist_ok=True)

    def animate_all(self, lore_path: str, blend_path: str, blender_exe="blender") -> list:
        """Animate all actions defined for {ASSET_ID} in lore JSON."""
        with open(lore_path) as f:
            lore = json.load(f)

        asset_id = lore["id"]
        results  = []

        for action in lore.get("actions", []):
            tag  = action.get("motion_tag", "")
            tmpl = MOTION_TEMPLATES.get(tag)

            if not tmpl:
                print(f"[MotionHub] ⚠ No template for motion_tag '{tag}' — skipping '{action['name']}'")
                continue

            slug   = action["name"].lower().replace(" ", "_")
            output = f"pipeline/animated/{asset_id}_{slug}.blend"

            payload = {
                "blend_path":  blend_path,
                "output_path": output,
                "asset_id":    asset_id,
                "action_name": action["name"],
                "motion_tag":  tag,
                "sfx_tags":    action.get("sfx_tags", []),
                "keyframes":   tmpl["keyframes"],
            }

            cmd = [
                blender_exe, "--background",
                "--python-expr", BLENDER_ANIMATE_SCRIPT,
                "--", json.dumps(payload)
            ]

            print(f"[MotionHub] Animating {asset_id} → {action['name']} ({tag})")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                results.append(output)
            else:
                print(f"[MotionHub] ✗ {result.stderr[-300:]}")

        return results


# ── USAGE ─────────────────────────────────────────────────
# hub = MotionHub()
# hub.animate_all(
#     lore_path="pipeline/lore/{ASSET_ID}.json",
#     blend_path="pipeline/assets/{ASSET_ID}.blend"
# )
