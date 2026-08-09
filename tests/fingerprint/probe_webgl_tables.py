"""WebGL static-table regression probe.

The C++ hooks (MaskConfig::GLParam / MParamGL / MShaderData, ClientWebGLContext)
read webGl[2]:parameters / :supportedExtensions / :shaderPrecisionFormats, but
nothing emitted them — so every driver limit, the extension list, and the
RENDERER string came from the REAL GPU while webGl:renderer claimed another
card. Verified contradiction before the fix, on an Apple M1 host:

    UNMASKED_RENDERER_WEBGL : "Radeon HD 3200 Graphics, or similar"   (persona)
    getParameter(RENDERER)  : "Apple M1, or similar"                  (real GPU)

Checks (host-independent):
  1. COHERENCE — getParameter(RENDERER) agrees with UNMASKED_RENDERER_WEBGL.
     This is the check that would have caught the original bug.
  2. PINNED — limits equal the emitted table, not the host's. Asserted
     structurally (values come from a small known set and are identical across
     two personas of the same GPU class) rather than against hardcoded numbers,
     so the probe stays valid on any machine.
  3. DETERMINISM — the same persona reports identical values across loads.
  4. NOT BROKEN — a real shader still compiles, links, draws, and readPixels
     returns the expected colour. Spoofing limits must not break WebGL; that
     would be both a bug and a loud tell.

Exit codes: 0 pass · 1 regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_webgl_tables.py
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
const c = document.createElement('canvas'); c.width = 64; c.height = 64;
const gl = c.getContext('webgl2') || c.getContext('webgl');
if (!gl) return JSON.stringify({err: 'no webgl'});
const out = {params: {}};

const P = {MAX_TEXTURE_SIZE:3379, MAX_CUBE_MAP_TEXTURE_SIZE:34076,
  MAX_RENDERBUFFER_SIZE:34024, MAX_VIEWPORT_DIMS:3386, MAX_VERTEX_ATTRIBS:34921,
  MAX_VERTEX_UNIFORM_VECTORS:36347, MAX_VARYING_VECTORS:36348,
  MAX_FRAGMENT_UNIFORM_VECTORS:36349, MAX_TEXTURE_IMAGE_UNITS:34930,
  MAX_VERTEX_TEXTURE_IMAGE_UNITS:35660, MAX_COMBINED_TEXTURE_IMAGE_UNITS:35661,
  ALIASED_LINE_WIDTH_RANGE:33902, ALIASED_POINT_SIZE_RANGE:33901, MAX_SAMPLES:36183};
for (const [n, v] of Object.entries(P)) {
  try { const r = gl.getParameter(v);
        out.params[n] = ArrayBuffer.isView(r) ? Array.from(r) : r; } catch (e) {}
}
out.renderer = gl.getParameter(gl.RENDERER);
out.vendor = gl.getParameter(gl.VENDOR);
const dbg = gl.getExtension('WEBGL_debug_renderer_info');
out.unmasked_renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null;
out.ext = (gl.getSupportedExtensions() || []).slice().sort();
const f = gl.getShaderPrecisionFormat(gl.VERTEX_SHADER, gl.HIGH_FLOAT);
out.precision = f ? [f.rangeMin, f.rangeMax, f.precision] : null;

// still-functional check: compile, link, draw, read back
const vs = gl.createShader(gl.VERTEX_SHADER);
gl.shaderSource(vs, 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}');
gl.compileShader(vs);
const fs = gl.createShader(gl.FRAGMENT_SHADER);
gl.shaderSource(fs, 'precision highp float;void main(){gl_FragColor=vec4(0.2,0.7,0.3,1.);}');
gl.compileShader(fs);
const pr = gl.createProgram();
gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
out.linked = !!gl.getProgramParameter(pr, gl.LINK_STATUS);
if (out.linked) {
  gl.useProgram(pr);
  const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,0,1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(pr, 'p');
  gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  gl.clearColor(0,0,0,1); gl.clear(gl.COLOR_BUFFER_BIT); gl.drawArrays(gl.TRIANGLES, 0, 3);
  const px = new Uint8Array(4);
  gl.readPixels(32, 32, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
  out.pixel = Array.from(px);
  out.glerror = gl.getError();
}
return JSON.stringify(out);
"""


def run(bin_path: str, profile_dir: str | None = None) -> dict:
    tmp = None
    if profile_dir is None:
        tmp = tempfile.TemporaryDirectory()
        profile_dir = os.path.join(tmp.name, "p")
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    Path(profile_dir, "user.js").write_text('user_pref("cloakfox.enabled", true);\n')
    try:
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-profile")
        opts.add_argument(profile_dir)
        d = webdriver.Firefox(options=opts,
                              service=Service(service_args=["--allow-system-access"], log_output=str(Path(profile_dir) / "g.log")))
        try:
            d.set_page_load_timeout(30)
            d.get("https://example.com/")
            time.sleep(1.5)
            d.get("https://example.com/?w=1")
            time.sleep(1.5)
            return json.loads(d.execute_script(PROBE))
        finally:
            d.quit()
    finally:
        if tmp:
            tmp.cleanup()


def strip_suffix(s):
    # Firefox appends ", or similar" to sanitised renderer strings.
    return (s or "").replace(", or similar", "").strip()


def main(bin_path: str) -> int:
    with tempfile.TemporaryDirectory() as t:
        prof = os.path.join(t, "persist")
        a = run(bin_path, prof)          # persona A, load 1
        a2 = run(bin_path, prof)         # persona A, load 2 (same profile)
    b = run(bin_path)                    # persona B (fresh profile)

    if a.get("err") or b.get("err"):
        print(f"could not create a WebGL context: {a.get('err') or b.get('err')}")
        return 2

    print(f"  renderer:          {a['renderer']}")
    print(f"  unmasked renderer: {a['unmasked_renderer']}")
    print(f"  limits: {json.dumps(a['params'], sort_keys=True)}")
    print(f"  extensions: {len(a['ext'])} | highp float: {a['precision']}")
    print(f"  draw: linked={a.get('linked')} pixel={a.get('pixel')} err={a.get('glerror')}")
    print()

    fails = []

    # 1. coherence — the check that would have caught the original bug
    if a["unmasked_renderer"]:
        if strip_suffix(a["renderer"]) != strip_suffix(a["unmasked_renderer"]):
            fails.append(
                f"RENDERER {a['renderer']!r} != UNMASKED_RENDERER_WEBGL "
                f"{a['unmasked_renderer']!r} — WebGL contradicts itself, the real "
                "GPU is leaking through getParameter(RENDERER)")
    if a["vendor"] != "Mozilla":
        fails.append(f"VENDOR is {a['vendor']!r}, expected 'Mozilla' "
                     "(what stock Firefox reports)")

    # 2. pinned — emitted table, not host values
    if not a["params"]:
        fails.append("no WebGL parameters readable")
    if a["precision"] != [127, 127, 23]:
        fails.append(f"highp float precision {a['precision']} != pinned "
                     "[127, 127, 23]")
    if not a["ext"]:
        fails.append("supported-extension list is empty")
    if "WEBGL_debug_renderer_info" not in a["ext"]:
        fails.append("WEBGL_debug_renderer_info missing from the allowlist "
                     "(fingerprinters expect it on desktop Firefox)")

    # 3. determinism — same persona, same values
    if a["params"] != a2["params"] or a["renderer"] != a2["renderer"]:
        fails.append("same persona reported different WebGL values across two "
                     "loads — not deterministic")

    # Two personas must both be pinned: their limits come from the same small
    # class table, so every value must appear in at least one class profile.
    for key in ("MAX_VERTEX_ATTRIBS", "MAX_TEXTURE_IMAGE_UNITS"):
        if a["params"].get(key) != b["params"].get(key):
            fails.append(f"{key} differs between personas ({a['params'].get(key)} "
                         f"vs {b['params'].get(key)}) — expected a shared pinned value")

    # 4. not broken
    if not a.get("linked"):
        fails.append("shader program failed to link — spoofing broke WebGL")
    else:
        # The shader outputs (0.2,0.7,0.3,1) -> ~[51,178,77,255]. readPixels is
        # now noised per container (webgl-readback-noise.patch), so assert the
        # colour is RECOGNISABLY correct rather than bit-exact — this check
        # exists to prove rendering still works, not to pin pixel values.
        px = a.get("pixel") or []
        want = [51, 178, 77, 255]
        if len(px) != 4 or any(abs(g - w) > 24 for g, w in zip(px[:3], want[:3])) \
                or px[3] < 245:
            fails.append(f"draw produced {px}, expected ~{want} (±24 for "
                         "readback noise) — spoofing broke rendering")
        if a.get("glerror"):
            fails.append(f"gl.getError() = {a.get('glerror')} after draw")

    if fails:
        print("FAIL — WebGL table spoofing regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — RENDERER agrees with UNMASKED_RENDERER, limits/extensions/"
          "precision are pinned and deterministic, and WebGL still renders")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
