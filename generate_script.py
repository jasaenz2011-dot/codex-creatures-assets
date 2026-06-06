#!/usr/bin/env python3
"""
Video Script Generator — uses a local LM Studio model via its OpenAI-compatible API.

Usage:
    python generate_script.py --topic "A mysterious forest creature emerges at dawn"
    python generate_script.py --topic "..." --model "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF"
    python generate_script.py --topic "..." --output my_script.txt
    python generate_script.py --topic "..." --host http://192.168.1.5:1234

LM Studio must be running with a model loaded and the local server enabled
(Server tab → Start Server, default port 1234).
"""

import argparse
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai package not found. Install it with:\n  pip install openai")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a professional video scriptwriter. When given a video topic or concept,
you produce three sections in order:

1. SCENE-BY-SCENE BREAKDOWN
   Numbered list of scenes. Each entry: Scene number, INT/EXT, location, time of day,
   duration estimate, and a one-sentence description of the action.

2. FULL SHOOTING SCRIPT
   Industry-standard format with scene headings (INT./EXT.), action lines, character
   names centred before dialogue, and brief parentheticals where needed.

3. NARRATION / VOICEOVER
   The spoken words only, written as a clean narration script that matches the pacing
   of the shooting script. Mark pauses with [PAUSE] and emphasis with *word*.

Separate each section with a line of dashes (---).
Be vivid, cinematic, and concise. Tailor the tone to the topic."""

USER_TEMPLATE = "Write a complete video script for the following concept:\n\n{topic}"


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate(topic: str, host: str, model: str, temperature: float, max_tokens: int) -> str:
    client = OpenAI(base_url=f"{host}/v1", api_key="lm-studio")

    # Discover available model if caller passed "auto"
    if model == "auto":
        models = client.models.list()
        available = [m.id for m in models.data]
        if not available:
            raise RuntimeError(
                "No models loaded in LM Studio. Load a model in the app first."
            )
        model = available[0]
        print(f"[info] Using model: {model}")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(topic=topic)},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_output(topic: str, model: str, raw: str) -> str:
    header = textwrap.dedent(f"""\
        ╔══════════════════════════════════════════════════════════════╗
        ║               CODEX CREATURES — VIDEO SCRIPT                 ║
        ╚══════════════════════════════════════════════════════════════╝
        Generated : {datetime.now().strftime('%Y-%m-%d %H:%M')}
        Model     : {model}
        Topic     : {topic}
        ══════════════════════════════════════════════════════════════

    """)

    sections = raw.split("---")
    labels = [
        "SECTION 1 — SCENE-BY-SCENE BREAKDOWN",
        "SECTION 2 — FULL SHOOTING SCRIPT",
        "SECTION 3 — NARRATION / VOICEOVER",
    ]

    body_parts = []
    for i, section in enumerate(sections):
        label = labels[i] if i < len(labels) else f"SECTION {i + 1}"
        body_parts.append(f"{label}\n{'─' * 62}\n{section.strip()}\n")

    return header + "\n\n".join(body_parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate a video script using a local LM Studio model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--topic", required=True, help="Video topic or concept")
    p.add_argument(
        "--host",
        default="http://localhost:1234",
        help="LM Studio server URL (default: http://localhost:1234)",
    )
    p.add_argument(
        "--model",
        default="auto",
        help='Model ID to use, or "auto" to pick the first loaded model (default: auto)',
    )
    p.add_argument(
        "--temperature",
        type=float,
        default=0.75,
        help="Sampling temperature, 0.0–2.0 (default: 0.75)",
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="Maximum tokens to generate (default: 2048)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Save output to this file (optional; always prints to stdout too)",
    )
    p.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Also save a machine-readable JSON file alongside --output",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Connecting to LM Studio at {args.host} …")
    try:
        raw = generate(
            topic=args.topic,
            host=args.host,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except Exception as exc:
        print(f"\nERROR: {exc}")
        print(
            "\nTroubleshooting:\n"
            "  1. Open LM Studio → Server tab → click 'Start Server'\n"
            "  2. Make sure a model is loaded (Models tab)\n"
            "  3. Check that the port matches --host (default 1234)\n"
        )
        sys.exit(1)

    resolved_model = args.model if args.model != "auto" else "[auto-detected]"
    formatted = format_output(args.topic, resolved_model, raw)

    print("\n" + formatted)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(formatted, encoding="utf-8")
        print(f"\n[saved] {out_path}")

        if args.as_json:
            sections = raw.split("---")
            data = {
                "topic": args.topic,
                "model": resolved_model,
                "generated_at": datetime.now().isoformat(),
                "scene_breakdown": sections[0].strip() if len(sections) > 0 else "",
                "shooting_script": sections[1].strip() if len(sections) > 1 else "",
                "narration": sections[2].strip() if len(sections) > 2 else "",
                "raw": raw,
            }
            json_path = out_path.with_suffix(".json")
            json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[saved] {json_path}")


if __name__ == "__main__":
    main()
