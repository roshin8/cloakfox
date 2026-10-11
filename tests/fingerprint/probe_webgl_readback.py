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
  * ClientWebGLContext::DoReadPixels    — gl.readPixels (IPC in Firefox 155)
  * CanvasUtils extraction policy     — configured Cloakfox noise supersedes
                                         Firefox's session-keyed randomization

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
  4. NATIVE FALLBACK — disabled Cloakfox and enabled-but-unconfigured contexts
                retain Firefox 155's session-keyed canvas export randomization.

Exit codes: 0 pass · 1 regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_webgl_readback.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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

async function blobHash(canvas) {
  const blob = await new Promise(resolve => canvas.toBlob(resolve));
  if (!blob) throw new Error('canvas.toBlob returned null');
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let h = 0; for (const b of bytes) h = (h * 31 + b) >>> 0;
  return h.toString(16);
}
return JSON.stringify({linked, corner,
  readPixels: h1.toString(16), webglDataURL: h2.toString(16),
  canvas2d: h3.toString(16), glerror: gl.getError(),
  webglBlob: await blobHash(c), canvas2dBlob: await blobHash(c2)});
"""


def run(bin_path: str, seed: int, *, site_url: str, enabled: bool = True,
        configured: bool = True) -> dict:
    with tempfile.TemporaryDirectory() as t:
        prof = os.path.join(t, "p")
        Path(prof).mkdir()
        # Noise now includes the full master secret and top-level site. Pin the
        # complete identity across profiles, varying only canvas:seed below.
        master = base64.b64encode(bytes(range(32))).decode()
        cfg = {"fingerprint:secret": master,
               "navigator.platform": "Win32",
               "fonts": ["Arial", "Verdana", "Georgia"],
               "fonts:spacing_seed": 0x5EED}
        if configured:
            cfg["canvas:seed"] = seed
        # Keep a valid font configuration so SeedSync does not generate a new
        # persona (and canvas seed) for the unconfigured-canvas control.
        prefs = f'user_pref("cloakfox.enabled", {str(enabled).lower()});\n'
        for vector in ("math_seed", "keyboard_seed", "timing_seed"):
            prefs += f'user_pref("cloakfox.container.0.{vector}", {json.dumps(master)});\n'
        prefs += 'user_pref("dom.security.https_only_mode", false);\n'
        prefs += f'user_pref("cloakfox.s.cloak_cfg_0", {json.dumps(json.dumps(cfg))});\n'
        Path(prof, "user.js").write_text(prefs)
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(options=opts,
                              service=Service(service_args=["--allow-system-access"], log_output=str(Path(prof) / "g.log")))
        try:
            d.set_page_load_timeout(30)
            d.get(site_url)
            time.sleep(1.3)
            d.get(site_url + "?w=1")
            time.sleep(1.3)
            d.set_script_timeout(30)
            return json.loads(d.execute_async_script(
                "const done = arguments[arguments.length - 1];"
                "(async () => {" + PROBE + "})().then(done, "
                "e => done(JSON.stringify({err: String(e)})));")
            )
        finally:
            d.quit()


def check_runs(bin_path: str, site_url: str) -> int:
    a = run(bin_path, 111111, site_url=site_url)
    b = run(bin_path, 999999, site_url=site_url)
    a2 = run(bin_path, 111111, site_url=site_url)      # repeat of A — must reproduce exactly
    base = run(bin_path, 0, site_url=site_url)         # seed 0 = noise disabled -> true baseline

    if a.get("err") or b.get("err"):
        print(f"could not create a WebGL context: {a.get('err') or b.get('err')}")
        return 2

    print(f"  {'SIGNAL':<16}{'seedA':<12}{'seedB':<12}{'seedA again'}")
    for k in ("readPixels", "webglDataURL", "webglBlob", "canvas2d", "canvas2dBlob"):
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

    for k in ("webglBlob", "canvas2dBlob"):
        if a[k] == b[k]:
            fails.append(f"{k} identical across different configured seeds")

    # 2. deterministic
    for k in ("readPixels", "webglDataURL", "webglBlob", "canvas2d", "canvas2dBlob"):
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

    # 4. Native fallback stays session-randomized for both bypass cases.
    for label, options in (
        ("disabled", {"enabled": False}),
        ("unconfigured", {"configured": False}),
    ):
        native = [run(bin_path, 111111, site_url=site_url, **options) for _ in range(2)]
        if any(result.get("err") for result in native):
            fails.append(f"{label} native canvas probe could not run: {native}")
            continue
        for k in ("webglDataURL", "webglBlob", "canvas2d", "canvas2dBlob"):
            if native[0][k] == native[1][k]:
                fails.append(f"{label} {k} lost native session randomization")
        print(f"  native {label}: {native[0]['webglDataURL']} / "
              f"{native[1]['webglDataURL']}")

    if fails:
        print("FAIL — WebGL readback noise regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — seeded readPixels/toDataURL/toBlob are deterministic, "
          "rendering is intact, and disabled/unconfigured native policy remains")
    return 0


def main(bin_path: str) -> int:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = b"<!doctype html><meta charset=utf-8><title>WebGL probe</title>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    # One server/origin spans all fresh profiles, including native controls.
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        return check_runs(bin_path, f"http://127.0.0.1:{server.server_port}/")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
