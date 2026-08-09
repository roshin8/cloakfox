"""WebGL pixel-readback noise regression probe ("webglHash").

The 2D canvas has been noised per container for a long time, but the WebGL
readback paths were completely unprotected: draw a scene, then either
canvas.toDataURL()/toBlob() on the WebGL context or gl.readPixels(), and the
result was byte-identical across containers and across machines. That is the
classic webglHash used by FingerprintJS and CreepJS. Verified before the fix:
two personas with different canvas:seed produced the same readPixels hash
(15e80087) and the same toDataURL hash (62625e96), while the 2D canvas beside
them correctly differed.

Both paths now run the same CanvasFingerprintManager noise as the 2D context,
keyed on the same canvas:seed so a container's surfaces stay mutually
consistent:
  * ClientWebGLContext::GetImageBuffer  — toDataURL / toBlob
  * ClientWebGLContext::DoReadPixels    — gl.readPixels (both the in-process
                                          and the IPC path)

readPixels noise is deliberately limited to 8-bit RGBA: float/integer formats
are used for GPU compute readback, where perturbing values corrupts results
rather than defending a fingerprint.

Checks (host-independent):
  1. NOISED   — two different canvas:seed values produce different readPixels
                and different WebGL toDataURL hashes.
  2. DETERMINISTIC — the same seed reproduces its hashes exactly (the
                same-container-same-fingerprint invariant; Gecko's own
                Randomize path re-randomises per call and would fail this).
  3. NOT BROKEN — a real shader still compiles, links and draws, and the
                readback is only subtly perturbed, not corrupted.

Exit codes: 0 pass · 1 regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_webgl_readback.py
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

PROBE = r"""
const c = document.createElement('canvas'); c.width = 128; c.height = 128;
const gl = c.getContext('webgl');
if (!gl) return JSON.stringify({err: 'no webgl'});
const vs = gl.createShader(gl.VERTEX_SHADER);
gl.shaderSource(vs, 'attribute vec2 p;varying vec2 v;void main(){v=p;gl_Position=vec4(p,0.,1.);}');
gl.compileShader(vs);
const fs = gl.createShader(gl.FRAGMENT_SHADER);
gl.shaderSource(fs, 'precision highp float;varying vec2 v;void main(){gl_FragColor=vec4(v.x*0.5+0.5,v.y*0.5+0.5,0.7,1.);}');
gl.compileShader(fs);
const pr = gl.createProgram();
gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
const linked = !!gl.getProgramParameter(pr, gl.LINK_STATUS);
gl.useProgram(pr);
const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,0,1]), gl.STATIC_DRAW);
const l = gl.getAttribLocation(pr, 'p');
gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, 2, gl.FLOAT, false, 0, 0);
gl.clearColor(0.1, 0.2, 0.3, 1); gl.clear(gl.COLOR_BUFFER_BIT);
gl.drawArrays(gl.TRIANGLES, 0, 3);

const px = new Uint8Array(128 * 128 * 4);
gl.readPixels(0, 0, 128, 128, gl.RGBA, gl.UNSIGNED_BYTE, px);
let h1 = 0; for (let i = 0; i < px.length; i++) h1 = (h1 * 31 + px[i]) >>> 0;
const u = c.toDataURL();
let h2 = 0; for (let i = 0; i < u.length; i++) h2 = (h2 * 31 + u.charCodeAt(i)) >>> 0;

// Sample a pixel for the "perturbed, not corrupted" check. The probe compares
// it against an unnoised baseline run rather than a hardcoded expectation —
// the triangle covers this corner, so the value is shader output, not the
// clear colour.
const corner = [px[0], px[1], px[2], px[3]];

// 2D canvas control — already known-good, proves the seed reached the process.
const c2 = document.createElement('canvas'); c2.width = 100; c2.height = 40;
const x = c2.getContext('2d');
x.font = '14px Arial'; x.fillStyle = '#069'; x.fillText('cfx 0123', 2, 20);
const u2 = c2.toDataURL();
let h3 = 0; for (let i = 0; i < u2.length; i++) h3 = (h3 * 31 + u2.charCodeAt(i)) >>> 0;

return JSON.stringify({linked, corner,
  readPixels: h1.toString(16), webglDataURL: h2.toString(16),
  canvas2d: h3.toString(16), glerror: gl.getError()});
"""


def run(bin_path: str, seed: int) -> dict:
    with tempfile.TemporaryDirectory() as t:
        prof = os.path.join(t, "p")
        Path(prof).mkdir()
        cfg = json.dumps({"canvas:seed": seed, "navigator.platform": "Win32"})
        Path(prof, "user.js").write_text(
            'user_pref("cloakfox.enabled", true);\n'
            f'user_pref("cloakfox.s.cloak_cfg_0", {json.dumps(cfg)});\n')
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
            time.sleep(1.3)
            d.get("https://example.com/?w=1")
            time.sleep(1.3)
            return json.loads(d.execute_script(PROBE))
        finally:
            d.quit()


def main(bin_path: str) -> int:
    a = run(bin_path, 111111)
    b = run(bin_path, 999999)
    a2 = run(bin_path, 111111)      # repeat of A — must reproduce exactly
    base = run(bin_path, 0)         # seed 0 = noise disabled -> true baseline

    if a.get("err") or b.get("err"):
        print(f"could not create a WebGL context: {a.get('err') or b.get('err')}")
        return 2

    print(f"  {'SIGNAL':<16}{'seedA':<12}{'seedB':<12}{'seedA again'}")
    for k in ("readPixels", "webglDataURL", "canvas2d"):
        print(f"    {k:<14}{a[k]:<12}{b[k]:<12}{a2[k]}")
    print(f"  corner pixel: noised={a['corner']} baseline={base['corner']}")
    print(f"  linked={a['linked']} glerror={a['glerror']}")
    print()

    fails = []
    # 1. noised
    if a["readPixels"] == b["readPixels"]:
        fails.append("readPixels hash identical across two canvas:seed values — "
                     "WebGL readback is unnoised (the classic webglHash)")
    if a["webglDataURL"] == b["webglDataURL"]:
        fails.append("WebGL toDataURL hash identical across two canvas:seed "
                     "values — the toDataURL/toBlob path is unnoised")
    if a["canvas2d"] == b["canvas2d"]:
        fails.append("2D canvas hash identical across seeds — the seed never "
                     "reached the content process, so this run proves nothing")

    # 2. deterministic
    for k in ("readPixels", "webglDataURL", "canvas2d"):
        if a[k] != a2[k]:
            fails.append(f"{k} changed between two runs of the SAME seed "
                         f"({a[k]} vs {a2[k]}) — noise must be deterministic per "
                         "container, not random per call")

    # 3. not broken
    if not a["linked"]:
        fails.append("shader program failed to link — noise broke WebGL")
    if a["glerror"]:
        fails.append(f"gl.getError() = {a['glerror']} after readPixels")
    # Perturbed, not corrupted: compare against the unnoised baseline rather
    # than a hardcoded colour. Canvas noise is intentionally not ±1 (it must
    # survive rescaling/compression), so allow a generous band but require the
    # pixel to remain recognisably the same colour.
    if base.get("corner") and a.get("corner"):
        deltas = [abs(x - y) for x, y in zip(a["corner"], base["corner"])]
        if max(deltas[:3]) > 64:
            fails.append(f"corner pixel {a['corner']} deviates from the unnoised "
                         f"baseline {base['corner']} by {deltas} — readback looks "
                         "corrupted rather than perturbed")
    if base.get("readPixels") == a.get("readPixels"):
        fails.append("noised readPixels equals the seed-0 baseline — noise did "
                     "not apply at all")

    if fails:
        print("FAIL — WebGL readback noise regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — readPixels and WebGL toDataURL are noised per canvas:seed, "
          "deterministic per container, and rendering is intact")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
