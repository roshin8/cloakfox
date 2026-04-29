#!/usr/bin/env python3
"""
Generate the filtered BrowserForge network for runtime sampling.

BrowserForge ships a 9.5 MB Bayesian network (525 KB gzipped) covering
every desktop+mobile browser fingerprint distribution Apify has trained
on. We don't need most of that — Cloakfox is Firefox-only. This script
extracts the network, prunes every conditional-probability subtree
keyed on a non-Firefox userAgent, and emits the result as an importable
chrome JS module so the runtime sampler can do
`import { NETWORK } from "resource:///modules/CloakfoxBFNetwork.sys.mjs"`.

Output: additions/browser/components/cloakfox/CloakfoxBFNetwork.sys.mjs
Filtered size: ~3.2 MB raw, ~170 KB gzipped (omni.ja stores compressed).

Run when:
    pip install browserforge
    python3 scripts/generate-bf-network.py

Regenerate when:
    - apify_fingerprint_datapoints package updates with new training data
    - Firefox version distribution shifts and you want the latest UAs

Compared to the older scripts/generate-personas.py:
    - generate-personas.py samples N concrete personas from BF and bakes
      them as a fixed pool (CloakfoxPersonaData.sys.mjs)
    - generate-bf-network.py ships the network ITSELF so the runtime
      can sample fresh personas on-demand. Replaces the fixed pool.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

try:
    from apify_fingerprint_datapoints import data_dir
except ImportError:
    # Older browserforge data layout — derive from package location
    try:
        import apify_fingerprint_datapoints as _afd
        data_dir = Path(_afd.__file__).parent / "data"
    except ImportError:
        sys.exit("apify_fingerprint_datapoints not installed. "
                 "Run: pip install browserforge")


REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "additions/browser/components/cloakfox/CloakfoxBFNetwork.sys.mjs"

# Network zip ships inside apify_fingerprint_datapoints.
NETWORK_ZIP = Path(data_dir) / "fingerprint-network-definition.zip"


def filter_probs(probs, allowed_uas, depth=0):
    """Recursively filter conditional-probability subtrees to keep only
    paths where the userAgent parent (always the first / only parent in
    this network's structure) is in allowed_uas. Drops 'skip' fallbacks
    since we never reach them with a tight UA filter."""
    if not isinstance(probs, dict):
        return probs
    if "deeper" not in probs and "skip" not in probs:
        return probs  # leaf: {value: prob}

    new = {}
    if "deeper" in probs:
        deeper = probs["deeper"]
        if depth == 0:
            kept = {k: v for k, v in deeper.items() if k in allowed_uas}
        else:
            kept = deeper
        new_deeper = {
            k: filter_probs(v, allowed_uas, depth + 1) for k, v in kept.items()
        }
        if new_deeper:
            new["deeper"] = new_deeper
    if "skip" in probs:
        sk = filter_probs(probs["skip"], allowed_uas, depth + 1)
        if sk:
            new["skip"] = sk
    return new


def main() -> None:
    if not NETWORK_ZIP.exists():
        sys.exit(f"Network zip not found at {NETWORK_ZIP}. "
                 "Reinstall browserforge with `pip install browserforge --force-reinstall`.")

    with zipfile.ZipFile(NETWORK_ZIP, "r") as zf:
        with zf.open("network.json") as f:
            net = json.load(f)

    # Find every Firefox UA in the network's pool.
    ua_node = next(n for n in net["nodes"] if n["name"] == "userAgent")
    firefox_uas = sorted(
        v for v in ua_node["possibleValues"] if "Firefox" in v
    )
    if not firefox_uas:
        sys.exit("No Firefox UAs in the BF network — data file may be corrupted")
    print(f"Firefox UAs in network: {len(firefox_uas)}")
    for ua in firefox_uas:
        print(f"  {ua[:90]}")

    # Drop mobile (Android) — we ship desktop Firefox.
    desktop_uas = [u for u in firefox_uas if "Android" not in u and "Mobile" not in u]
    print(f"Desktop Firefox UAs: {len(desktop_uas)}")

    # Build filtered network.
    out = {"nodes": []}
    for node in net["nodes"]:
        new_node = dict(node)
        if node["name"] == "userAgent":
            # The root's conditionalProbabilities is the unconditional
            # distribution. Reduce to just the desktop Firefox UAs and
            # renormalize so probabilities sum to 1.0.
            new_node["possibleValues"] = desktop_uas
            cp = node["conditionalProbabilities"]
            sub = {ua: cp[ua] for ua in desktop_uas if ua in cp}
            total = sum(sub.values())
            if total > 0:
                sub = {k: v / total for k, v in sub.items()}
            new_node["conditionalProbabilities"] = sub
        else:
            new_node["conditionalProbabilities"] = filter_probs(
                node["conditionalProbabilities"], desktop_uas, 0
            )
        out["nodes"].append(new_node)

    # Emit as a JS module. Single big NETWORK export = synchronous import,
    # zero parsing-on-fetch, ships compressed in omni.ja.
    js_body = "export const NETWORK = " + json.dumps(out, separators=(",", ":")) + ";\n"
    header = (
        "/* This Source Code Form is subject to the terms of the Mozilla Public\n"
        " * License, v. 2.0. If a copy of the MPL was not distributed with this\n"
        " * file, You can obtain one at http://mozilla.org/MPL/2.0/. */\n\n"
        "/* AUTO-GENERATED by scripts/generate-bf-network.py — do not edit by hand.\n"
        " *\n"
        " * Filtered subset of Apify BrowserForge's fingerprint Bayesian network.\n"
        " * Pruned to desktop-Firefox-only UAs so the runtime sampler in\n"
        " * CloakfoxPersonas.sys.mjs (via CloakfoxBayesianNetwork) draws coherent\n"
        " * Firefox fingerprints without carrying the full ~9.5MB multi-browser\n"
        " * network. Regenerate with `python3 scripts/generate-bf-network.py`.\n"
        " */\n\n"
    )
    OUT.write_text(header + js_body)
    print(f"\nWrote {OUT.relative_to(REPO)} ({len(js_body):,} bytes)")


if __name__ == "__main__":
    main()
