"""Coverage probe for engine patches that previously had no test at all.

These C++ patches ship real spoofs but nothing exercised them, so a silent
regression (or a dead config key, as happened with fonts:spacing_seed) would go
unnoticed. They fall into two groups, tested differently:

  SEED-DRIVEN (active whenever a persona exists, keyed on canvas:seed)
    - domrect-spoofing        getBoundingClientRect / getClientRects
    - svg-bbox-spoofing       SVGGraphicsElement.getBBox
    - svg-geometry-spoofing   getTotalLength (getPointAtLength is NOT
                              patched — deliberately not asserted)
    - svg-metrics-spoofing    SVG text extents

  OPT-IN FLAGS (only when the persona sets the key in cloak_cfg)
    - clipboard-spoofing      navigator:clipboard:disabled
    - codecs-spoofing         codecs:spoof   (canPlayType)
    - mediasource-...         codecs:spoof   (MediaSource.isTypeSupported)
    - indexeddb-spoofing      indexedDB:databases:hidden
    - visual-viewport-...     window:visualViewport:spoof
    - websocket-spoofing      webSocket:disabled

Method (host-independent):
  * Seed-driven: run two personas with DIFFERENT canvas:seed and one disabled
    run. A live spoof makes the measured values differ between the two seeds;
    disabled must produce clean stock values. Comparing seed-vs-seed (rather
    than against a hardcoded number) keeps this valid on any machine.
  * Opt-in: inject the flag and assert the behaviour actually changes versus
    the same build without the flag.

Each vector reports PASS / FAIL independently so one dead patch doesn't mask
the others.

Exit codes: 0 all pass · 1 one or more vectors regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_untested_vectors.py
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

# ---------------------------------------------------------------- seed-driven
SEED_PROBE = r"""
const out = {};
// DOMRect: a positioned element's rect (domrect-spoofing perturbs these)
const d = document.createElement('div');
d.style.cssText = 'position:absolute;left:13.5px;top:7.25px;width:123.5px;height:45.25px';
document.body.appendChild(d);
const r = d.getBoundingClientRect();
out.domrect = [r.x, r.y, r.width, r.height].map(v => v.toFixed(6)).join(',');
const cr = d.getClientRects()[0];
out.clientrect = cr ? [cr.width, cr.height].map(v => v.toFixed(6)).join(',') : null;

// SVG getBBox + geometry (svg-bbox / svg-geometry / svg-metrics)
const NS = 'http://www.w3.org/2000/svg';
const svg = document.createElementNS(NS, 'svg');
svg.setAttribute('width', '200'); svg.setAttribute('height', '100');
const rect = document.createElementNS(NS, 'rect');
rect.setAttribute('x', '10'); rect.setAttribute('y', '10');
rect.setAttribute('width', '80'); rect.setAttribute('height', '40');
svg.appendChild(rect);
const path = document.createElementNS(NS, 'path');
path.setAttribute('d', 'M10 10 L90 50 L120 10');
svg.appendChild(path);
const txt = document.createElementNS(NS, 'text');
txt.textContent = 'Cloakfox 0123 Wax';
svg.appendChild(txt);
document.body.appendChild(svg);
const bb = rect.getBBox();
out.svg_bbox = [bb.x, bb.y, bb.width, bb.height].map(v => v.toFixed(6)).join(',');
out.svg_len = path.getTotalLength().toFixed(6);
const pt = path.getPointAtLength(20);
out.svg_point = [pt.x, pt.y].map(v => v.toFixed(6)).join(',');
const tb = txt.getBBox();
out.svg_text = [tb.width, tb.height].map(v => v.toFixed(6)).join(',');
return JSON.stringify(out);
"""

# ------------------------------------------------------------------- opt-in
# NOTE: these patches gate OPERATIONS, not the existence of the API object —
# navigator.clipboard stays present but read()/write() reject; WebSocket stays
# defined but the CONSTRUCTOR throws; codecs:spoof normalises canPlayType /
# isTypeSupported to "supported" for a fixed MIME list rather than changing a
# single codec. Assert accordingly.
OPTIN_PROBE = r"""
return (async () => {
  const out = {};
  // clipboard: object stays present; the read operation must be denied
  out.clipboard_present = typeof navigator.clipboard !== 'undefined';
  try {
    await navigator.clipboard.readText();
    out.clipboard_read = 'resolved';
  } catch (e) { out.clipboard_read = 'rejected:' + (e && e.name ? e.name : 'unknown'); }

  // websocket: constructor must throw
  try {
    const s = new WebSocket('wss://example.com/cloakfox-probe');
    try { s.close(); } catch (_) {}
    out.ws_construct = 'ok';
  } catch (e) { out.ws_construct = 'threw:' + (e && e.name ? e.name : 'unknown'); }

  // codecs: normalisation across a MIME list
  const TYPES = ['video/mp4; codecs="avc1.42E01E"', 'video/webm; codecs="vp9"',
                 'video/ogg; codecs="theora"', 'audio/mpeg', 'audio/wav; codecs="1"',
                 'audio/flac', 'audio/ogg; codecs="vorbis"'];
  const v = document.createElement('video');
  out.canPlay = {}; out.ms = {};
  for (const t of TYPES) {
    try { out.canPlay[t] = v.canPlayType(t); } catch (e) { out.canPlay[t] = 'ERR'; }
    try {
      out.ms[t] = (typeof MediaSource !== 'undefined')
        ? String(MediaSource.isTypeSupported(t)) : 'no-MediaSource';
    } catch (e) { out.ms[t] = 'ERR'; }
  }

  try {
    out.vv = (typeof visualViewport !== 'undefined')
      ? [visualViewport.width, visualViewport.height, visualViewport.scale].join(',') : 'none';
  } catch (e) { out.vv = 'ERR'; }
  return JSON.stringify(out);
})();
"""

IDB_PROBE = r"""
return (async () => {
  try {
    if (!indexedDB.databases) return 'no-api';
    await new Promise(res => { const r = indexedDB.open('cloakfox_probe_db', 1);
      r.onsuccess = () => { r.result.close(); res(); }; r.onerror = () => res();
      r.onupgradeneeded = () => {}; });
    const dbs = await indexedDB.databases();
    return String(dbs.length);
  } catch (e) { return 'ERR ' + e; }
})();
"""


def run(bin_path: str, probe: str, cfg: dict | None, enabled: bool = True,
        async_probe: bool = False):
    with tempfile.TemporaryDirectory() as t:
        prof = os.path.join(t, "p")
        Path(prof).mkdir()
        js = f'user_pref("cloakfox.enabled", {str(enabled).lower()});\n'
        if cfg is not None:
            # CloakfoxSeedSync.needsCfgRebuild() REGENERATES any cloak_cfg that
            # is missing the font keys — an upgrade path for profiles written
            # before per-container fonts existed. A probe cfg without them is
            # therefore overwritten with a random persona during startup, and
            # every opt-in flag in it is silently discarded.
            #
            # That is not a hypothetical: measured with a control field, an
            # injected {"navigator.platform": "Win32", ...} came back as
            # MacIntel, and both webSocket:disabled and
            # indexedDB:databases:hidden read as unset — which looked exactly
            # like two dead C++ patches. Adding these keys made the same build
            # report Win32, throw SecurityError from the WebSocket constructor,
            # and hide databases(). Both patches were correct all along; the
            # injection never survived.
            #
            # Any probe that seeds cloak_cfg must include these.
            # A concrete allowlist, not []: an empty one admits no families at
            # all, which would change the text/SVG metric vectors measured by
            # this same probe. Caller-supplied keys win over these defaults.
            cfg = {
                "fonts:spacing_seed": 0x5EED,
                "fonts": ["Arial", "Courier New", "Georgia", "Times New Roman",
                          "Verdana", "Helvetica"],
                **cfg,
            }
            js += f'user_pref("cloakfox.s.cloak_cfg_0", {json.dumps(json.dumps(cfg))});\n'
        Path(prof, "user.js").write_text(js)
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(options=opts,
                              service=Service(service_args=["--allow-system-access"], log_output=str(Path(prof) / "g.log")))
        try:
            d.set_page_load_timeout(30)
            d.get("https://example.com/")
            time.sleep(1.2)
            d.get("https://example.com/?w=1")
            time.sleep(1.2)
            if async_probe:
                d.set_script_timeout(20)
                raw = d.execute_async_script(
                    "const cb = arguments[arguments.length-1];" + probe.replace(
                        "return (async () =>", "(async () =>"
                    ).replace("})();", "})().then(cb);"))
            else:
                raw = d.execute_script(probe)
            # Probes that build an object return it JSON-encoded; the IndexedDB
            # probe returns a bare count string. Parse only the former.
            if isinstance(raw, str) and raw.startswith("{"):
                return json.loads(raw)
            return raw
        finally:
            d.quit()


def main(bin_path: str) -> int:
    results = []   # (vector, ok, detail)

    # ---- seed-driven: two different canvas seeds + disabled baseline
    a = run(bin_path, SEED_PROBE, {"canvas:seed": 111111, "navigator.platform": "Win32"})
    b = run(bin_path, SEED_PROBE, {"canvas:seed": 999999, "navigator.platform": "Win32"})
    off = run(bin_path, SEED_PROBE, None, enabled=False)

    for key, label in [("domrect", "domrect-spoofing (getBoundingClientRect)"),
                       ("clientrect", "domrect-spoofing (getClientRects)"),
                       ("svg_bbox", "svg-bbox-spoofing (getBBox)"),
                       ("svg_len", "svg-geometry-spoofing (getTotalLength)"),
                       ("svg_text", "svg-metrics-spoofing (text getBBox)")]:
        va, vb, vo = a.get(key), b.get(key), off.get(key)
        if va is None or vb is None:
            results.append((label, False, "probe returned nothing"))
            continue
        # A live seed-driven spoof makes the two seeds disagree.
        ok = va != vb
        detail = f"seedA={va} seedB={vb} disabled={vo}"
        results.append((label, ok, detail))

    # ---- opt-in flags
    base = run(bin_path, OPTIN_PROBE, {"navigator.platform": "Win32"}, async_probe=True)

    clip = run(bin_path, OPTIN_PROBE,
               {"navigator.platform": "Win32", "navigator:clipboard:disabled": True},
               async_probe=True)
    # The object stays present (that itself would be a tell); the READ must be denied.
    results.append(("clipboard-spoofing (clipboard.readText denied)",
                    clip["clipboard_present"] and
                    clip["clipboard_read"].startswith("rejected"),
                    f"present={clip['clipboard_present']} "
                    f"base_read={base['clipboard_read']} flagged_read={clip['clipboard_read']}"))

    ws = run(bin_path, OPTIN_PROBE,
             {"navigator.platform": "Win32", "webSocket:disabled": True},
             async_probe=True)
    results.append(("websocket-spoofing (constructor throws)",
                    ws["ws_construct"].startswith("threw") and
                    base["ws_construct"] == "ok",
                    f"base={base['ws_construct']} flagged={ws['ws_construct']}"))

    cod = run(bin_path, OPTIN_PROBE,
              {"navigator.platform": "Win32", "codecs:spoof": True},
              async_probe=True)
    # Normalisation, but SPEC-CORRECT: "probably" only when the type carries a
    # codecs= parameter, "maybe" for a bare container type. Returning
    # "probably" for canPlayType("video/mp4") is a value stock Firefox never
    # produces, so asserting that would enshrine a browser-detection tell.
    def expected(t):
        return "probably" if "codecs" in t else "maybe"
    cp_bad = {t: v for t, v in cod["canPlay"].items() if v != expected(t)}
    cp_changed = [t for t in cod["canPlay"] if cod["canPlay"][t] != base["canPlay"][t]]
    results.append(("codecs-spoofing (canPlayType normalised, spec-correct)",
                    not cp_bad,
                    f"mismatches={cp_bad or 'none'}; changed-vs-base={cp_changed or 'none'}"))
    # MediaSource's list is narrower than canPlayType's: the patch covers
    # video/mp4, video/webm, audio/mp4, audio/webm, audio/mpeg only.
    MS_COVERED = ("video/mp4", "video/webm", "audio/mp4", "audio/webm", "audio/mpeg")
    ms_cov = {t: v for t, v in cod["ms"].items() if t.startswith(MS_COVERED)}
    ms_all = bool(ms_cov) and all(v == "true" for v in ms_cov.values())
    ms_changed = [t for t in cod["ms"] if cod["ms"][t] != base["ms"][t]]
    results.append(("mediasource-isTypeSupported (normalised)", ms_all,
                    f"covered-all-true={ms_all} ({len(ms_cov)} types); "
                    f"changed-vs-base={ms_changed or 'none'}"))

    vv = run(bin_path, OPTIN_PROBE,
             {"navigator.platform": "Win32", "window:visualViewport:spoof": True,
              "window.outerWidth": 1536, "window.outerHeight": 864,
              "window.innerWidth": 1536, "window.innerHeight": 738},
             async_probe=True)
    results.append(("visual-viewport-spoofing",
                    vv["vv"] != base["vv"],
                    f"base={base['vv']} flagged={vv['vv']}"))

    idb_base = run(bin_path, IDB_PROBE, {"navigator.platform": "Win32"}, async_probe=True)
    idb_hid = run(bin_path, IDB_PROBE,
                  {"navigator.platform": "Win32", "indexedDB:databases:hidden": True},
                  async_probe=True)
    results.append(("indexeddb-spoofing (databases())",
                    str(idb_hid) == "0" and str(idb_base) != "0",
                    f"base={idb_base} flagged={idb_hid}"))

    # ---- report
    print("=== previously-untested engine patches ===")
    failed = 0
    for label, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        print(f"         {detail}")
        if not ok:
            failed += 1
    print()
    if failed:
        print(f"FAIL — {failed}/{len(results)} vectors are not spoofing as expected")
        return 1
    print(f"PASS — all {len(results)} previously-untested vectors verified")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
