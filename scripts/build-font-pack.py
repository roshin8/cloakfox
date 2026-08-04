"""Assemble Cloakfox's bundled font pack from openly-licensed, metric-compatible
substitutes, renamed to the target family names personas claim.

Downloads the open source fonts (Google Fonts OFL/Apache + Microsoft Selawik
MIT), renames each to its target family via the name-table rewrite in
rename-font.py, and writes bundle/fonts/<os>/<Target>.ttf. macOS has no
fontconfig aliasing, so the name must be baked into the file.

Licenses: Arimo/Tinos/Cousine (Apache-2.0), Carlito/Caladea/Gelasio/Comic
Neue/Anton (SIL OFL), Selawik (MIT). All redistributable.

Usage: python scripts/build-font-pack.py
"""
import io
import os
import sys
import zipfile
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from importlib import import_module

rename_mod = import_module("rename-font")

RAW = "https://raw.githubusercontent.com/google/fonts/main"

# source name -> URL of a redistributable open font file
SOURCES = {
    "Arimo": f"{RAW}/ofl/arimo/Arimo%5Bwght%5D.ttf",
    "Tinos": f"{RAW}/ofl/tinos/Tinos-Regular.ttf",
    "Cousine": f"{RAW}/ofl/cousine/Cousine-Regular.ttf",
    "Carlito": f"{RAW}/ofl/carlito/Carlito-Regular.ttf",
    "Caladea": f"{RAW}/ofl/caladea/Caladea-Regular.ttf",
    "Gelasio": f"{RAW}/ofl/gelasio/Gelasio%5Bwght%5D.ttf",
    "ComicNeue": f"{RAW}/ofl/comicneue/ComicNeue-Regular.ttf",
    "Anton": f"{RAW}/ofl/anton/Anton-Regular.ttf",
}
SELAWIK_ZIP = "https://github.com/microsoft/Selawik/releases/download/1.01/Selawik_Release.zip"
# Curated Noto subset for non-Latin script coverage (SIL OFL). Kept under their
# real names (universal fallback fonts personas legitimately have). Copied
# as-is, no rename. Variable-font URLs are URL-encoded ([wght] -> %5Bwght%5D).
NOTO = {
    "NotoSans": "ofl/notosans/NotoSans%5Bwdth,wght%5D.ttf",
    "NotoSansArabic": "ofl/notosansarabic/NotoSansArabic%5Bwdth,wght%5D.ttf",
    "NotoSansHebrew": "ofl/notosanshebrew/NotoSansHebrew%5Bwdth,wght%5D.ttf",
    "NotoSansThai": "ofl/notosansthai/NotoSansThai%5Bwdth,wght%5D.ttf",
    "NotoSansDevanagari": "ofl/notosansdevanagariui/NotoSansDevanagariUI-Regular.ttf",
    "NotoSansBengali": "ofl/notosansbengali/NotoSansBengali%5Bwdth,wght%5D.ttf",
    "NotoSansGeorgian": "ofl/notosansgeorgian/NotoSansGeorgian%5Bwdth,wght%5D.ttf",
    "NotoSansArmenian": "ofl/notosansarmenian/NotoSansArmenian%5Bwdth,wght%5D.ttf",
    "NotoSansSC": "ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf",  # CJK (large)
}
DEJAVU_ZIP = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
# DejaVu faces are already correctly named (open, Bitstream-derived license); no
# rename needed — Linux personas legitimately claim them.
DEJAVU_FACES = {
    "DejaVuSans": "DejaVuSans.ttf",
    "DejaVuSerif": "DejaVuSerif.ttf",
    "DejaVuSansMono": "DejaVuSansMono.ttf",
}

# target family (what personas claim) -> open substitute source
MAPPING = {
    "Arial": "Arimo",
    "Helvetica": "Arimo",
    "Helvetica Neue": "Arimo",
    "Trebuchet MS": "Arimo",
    "Verdana": "DejaVuSans",  # DejaVu Sans is a closer humanist-sans match
    "Tahoma": "DejaVuSans",
    # Linux generic families (personas claim these; used by GENERIC_FONTS.linux).
    "DejaVu Sans": "DejaVuSans",
    "DejaVu Serif": "DejaVuSerif",
    "DejaVu Sans Mono": "DejaVuSansMono",
    "Times New Roman": "Tinos",
    "Times": "Tinos",
    "Georgia": "Gelasio",
    "Courier New": "Cousine",
    "Courier": "Cousine",
    "Consolas": "Cousine",    # monospace approximation
    "Menlo": "Cousine",
    "Monaco": "Cousine",
    "Calibri": "Carlito",
    "Segoe UI": "Selawik",
    "Cambria": "Caladea",
    "Comic Sans MS": "ComicNeue",
    "Impact": "Anton",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "cloakfox-fontpack"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> int:
    cache = Path("/tmp/cloakfox-fontsrc")
    cache.mkdir(exist_ok=True)
    out = Path("bundle/fonts/macos")
    out.mkdir(parents=True, exist_ok=True)

    srcfiles = {}
    for name, url in SOURCES.items():
        dst = cache / f"{name}.ttf"
        if not dst.exists():
            print(f"fetch {name} ...", flush=True)
            dst.write_bytes(fetch(url))
        srcfiles[name] = dst

    # Selawik ships a release zip; pull the Regular face out of it.
    sel = cache / "Selawik.ttf"
    if not sel.exists():
        print("fetch Selawik ...", flush=True)
        z = zipfile.ZipFile(io.BytesIO(fetch(SELAWIK_ZIP)))
        # Selawik's Regular face is "selawk.ttf" (weights add a suffix letter).
        member = next(n for n in z.namelist()
                      if os.path.basename(n).lower() == "selawk.ttf")
        sel.write_bytes(z.read(member))
    srcfiles["Selawik"] = sel

    # DejaVu faces (Linux generics) from the release zip.
    if not all((cache / f"{k}.ttf").exists() for k in DEJAVU_FACES):
        print("fetch DejaVu ...", flush=True)
        dz = zipfile.ZipFile(io.BytesIO(fetch(DEJAVU_ZIP)))
        for key, fname in DEJAVU_FACES.items():
            member = next(n for n in dz.namelist()
                          if os.path.basename(n) == fname)
            (cache / f"{key}.ttf").write_bytes(dz.read(member))
    for key in DEJAVU_FACES:
        srcfiles[key] = cache / f"{key}.ttf"

    made = 0
    for target, source in MAPPING.items():
        src = srcfiles.get(source)
        if not src or not src.exists():
            print(f"SKIP {target}: source {source} missing")
            continue
        rename_mod.rename(str(src), str(out / f"{target.replace(' ', '')}.ttf"), target)
        made += 1

    # Noto script coverage — fetched and copied under their real names (no
    # rename); they serve as the universal fallback for non-Latin scripts.
    noto = 0
    for name, path in NOTO.items():
        dst = cache / f"{name}.ttf"
        if not dst.exists():
            print(f"fetch {name} ...", flush=True)
            dst.write_bytes(fetch(f"{RAW}/{path}"))
        (out / f"{name}.ttf").write_bytes(dst.read_bytes())
        noto += 1

    print(f"\nbuilt {made} Latin families + {noto} Noto script fonts into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
