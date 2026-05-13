"""
MODULE 1: LORE-LOGIC ENGINE
Role: World-state authority. Generates and validates all canonical data.
Output: Structured JSON consumed by every downstream module.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Move:
    name: str
    type: str           # fire, grass, water, normal, etc.
    category: str       # attack | status | special
    power: int
    pp: int
    effect: Optional[str] = None
    sfx_tags: List[str] = field(default_factory=list)   # → feeds VFX module
    motion_tag: str = ""                                  # → feeds Motion Hub


@dataclass
class Character:
    id: str
    name: str
    type: str
    origin: str
    height_cm: int
    weight_kg: int
    hp: int
    atk: int
    def_: int
    moves: List[Move]
    palette: List[str]          # hex colors → feeds Asset Architect
    style_tags: List[str]       # e.g. "32bit", "ink-brush" → feeds VFX module
    signature_quote: str
    vibe: List[str]


@dataclass
class World:
    name: str
    regions: List[str]
    rules: List[str]            # game logic rules (type chart, etc.)
    characters: List[Character]


class LoreLogicEngine:
    """
    DNA:
    - Single source of truth. All modules read from here, none write back.
    - Every character export is versioned (v1, v2...) to avoid stale assets.
    - Output format: lore/<character_id>.json
    """

    def __init__(self, output_dir="pipeline/lore"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, character: Character) -> Path:
        """Serialize character to JSON for downstream modules."""
        data = asdict(character)
        path = self.output_dir / f"{character.id}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[LoreEngine] Exported → {path}")
        return path

    def load(self, character_id: str) -> dict:
        path = self.output_dir / f"{character_id}.json"
        with open(path) as f:
            return json.load(f)

    def update_index(self, character: Character) -> Path:
        """Maintain lore_index.json — manifest of all exported characters."""
        index_path = self.output_dir / "lore_index.json"
        index = {}
        if index_path.exists():
            with open(index_path) as f:
                index = json.load(f)

        index[character.id] = {
            "name": character.name,
            "type": character.type,
            "file": f"{character.id}.json",
        }

        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)
        print(f"[LoreEngine] Index updated → {index_path}")
        return index_path


# ── EXAMPLE CHARACTER ────────────────────────────────────

if __name__ == "__main__":
    engine = LoreLogicEngine()

    embrix = Character(
        id="embrix",
        name="EMBRIX",
        type="fire",
        origin="Volcanic Ridge",
        height_cm=95,
        weight_kg=18,
        hp=45, atk=14, def_=10,
        moves=[
            Move("Ember", "fire", "attack", 18, 15,
                 sfx_tags=["flame_burst", "ember_particle"],
                 motion_tag="projectile_forward"),
            Move("Scratch", "normal", "attack", 12, 20,
                 sfx_tags=["claw_slash", "impact_dust"],
                 motion_tag="melee_swipe"),
            Move("Smokescreen", "normal", "status", 0, 15,
                 effect="lower_acc",
                 sfx_tags=["smoke_cloud", "vision_blur"],
                 motion_tag="area_emit"),
            Move("Heat Up", "fire", "status", 0, 10,
                 effect="raise_atk",
                 sfx_tags=["body_glow_red", "heat_shimmer"],
                 motion_tag="self_buff_pose"),
        ],
        palette=["#FF8C00", "#FFC800", "#FF4500", "#1A1A28"],
        style_tags=["32bit", "pixel-art", "high-contrast"],
        signature_quote="The flame doesn't ask permission.",
        vibe=["fierce", "impulsive", "loyal"]
    )

    engine.export(embrix)
    engine.update_index(embrix)
    print(json.dumps(engine.load("embrix"), indent=2))
