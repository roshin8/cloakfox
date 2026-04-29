"""
Worker-scope spoofer probe — verifies the C++ patch
patches/cpp-first-worker-spoofers.patch lands at runtime.

The window-side CloakfoxMath JSWindowActor doesn't fire in worker
realms (workers have their own SpiderMonkey context). The
WorkerPrivate.cpp::GetOrCreateGlobalScope injection evaluates a small
IIFE that wraps Math.sin/cos/exp/log etc. with deterministic per-call
ULP-magnitude noise. This probe confirms that:

  1. Worker Math.foo() output differs from native libm reference
     (native sin(0.5) = 0.479425538604203 bit-exact in every
     conforming implementation; if the worker returns that value,
     the spoof did NOT land).
  2. Main-thread Math.foo() is also noised (sanity — confirms
     CloakfoxMath JSWindowActor still works).
  3. Integers and non-finite results (Math.sqrt(4) = 2, Math.log(0)
     = -Infinity) are passed through unchanged — the wrap explicitly
     skips those to avoid breaking spec semantics.

Run:
    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_workers.py
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


# Native libm reference values — bit-exact in every conforming JS
# implementation. Any deviation = spoofer ran.
NATIVE = {
    "sin_0_5":  0.479425538604203,
    "cos_0_5":  0.8775825618903728,
    "tan_0_5":  0.5463024898437905,
    "exp_1":    2.718281828459045,
    "log_2":    0.6931471805599453,
    "asin_0_5": 0.5235987755982989,
    "atan_1":   0.7853981633974483,
}


PROBE_HTML = r"""<!doctype html>
<title>cfx-worker-probe</title>
<body>
<script>
const r = { stage: "main" };

// Main-thread Math values — should be noised by CloakfoxMathChild
// JSWindowActor. We sample several (and the same set inside the worker
// so we can compare) — even one bit-exact match indicates a leak.
r.main_sin_0_5  = Math.sin(0.5);
r.main_cos_0_5  = Math.cos(0.5);
r.main_tan_0_5  = Math.tan(0.5);
r.main_exp_1    = Math.exp(1);
r.main_log_2    = Math.log(2);
r.main_asin_0_5 = Math.asin(0.5);
r.main_atan_1   = Math.atan(1);

// Sanity: integer result should NOT be perturbed (wrap skips Number.isInteger)
r.main_sqrt_4 = Math.sqrt(4);  // expect exactly 2

// Main-thread purity (CloakfoxMath actor). Same input → same output.
r.main_pure = (Math.sin(0.5) === Math.sin(0.5));
r.main_sin_tostring = Math.sin.toString();
r.main_sin_name = Math.sin.name;

// Worker spawn via Blob URL — inline source avoids needing a separate
// .js file and keeps CSP simple for file:// load.
const workerSrc = `
  const out = {};
  out.worker_sin_0_5  = Math.sin(0.5);
  out.worker_cos_0_5  = Math.cos(0.5);
  out.worker_tan_0_5  = Math.tan(0.5);
  out.worker_exp_1    = Math.exp(1);
  out.worker_log_2    = Math.log(2);
  out.worker_asin_0_5 = Math.asin(0.5);
  out.worker_atan_1   = Math.atan(1);
  out.worker_sqrt_4   = Math.sqrt(4);

  // Stealth checks — these are the bits a fingerprinter probes to
  // tell whether the spoof itself is detectable.
  // Purity: Math should be spec-pure. Repeated call on same input
  // must return same value. Real browsers always pass; a per-call PRNG
  // wrap (the earlier draft) fails.
  out.worker_pure = (Math.sin(0.5) === Math.sin(0.5));
  // toString camouflage: native sin reads '[native code]'. A naked
  // function wrapper would expose its source.
  out.worker_sin_tostring = Math.sin.toString();
  out.worker_sin_name = Math.sin.name;
  out.worker_sin_length = Math.sin.length;
  // The lying Function.prototype.toString must itself look native
  // when introspected — otherwise a probe of toString.toString()
  // exposes the override.
  out.worker_fpts_tostring = Function.prototype.toString.toString();
  // Sentinel must NOT exist (earlier draft set Math.__cfx_done__ which
  // was trivially detectable).
  out.worker_no_sentinel = (typeof Math.__cfx_done__ === 'undefined');

  postMessage(out);
`;

const blob = new Blob([workerSrc], { type: "application/javascript" });
const url  = URL.createObjectURL(blob);
const w    = new Worker(url);

let finalized = false;
function finalize() {
  if (finalized) return;
  finalized = true;
  document.documentElement.setAttribute('data-cfx-probe', JSON.stringify(r));
  document.title = "PROBE_DONE";
}

w.onmessage = (e) => {
  Object.assign(r, e.data);
  finalize();
};
w.onerror = (e) => {
  r.worker_err = String(e.message || e);
  finalize();
};

// Hard timeout — workers occasionally hang; don't block the probe.
setTimeout(() => { if (!finalized) { r.worker_timeout = true; finalize(); } }, 4000);
</script>
</body>
"""


def _build_driver(bin_path: str, profile_dir: str):
    """Profile pre-seeded with cloakfox.enabled + a math_seed so SeedSync
    derives math:trig_seed into cloak_cfg before any worker can spawn —
    otherwise MaskConfig::GetUint32 returns nullopt and the worker
    spoofer is a no-op."""
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    seed = base64.b64encode(secrets.token_bytes(32)).decode()
    (Path(profile_dir) / "user.js").write_text(
        f'user_pref("cloakfox.enabled", true);\n'
        f'user_pref("cloakfox.container.0.math_seed", "{seed}");\n'
        f'user_pref("cloakfox.container.0.timing_seed", "{seed}");\n'
    )
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.add_argument("-profile")
    opts.add_argument(profile_dir)
    svc = Service(log_path=str(Path(profile_dir) / "geckodriver.log"))
    return webdriver.Firefox(options=opts, service=svc)


def assert_workers(r: dict) -> tuple[int, list[str]]:
    fails: list[str] = []

    # 1. Worker must run to completion (postMessage returned).
    if r.get("worker_timeout"):
        fails.append("Worker timed out — no postMessage within 4s")
        return len(fails), fails
    if r.get("worker_err"):
        fails.append(f"Worker errored: {r['worker_err']}")
        return len(fails), fails
    if "worker_sin_0_5" not in r:
        fails.append("Worker never posted message — patch may not have applied")
        return len(fails), fails

    # 2. No detectable sentinel — spoofer must not leave page-readable
    # markers on Math itself. Earlier drafts set Math.__cfx_done__.
    if not r.get("worker_no_sentinel"):
        fails.append(
            "Math.__cfx_done__ leaked to page — sentinel must not be "
            "set on Math (any page can read it and detect the spoof)"
        )

    # 3. PURITY — Math.sin(0.5) === Math.sin(0.5). Real browsers always
    # pass this; a per-call PRNG wrap fails it (the original draft's
    # behavior). High-detectability if violated.
    if not r.get("worker_pure"):
        fails.append(
            "Worker Math is NOT pure — Math.sin(0.5) returns different "
            "values across calls. Noise must hash on input, not advance "
            "PRNG state per call."
        )

    # 4. toString camouflage — native sin reads '[native code]' inside
    # the toString output. A naked function wrapper exposes its source.
    sin_ts = r.get("worker_sin_tostring", "")
    if "[native code]" not in sin_ts:
        fails.append(
            f"Math.sin.toString() = {sin_ts!r} — wrapper source leaked "
            f"(should match native '[native code]' format)"
        )
    fpts_ts = r.get("worker_fpts_tostring", "")
    if "[native code]" not in fpts_ts:
        fails.append(
            f"Function.prototype.toString.toString() = {fpts_ts!r} — "
            f"the lying toString itself is detectable"
        )

    # 5. name + length camouflage
    if r.get("worker_sin_name") != "sin":
        fails.append(
            f"Math.sin.name = {r.get('worker_sin_name')!r}, want 'sin'"
        )
    if r.get("worker_sin_length") != 1:
        fails.append(
            f"Math.sin.length = {r.get('worker_sin_length')}, want 1"
        )

    # 3. Each sampled Math.foo() in the worker must NOT equal the native
    # libm value. Equality means the spoof didn't apply for that op.
    for key, native in NATIVE.items():
        wkey = f"worker_{key}"
        if wkey not in r:
            fails.append(f"Worker missing {wkey}")
            continue
        if r[wkey] == native:
            fails.append(
                f"Worker {wkey} = {r[wkey]!r} (bit-exact native libm) — "
                f"spoof did NOT apply to this op"
            )

    # 4. Main-thread sanity — same assertion (CloakfoxMath actor should
    # have wrapped these). If main-thread fails, problem isn't worker-
    # scope-specific.
    for key, native in NATIVE.items():
        mkey = f"main_{key}"
        if mkey not in r:
            fails.append(f"Main thread missing {mkey}")
            continue
        if r[mkey] == native:
            fails.append(
                f"Main thread {mkey} = {r[mkey]!r} (bit-exact native libm) — "
                f"CloakfoxMath actor regression, not just a worker problem"
            )

    # 5. Integer results pass through unchanged (Number.isInteger guard).
    if r.get("worker_sqrt_4") != 2:
        fails.append(
            f"worker_sqrt_4 = {r.get('worker_sqrt_4')!r}, want 2 — "
            f"integer-pass-through guard broken in worker spoofer"
        )
    if r.get("main_sqrt_4") != 2:
        fails.append(
            f"main_sqrt_4 = {r.get('main_sqrt_4')!r}, want 2 — "
            f"integer-pass-through guard broken in main-thread spoofer"
        )

    # 6. Main-thread stealth parity.
    if not r.get("main_pure"):
        fails.append(
            "Main thread Math is NOT pure — CloakfoxMath actor still "
            "uses per-call PRNG instead of input-hashed noise"
        )
    if "[native code]" not in r.get("main_sin_tostring", ""):
        fails.append(
            f"Main Math.sin.toString() = {r.get('main_sin_tostring')!r} — "
            f"Cu.exportFunction camouflage failed (or not used)"
        )
    if r.get("main_sin_name") != "sin":
        fails.append(
            f"Main Math.sin.name = {r.get('main_sin_name')!r}, want 'sin'"
        )

    return len(fails), fails


def main() -> None:
    bin_path = os.environ.get("CLOAKFOX_BIN")
    if not bin_path or not os.path.exists(bin_path):
        sys.exit("CLOAKFOX_BIN not set or binary missing")

    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "profile")
        probe_html = os.path.join(tmp, "probe.html")
        Path(probe_html).write_text(PROBE_HTML)

        d = _build_driver(bin_path, prof)
        try:
            d.get(f"file://{probe_html}")
            deadline = time.time() + 8
            while time.time() < deadline:
                if d.title == "PROBE_DONE":
                    break
                time.sleep(0.2)
            attr = d.find_element("css selector", "html").get_attribute("data-cfx-probe")
            if not attr:
                sys.exit("probe never finished — no data-cfx-probe attribute")
            result = json.loads(attr)
        finally:
            d.quit()

    print(json.dumps(result, indent=2))
    print()

    fail_count, fails = assert_workers(result)
    if fail_count == 0:
        print(
            f"WORKER SPOOFER PASS — {len([k for k in result if k.startswith('worker_')])} "
            f"worker signals + {len([k for k in result if k.startswith('main_')])} main signals"
        )
        sys.exit(0)
    print(f"WORKER SPOOFER FAIL ({fail_count} issues):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)


if __name__ == "__main__":
    main()
