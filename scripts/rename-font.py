"""Rename a font's family name-table entries to a target family name.

Cloakfox bundles openly-licensed, metric-compatible substitute fonts (OFL /
Apache / MIT) and presents them under the target family names that personas
claim (e.g. an open Arial-metric font presented as "Arial", an open Segoe UI
substitute presented as "Segoe UI"). On macOS there is no fontconfig aliasing,
so the substitution must be baked into the font's own name table.

This edits nameIDs 1/16 (family / typographic family), 4 (full name), 6
(PostScript name) and 3 (unique id) on all platform/encoding records.

Usage:
    python scripts/rename-font.py <src.ttf> <dst.ttf> "<Target Family>"
"""
import sys

from fontTools.ttLib import TTFont


def rename(src: str, dst: str, target: str) -> None:
    ps = target.replace(" ", "")
    f = TTFont(src)
    for rec in f["name"].names:
        if rec.nameID in (1, 16):      # Family / Typographic Family
            rec.string = target
        elif rec.nameID == 4:          # Full name
            rec.string = target
        elif rec.nameID == 6:          # PostScript name
            rec.string = ps
        elif rec.nameID == 3:          # Unique ID
            rec.string = f"{ps};cloakfox"
    f.save(dst)
    print(f"renamed {src} -> family '{target}' (ps '{ps}') -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: rename-font.py <src.ttf> <dst.ttf> <Target Family>")
    rename(sys.argv[1], sys.argv[2], sys.argv[3])
