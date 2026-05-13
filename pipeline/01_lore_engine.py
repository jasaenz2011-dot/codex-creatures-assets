"""
MODULE 1: LORE-LOGIC ENGINE
Role: World-state authority and canonical data schema.
      Defines and exports structured production manifests consumed by all downstream modules.
Input:  Producer-defined asset definitions
Output: pipeline/lore/{ASSET_ID}.json + pipeline/lore/lore_index.json
"""

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Action:
    name: str
    category: str           # attack | status | special | idle | transition
    power: int              # 0 for non-combat actions
    duration_frames: int    # how long the action plays at 24fps
    effect: Optional[str] = None
    sfx_tags: List[str] = field(default_factory=list)   # → VFX module contract
    motion_tag: str = ""                                  # → Motion Hub contract


@dataclass
class Asset:
    id: str                 # {ASSET_ID} — slug, no spaces
    name: str               # display name
    asset_type: str         # {ASSET_TYPE}: character | prop | environment | creature
    origin: str             # world/region label
    dimensions: dict        # {"height_cm": int, "weight_kg": int} or equivalent
    stats: dict             # arbitrary key/value production stats
    actions: List[Action]
    palette: List[str]      # hex colors → Asset Architect material slots
    style_tags: List[str]   # e.g. "32bit", "ink-brush", "cel-shaded" → VFX module
    signature: str          # logline or brand statement
    vibe: List[str]         # tone descriptors → Director's briefing notes


@dataclass
class ProductionWorld:
    name: str
    regions: List[str]
    rules: List[str]
    assets: List[Asset]


class LoreLogicEngine:
    """
    SYSTEM INSTRUCTIONS:
    - Single source of truth. All modules READ from here. None WRITE back.
    - {ASSET_ID} is the primary key across the entire pipeline.
    - Adding a new asset = calling export() + update_index(). Nothing else.
    - lore_index.json is the orchestrator's discovery manifest.

    DNA RULES:
    1. Schema changes require a version bump in the JSON output.
    2. sfx_tags and motion_tag are the only fields other modules depend on directly.
    3. Never embed render settings here — those belong in modules 2-4.
    """

    def __init__(self, output_dir="pipeline/lore"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, asset: Asset) -> Path:
        """Serialize {ASSET_ID} to JSON for downstream modules."""
        data = {**asdict(asset), "_schema_version": 1}
        path = self.output_dir / f"{asset.id}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[LoreEngine] Exported → {path}")
        return path

    def load(self, asset_id: str) -> dict:
        path = self.output_dir / f"{asset_id}.json"
        with open(path) as f:
            return json.load(f)

    def update_index(self, asset: Asset) -> Path:
        """Maintain lore_index.json — orchestrator discovery manifest."""
        index_path = self.output_dir / "lore_index.json"
        index = {}
        if index_path.exists():
            with open(index_path) as f:
                index = json.load(f)

        index[asset.id] = {
            "name":       asset.name,
            "asset_type": asset.asset_type,
            "file":       f"{asset.id}.json",
        }

        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)
        print(f"[LoreEngine] Index updated → {index_path}")
        return index_path


# ── USAGE ────────────────────────────────────────────────
# Replace {ASSET_ID}, {ASSET_TYPE}, etc. with your Genesis Pitch data.
#
# asset = Asset(
#     id="{ASSET_ID}",
#     name="{DISPLAY_NAME}",
#     asset_type="{ASSET_TYPE}",
#     origin="{WORLD_REGION}",
#     dimensions={"height_cm": 0, "weight_kg": 0},
#     stats={"hp": 0, "atk": 0, "def": 0},
#     actions=[
#         Action("{ACTION_NAME}", "{CATEGORY}", 0, 24,
#                sfx_tags=["{SFX_TAG_1}", "{SFX_TAG_2}"],
#                motion_tag="{MOTION_TAG}"),
#     ],
#     palette=["{HEX_PRIMARY}", "{HEX_SECONDARY}"],
#     style_tags=["{STYLE_TAG}"],
#     signature="{LOGLINE}",
#     vibe=["{TONE_DESCRIPTOR}"]
# )
# engine = LoreLogicEngine()
# engine.export(asset)
# engine.update_index(asset)
