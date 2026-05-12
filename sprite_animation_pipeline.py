#!/usr/bin/env python3
"""
Local sprite extraction and animation pipeline.
Segments character sheets, extracts sprites, and generates videos.
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw
import os
import json
from pathlib import Path
import subprocess
from typing import List, Tuple

class SpriteExtractor:
    def __init__(self, output_dir="sprites_output"):
        self.output_dir = output_dir
        Path(output_dir).mkdir(exist_ok=True)
        Path(f"{output_dir}/extracted").mkdir(exist_ok=True)
        Path(f"{output_dir}/videos").mkdir(exist_ok=True)
        print(f"✓ Output directory: {output_dir}")

    def load_image(self, image_path: str) -> np.ndarray:
        """Load image with OpenCV."""
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Image not found: {image_path}")
        print(f"✓ Loaded: {image_path} ({img.shape[1]}x{img.shape[0]})")
        return img

    def find_sprite_regions(self, img: np.ndarray, min_area=500) -> List[Tuple[int, int, int, int]]:
        """
        Detect sprite regions using contour detection.
        Returns list of (x, y, w, h) bounding boxes.
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Threshold to binary (white sprites on dark background)
        _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)

        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h

            # Filter out noise: min size and reasonable aspect ratio
            if area > min_area and 0.3 < (w / h) < 3.0:
                regions.append((x, y, w, h))

        # Sort by position (left-to-right, top-to-bottom)
        regions.sort(key=lambda r: (r[1] // 100, r[0]))

        print(f"  Found {len(regions)} sprite regions")
        return regions

    def extract_sprites(self, image_path: str, character_name: str, padding=5) -> List[np.ndarray]:
        """Extract individual sprites from character sheet."""
        img = self.load_image(image_path)
        regions = self.find_sprite_regions(img)

        sprites = []
        char_dir = Path(self.output_dir) / "extracted" / character_name
        char_dir.mkdir(exist_ok=True)

        for idx, (x, y, w, h) in enumerate(regions):
            # Add padding
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(img.shape[1], x + w + padding)
            y2 = min(img.shape[0], y + h + padding)

            sprite = img[y1:y2, x1:x2]
            sprites.append(sprite)

            # Save sprite
            sprite_path = char_dir / f"sprite_{idx:03d}.png"
            cv2.imwrite(str(sprite_path), sprite)

        print(f"✓ Extracted {len(sprites)} sprites to {char_dir}")
        return sprites

    def create_sprite_animation(
        self,
        sprites: List[np.ndarray],
        output_path: str,
        fps: int = 8,
        loop_count: int = 2,
        duration_per_sprite: int = 200  # milliseconds for GIF
    ) -> str:
        """
        Create animated GIF from sprite list.
        Also generate MP4 if ffmpeg is available.
        """
        if not sprites:
            print("  ⚠ No sprites to animate")
            return None

        # Convert BGR to RGB for PIL
        pil_sprites = []
        for sprite in sprites:
            rgb = cv2.cvtColor(sprite, cv2.COLOR_BGR2RGB)
            pil_sprites.append(Image.fromarray(rgb))

        # Create looping animation
        animation_frames = pil_sprites * loop_count

        # Save as GIF
        gif_path = str(output_path).replace('.mp4', '.gif')
        pil_sprites[0].save(
            gif_path,
            save_all=True,
            append_images=animation_frames[1:],
            duration=duration_per_sprite,
            loop=0  # infinite loop
        )
        print(f"✓ Saved GIF: {gif_path}")

        # Try to create MP4 with ffmpeg
        try:
            # Create temp PNG sequence
            temp_dir = Path(self.output_dir) / "temp"
            temp_dir.mkdir(exist_ok=True)

            for idx, frame in enumerate(animation_frames):
                frame.save(temp_dir / f"frame_{idx:04d}.png")

            # Use ffmpeg to create MP4
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", str(temp_dir / "frame_%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(output_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ Saved MP4: {output_path}")
            else:
                print(f"  ⚠ ffmpeg error: {result.stderr[:200]}")

            # Cleanup temp
            for f in temp_dir.glob("*.png"):
                f.unlink()
            temp_dir.rmdir()

        except FileNotFoundError:
            print("  ⚠ ffmpeg not found (install with: sudo apt install ffmpeg)")

        return gif_path

    def process_character(self, image_path: str, character_name: str):
        """Full pipeline: load image → extract sprites → create animation."""
        print(f"\n━━━ Processing {character_name} ━━━")

        # Extract sprites
        sprites = self.extract_sprites(image_path, character_name)

        if not sprites:
            print("  ✗ No sprites extracted")
            return

        # Create animation
        output_video = Path(self.output_dir) / "videos" / f"{character_name}_animation.mp4"
        self.create_sprite_animation(sprites, str(output_video))

        # Save metadata
        metadata = {
            "character": character_name,
            "sprite_count": len(sprites),
            "source": image_path,
        }
        meta_path = Path(self.output_dir) / "videos" / f"{character_name}_meta.json"
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    def batch_process(self, image_dict: dict):
        """
        Process multiple character sheets.
        image_dict: {"character_name": "path/to/image.png", ...}
        """
        print(f"\n{'='*60}")
        print("SPRITE EXTRACTION & ANIMATION PIPELINE")
        print(f"{'='*60}\n")

        for character, image_path in image_dict.items():
            try:
                self.process_character(image_path, character)
            except Exception as e:
                print(f"  ✗ Error: {e}")

        print(f"\n{'='*60}")
        print(f"✓ Pipeline complete. Output: {self.output_dir}/")
        print(f"{'='*60}\n")

# ─── USAGE EXAMPLE ───

if __name__ == "__main__":
    extractor = SpriteExtractor(output_dir="sprites_output")

    # Define your character sheets here
    characters = {
        "samus": "samus.png",
        "link": "link.png",
        "linkuzu": "linkuzu.png",
        "sasketto": "sasketto.png",
    }

    # Process all characters
    extractor.batch_process(characters)

    # Or process a single character:
    # extractor.process_character("path/to/image.png", "character_name")
