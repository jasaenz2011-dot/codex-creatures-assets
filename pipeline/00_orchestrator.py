"""
GOD-BUILDER ARCHITECT — ORCHESTRATOR
Runs all 5 modules in sequence for a character, or starts the Director's Remote.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def build_character(character_id: str, blender_exe: str = "blender"):
    print(f"\n{'='*60}")
    print(f"  GOD-BUILDER: Starting full pipeline for {character_id.upper()}")
    print(f"{'='*60}")

    from pipeline.p01_lore_engine    import LoreLogicEngine
    from pipeline.p02_asset_architect import AssetArchitect
    from pipeline.p03_motion_hub      import MotionHub
    from pipeline.p04_vfx_manager     import VFXManager

    # Module 1 → 2 → 3 → 4
    lore_path  = f"pipeline/lore/{character_id}.json"
    blend_path = f"pipeline/assets/{character_id}.blend"

    print("\n[1/4] Lore Engine")
    engine = LoreLogicEngine()
    engine.load(character_id)   # must already exist; run 01_lore_engine.py first

    print("\n[2/4] Asset Architect")
    arch = AssetArchitect()
    arch.build(lore_path, blender_exe)

    print("\n[3/4] Motion Hub")
    hub = MotionHub()
    animated = hub.animate_all(lore_path, blend_path, blender_exe)

    print("\n[4/4] VFX Manager")
    vfx = VFXManager()
    for blend in animated:
        vfx.render(lore_path, blend, blender_exe)

    print(f"\n{'='*60}")
    print(f"  ✓ Pipeline complete. Renders in pipeline/renders/")
    print(f"{'='*60}\n")


def start_remote():
    from pipeline.p05_directors_remote import DirectorsRemote
    DirectorsRemote().start()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="God-Builder Architect")
    parser.add_argument("--character", default="embrix")
    parser.add_argument("--blender",   default="blender")
    parser.add_argument("--remote",    action="store_true", help="Start Director's Remote server")
    args = parser.parse_args()

    if args.remote:
        start_remote()
    else:
        build_character(args.character, args.blender)
