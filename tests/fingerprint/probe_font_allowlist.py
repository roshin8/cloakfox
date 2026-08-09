"""
Font-allowlist regression probe.

The C++ font-hijacker treats cloak_cfg "fonts" (or, on the first launch of
a fresh profile, a conservative built-in fallback) as an ALLOWLIST: only
listed system fonts are exposed. The persona mapper used to DROP the fonts
key entirely, so the allowlist stayed inactive and the browser leaked the
real host's system fonts — unspoofed and OS-incoherent.

Host-independent check: enumerate a broad cross-OS panel of fonts with the
persona ACTIVE vs DISABLED. With the allowlist working, the active set must
be a STRICT SUBSET of the disabled (real-host) set — the allowlist can only
remove fonts, and every real OS has distinctive fonts that get filtered out.
If the active set equals the host set, the allowlist is inactive (the bug).

  disabled (enabled=false): H = host fonts present from the panel
  active   (enabled=true):  P = fonts present with the persona/fallback list
  PASS iff  P ⊂ H  (P ⊆ H and P != H)

Exit codes: 0 pass · 1 allowlist inactive · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_font_allowlist.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

# Broad panel: OS-distinctive fonts (so the host set is non-trivial on any
# platform) plus a few web-safe fonts common to the allowlist and the host.
PANEL = [
    # macOS-distinctive
    "Helvetica Neue", "Menlo", "Geneva", "Chalkduster", "Zapfino", "Cochin",
    "Optima", "Monaco", "Papyrus",
    # Windows-distinctive
    "Segoe UI", "Calibri", "Cambria", "Consolas", "Marlett", "Ebrima",
    "Nirmala UI", "Gadugi",
    # Linux-distinctive
    "DejaVu Sans", "Ubuntu", "Liberation Sans", "Cantarell", "FreeSans",
    # web-safe (expected in both sets)
    "Arial", "Times New Roman", "Georgia", "Verdana", "Courier New",
]

PROBE = """
const s = document.createElement('script');
s.textContent = `
  const PANEL = %s;
  function present(font){
    const base = ['monospace','sans-serif','serif'];
    const txt = 'mmmmmmmmmmlli WW@@gjpqy';
    const span = document.createElement('span');
    span.style.cssText = 'position:absolute;left:-9999px;font-size:72px';
    span.textContent = txt; document.body.appendChild(span);
    let det = false;
    for (const b of base){
      span.style.fontFamily = b;
      const w0 = span.offsetWidth, h0 = span.offsetHeight;
      span.style.fontFamily = '"' + font + '",' + b;
      if (span.offsetWidth !== w0 || span.offsetHeight !== h0){ det = true; break; }
    }
    document.body.removeChild(span); return det;
  }
  const found = PANEL.filter(present);
  const out = document.createElement('pre');
  out.id = '_fonts'; out.textContent = JSON.stringify(found);
  document.body.appendChild(out);
`;
document.body.appendChild(s);
""" % json.dumps(PANEL)


def detect(bin_path: str, enabled: bool) -> list:
    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "p")
        Path(prof).mkdir()
        Path(prof, "user.js").write_text(
            f'user_pref("cloakfox.enabled", {str(enabled).lower()});\n'
        )
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(options=opts,
                              service=Service(service_args=["--allow-system-access"], log_output=str(Path(prof) / "gd.log")))
        try:
            d.set_page_load_timeout(30)
            d.get("https://example.com/")
            time.sleep(1.5)
            d.get("https://example.com/?warm=1")
            time.sleep(1.5)
            d.execute_script(PROBE)
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    raw = d.find_element("id", "_fonts").text
                    if raw:
                        return json.loads(raw)
                except Exception:
                    pass
                time.sleep(0.3)
            return None
        finally:
            d.quit()


def main(bin_path: str) -> int:
    host = detect(bin_path, enabled=False)
    active = detect(bin_path, enabled=True)
    if host is None or active is None:
        print("could not enumerate fonts (probe didn't run)")
        return 2

    H, P = set(host), set(active)
    print(f"  host fonts (enabled=false), {len(H)}: {sorted(H)}")
    print(f"  persona fonts (enabled=true), {len(P)}: {sorted(P)}")
    print(f"  blocked by allowlist: {sorted(H - P) or 'none'}")
    print()

    if not H:
        print("INCONCLUSIVE — no panel fonts present even unspoofed; can't "
              "assess the allowlist on this host")
        return 2
    extra = P - H
    if extra:
        print(f"INCONCLUSIVE — persona exposes fonts absent when disabled "
              f"{sorted(extra)} (unexpected; allowlist can only remove)")
        return 2
    if P == H:
        print("FAIL — persona font set equals the real-host set; the "
              "allowlist is inactive and host fonts are leaking")
        return 1
    print(f"PASS — allowlist active: persona set is a strict subset "
          f"({len(P)} ⊂ {len(H)}); host-distinctive fonts filtered out")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
