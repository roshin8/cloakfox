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

# target family (what personas claim) -> open substitute source
MAPPING = {
    "Arial": "Arimo",
    "Helvetica": "Arimo",
    "Helvetica Neue": "Arimo",
    "Trebuchet MS": "Arimo",
    "Verdana": "Arimo",       # no exact open match; Arimo approximates
    "Tahoma": "Arimo",        # ditto
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

    made = 0
    for target, source in MAPPING.items():
        src = srcfiles.get(source)
        if not src or not src.exists():
            print(f"SKIP {target}: source {source} missing")
            continue
        rename_mod.rename(str(src), str(out / f"{target.replace(' ', '')}.ttf"), target)
        made += 1
    print(f"\nbuilt {made} families into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
