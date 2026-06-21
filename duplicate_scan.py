#!/usr/bin/env python3
"""
Redundancy audit: finds duplicate files by SHA-256 hash.

Rules:
- Skips files <= 100 MB
- Skips known media extensions: .mp4 .mkv .mov .jpg .jpeg .png .raw
- Skips directories named Videos or Images (case-insensitive)
- Skips .git directories
- Writes results to cleanup_plan.csv (never deletes anything)
"""

import csv
import hashlib
import os
import sys
from collections import defaultdict
from pathlib import Path

MEDIA_EXTENSIONS = {".mp4", ".mkv", ".mov", ".jpg", ".jpeg", ".png", ".raw"}
MEDIA_DIRS = {"videos", "images"}
MIN_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
OUTPUT_CSV = "cleanup_plan.csv"


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def should_skip_dir(name: str) -> bool:
    return name.lower() in MEDIA_DIRS or name == ".git"


def scan(root: Path) -> dict[str, list[dict]]:
    hash_map: dict[str, list[dict]] = defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() in MEDIA_EXTENSIONS:
                continue
            try:
                size = fpath.stat().st_size
            except OSError:
                continue
            if size <= MIN_SIZE_BYTES:
                continue
            try:
                digest = sha256(fpath)
            except OSError as exc:
                print(f"[warn] cannot hash {fpath}: {exc}", file=sys.stderr)
                continue
            hash_map[digest].append({"path": str(fpath), "size_bytes": size})
    return hash_map


def write_csv(hash_map: dict[str, list[dict]], out: Path) -> int:
    rows = []
    for digest, entries in hash_map.items():
        if len(entries) < 2:
            continue
        # First entry is the "keeper"; the rest are redundant copies.
        for idx, entry in enumerate(entries):
            rows.append(
                {
                    "hash": digest,
                    "path": entry["path"],
                    "size_bytes": entry["size_bytes"],
                    "size_mb": round(entry["size_bytes"] / (1024 * 1024), 2),
                    "status": "KEEP" if idx == 0 else "REDUNDANT",
                }
            )
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["hash", "path", "size_bytes", "size_mb", "status"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return len([r for r in rows if r["status"] == "REDUNDANT"])


def summarise(hash_map: dict[str, list[dict]]) -> None:
    redundant_files = 0
    reclaimable_bytes = 0
    for entries in hash_map.values():
        if len(entries) < 2:
            continue
        for entry in entries[1:]:  # skip the keeper
            redundant_files += 1
            reclaimable_bytes += entry["size_bytes"]

    print(f"\n{'='*60}")
    print("REDUNDANCY AUDIT SUMMARY")
    print(f"{'='*60}")
    print(f"  Duplicate groups found : {sum(1 for e in hash_map.values() if len(e) >= 2)}")
    print(f"  Redundant files        : {redundant_files}")
    print(f"  Space reclaimable      : {reclaimable_bytes / (1024**3):.2f} GB "
          f"({reclaimable_bytes / (1024**2):.0f} MB)")
    print(f"  Report written to      : {OUTPUT_CSV}")
    print(f"{'='*60}")
    print("No files were modified or deleted.")


def main() -> None:
    roots = sys.argv[1:] or ["."]
    combined: dict[str, list[dict]] = defaultdict(list)
    for root in roots:
        root_path = Path(root).resolve()
        print(f"Scanning {root_path} …")
        for digest, entries in scan(root_path).items():
            combined[digest].extend(entries)

    redundant_count = write_csv(combined, Path(OUTPUT_CSV))
    summarise(combined)

    if redundant_count == 0:
        print("\nNo redundant files found matching the criteria.")


if __name__ == "__main__":
    main()
