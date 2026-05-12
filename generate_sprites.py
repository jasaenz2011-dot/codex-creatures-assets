#!/usr/bin/env python3
"""Generate simple pixel art creature sprites using PIL."""

from PIL import Image, ImageDraw
import base64
from io import BytesIO
import json

def create_sprite(name, colors, pattern):
    """
    Create a simple pixel art sprite.
    colors: dict with 'body', 'accent', 'eye'
    pattern: list of lists describing pixel grid (0=transparent, 1=body, 2=accent, 3=eye)
    """
    pixel_size = 8  # each "pixel" is 8x8 in the image
    width = len(pattern[0]) * pixel_size
    height = len(pattern) * pixel_size

    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    color_map = {
        0: (0, 0, 0, 0),           # transparent
        1: colors['body'],          # body color
        2: colors['accent'],        # accent color
        3: colors['eye'],           # eye color
    }

    for y, row in enumerate(pattern):
        for x, pixel_type in enumerate(row):
            if pixel_type != 0:
                rect = [
                    x * pixel_size,
                    y * pixel_size,
                    (x + 1) * pixel_size,
                    (y + 1) * pixel_size
                ]
                draw.rectangle(rect, fill=color_map[pixel_type])

    return img

def img_to_base64(img):
    """Convert PIL image to base64 data URL."""
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    data = base64.b64encode(buffer.read()).decode('utf-8')
    return f"data:image/png;base64,{data}"

# EMBRIX - Fire type (orange flame creature)
embrix_pattern = [
    [0, 0, 1, 1, 1, 0, 0, 0],
    [0, 1, 1, 2, 1, 1, 0, 0],
    [1, 1, 2, 2, 2, 1, 1, 0],
    [1, 1, 2, 2, 2, 1, 1, 0],
    [1, 1, 1, 2, 1, 1, 1, 0],
    [0, 1, 3, 3, 1, 1, 0, 0],
    [0, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 0, 0, 0],
]
embrix = create_sprite("EMBRIX", {
    'body': (255, 140, 0, 255),    # orange
    'accent': (255, 200, 0, 255),  # yellow
    'eye': (0, 0, 0, 255),         # black
}, embrix_pattern)

# LEAFANG - Grass type (leafy creature)
leafang_pattern = [
    [0, 0, 2, 2, 2, 0, 0, 0],
    [0, 2, 2, 1, 2, 2, 0, 0],
    [2, 2, 1, 1, 1, 2, 2, 0],
    [2, 1, 1, 1, 1, 1, 2, 0],
    [2, 1, 3, 3, 1, 1, 2, 0],
    [2, 1, 1, 1, 1, 1, 2, 0],
    [0, 2, 1, 1, 1, 2, 0, 0],
    [0, 0, 2, 1, 2, 0, 0, 0],
]
leafang = create_sprite("LEAFANG", {
    'body': (80, 180, 80, 255),    # green
    'accent': (120, 220, 120, 255), # light green
    'eye': (0, 0, 0, 255),         # black
}, leafang_pattern)

# Convert to base64
embrix_b64 = img_to_base64(embrix)
leafang_b64 = img_to_base64(leafang)

# Output as JSON for easy use in HTML
sprites = {
    "embrix": embrix_b64,
    "leafang": leafang_b64,
}

print(json.dumps(sprites, indent=2))

# Also save as actual PNG files
embrix.save("embrix.png")
leafang.save("leafang.png")
print("\n✓ Saved embrix.png and leafang.png")
print(f"✓ Base64 data URLs ready for HTML")
