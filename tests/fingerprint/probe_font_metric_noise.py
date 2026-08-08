"""
Per-container font-metric-noise regression probe.

The anti-font-fingerprinting patch (FontSpacingSeedManager + gfxHarfBuzzShaper)
adds up to 0.1px of letter-spacing PER GLYPH, driven by a per-container seed the
persona publishes in the cloak_cfg blob under "fonts:spacing_seed". This breaks
text-measurement fingerprinting (offsetWidth / getBoundingClientRect) that would
otherwise read the host's exact glyph advances.

CRITICAL — why this probe PRE-SEEDS cloak_cfg instead of letting the persona
generator run: the persona OS is sampled from the seed (see
CloakfoxPersonas.sampleFingerprint), NOT locked to the host. On a ~1/3 of
profiles the persona is Linux, whose allowlist does NOT contain Arial, so a
probe measuring Arial would actually be measuring a SUBSTITUTED font (Arial
falls back to a generic). That width change is substitution, not spacing — a
false PASS that hides a completely dead spacing seed.

To isolate spacing we pin a fixed cloak_cfg_0 whose "fonts" allowlist explicitly
contains Arial (which the bundled font pack also ships, so it renders identically
whether Cloakfox is enabled or disabled). Arial therefore NEVER substitutes, and
the only thing that can move its width is the per-glyph spacing seed. We give two
"personas" the SAME allowlist but DIFFERENT "fonts:spacing_seed" values, so:

  disabled: clean stock Arial width W0 (deterministic — bundled face)
  enabled : W0 + per-glyph spacing; must differ from W0 by >1px, differ between
            the two seeds, and be stable across launches of one profile

A dead seed leaves enabled within jitter of disabled for BOTH seeds -> FAIL,
which is exactly the regression the old Arial-on-Linux false pass masked.

Exit codes: 0 pass · 1 noise inactive/regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_font_metric_noise.py
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

# Allowlist pinned into cloak_cfg_0. Arial is here AND in the bundled font pack,
# so it resolves to a single concrete face under Cloakfox and stock alike — no
# generic-resolution nondeterminism, no substitution. The rest are web-safe
# families so generic CSS still resolves.
PINNED_FONTS = [
    "Arial", "Arial Black", "Comic Sans MS", "Courier New", "Georgia",
    "Impact", "Times New Roman", "Trebuchet MS", "Verdana", "Tahoma",
    "Courier", "Helvetica",
]

# Two personas: identical allowlist, different spacing seeds. Distinct, non-zero.
SPACING_SEED_A = 0x1111_1111
SPACING_SEED_B = 0x7EED_2222

# Arial is guaranteed whitelisted (above) and bundled, so it never substitutes;
# any width change over this long string is pure per-glyph spacing.
MEASURE = r"""
const s = document.createElement('span');
s.style.cssText =
  'position:absolute;left:-9999px;white-space:nowrap;font:16px Arial';
s.textContent = 'WWWWWWWWWW iiiiiiiiii gjpqygjpqy 0123456789'.repeat(3);
document.body.appendChild(s);
return parseFloat(s.getBoundingClientRect().width.toFixed(5));
"""

# A dead seed leaves enabled within jitter of disabled (~0.2px observed); a live
# seed shifts by whole pixels. 1px cleanly separates the two.
MIN_SHIFT_PX = 1.0


def cloak_cfg(spacing_seed: int) -> str:
    """A minimal, fixed cloak_cfg_0 that whitelists Arial and pins the spacing
    seed, so the measurement isolates per-glyph spacing (see module docstring)."""
    return json.dumps({
        "fonts": sorted(PINNED_FONTS),
        "fonts:spacing_seed": spacing_seed,
        # font ordering seed — irrelevant to width, present for coherence.
        "font:seed": 12345,
    })


def write_profile(prof: str, enabled: bool, spacing_seed: int) -> None:
    Path(prof).mkdir(parents=True, exist_ok=True)
    # Pre-seed cloak_cfg_0 via user.js. SeedSync only generates a cfg when the
    # pref is empty, so our fixed value stands; enabling/disabling toggles the
    # C++ spacing path while the allowlist (hence the measured face) is constant.
    cfg = cloak_cfg(spacing_seed).replace("\\", "\\\\").replace('"', '\\"')
    Path(prof, "user.js").write_text(
        f'user_pref("cloakfox.enabled", {str(enabled).lower()});\n'
        f'user_pref("cloakfox.s.cloak_cfg_0", "{cfg}");\n'
    )


def measure(bin_path: str, enabled: bool, spacing_seed: int, prof: str) -> float:
    write_profile(prof, enabled, spacing_seed)
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.add_argument("-remote-allow-system-access")
    opts.add_argument("-profile")
    opts.add_argument(prof)
    d = webdriver.Firefox(options=opts,
                          service=Service(log_path=str(Path(prof) / "gd.log")))
    try:
        d.set_page_load_timeout(30)
        d.get("https://example.com/")
        time.sleep(1.2)
        return float(d.execute_script(MEASURE))
    finally:
        d.quit()


def main(bin_path: str) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        # Disabled baselines use the SAME allowlist (so Arial renders the bundled
        # face) but the spacing path is off — clean stock width, seed-independent.
        w0 = measure(bin_path, False, SPACING_SEED_A, os.path.join(tmp, "d1"))
        w0b = measure(bin_path, False, SPACING_SEED_B, os.path.join(tmp, "d2"))
        ea = measure(bin_path, True, SPACING_SEED_A, os.path.join(tmp, "ea"))
        eb = measure(bin_path, True, SPACING_SEED_B, os.path.join(tmp, "eb"))
        ea2 = measure(bin_path, True, SPACING_SEED_A, os.path.join(tmp, "ea"))

    print(f"  disabled  #1/#2: {w0} / {w0b}")
    print(f"  enabled   A/A':  {ea} / {ea2}")
    print(f"  enabled   B:     {eb}")
    print(f"  |A-disabled|={abs(ea - w0):.3f}px  |B-disabled|={abs(eb - w0b):.3f}px")
    print()

    fails = []
    if w0 != w0b:
        fails.append(f"disabled Arial width differs across profiles ({w0} vs "
                     f"{w0b}) — with Arial whitelisted+bundled this must be "
                     f"deterministic; a difference means substitution leaked in")
    if abs(ea - w0) < MIN_SHIFT_PX and abs(eb - w0b) < MIN_SHIFT_PX:
        fails.append(f"enabled Arial width within {MIN_SHIFT_PX}px of disabled "
                     f"for both seeds — the fonts:spacing_seed noise is dead "
                     f"(check the cloak_cfg key matches C++: fonts:spacing_seed)")
    if ea == eb:
        fails.append("two different spacing seeds produced identical enabled "
                     "width — the seed is not actually driving the spacing")
    if ea != ea2:
        fails.append(f"same profile gave different widths across launches "
                     f"({ea} vs {ea2}) — spacing is not deterministic")

    if fails:
        print("FAIL — font-metric noise regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — enabled shifts Arial width per-seed (deterministically); "
          "disabled measures clean stock metrics on the same whitelisted face")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
