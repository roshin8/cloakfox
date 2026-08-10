"""
Math constant per-container determinism test.

The Math spoofer replaces `window.Math` with a plain object carrying
per-container-deterministic noisy values for PI, E, LN2, LN10, LOG2E,
LOG10E, SQRT2, SQRT1_2. Function overrides (sin/cos/tan/etc.) get
±1e-12 noise on the return value. The goal: two containers visiting
the same domain produce different Math.PI / Math.sin values, catching
fingerprinters that profile IEEE-constant bit patterns.

Reading the spoofed values from selenium requires care: selenium's
execute_script runs in a "webdriver sandbox" which maintains its own
copy of Math (IEEE-exact). To observe the spoofed value we inject an
inline <script> into the page that runs in page context, writes the
result to the DOM, then read the DOM via find_element. The selenium
sandbox and the page's Math are different bindings even though
`window.Math === Math` inside the page.

Invariants:
  1. Math.PI is perturbed — not equal to the IEEE default.
  2. Same browser session + same page = same Math.PI across reads.
  3. Different browser sessions (different PRNG seeds) produce different
     Math.PI for the same domain.
  4. The perturbation stays within 1e-12 (no visible physics breakage).

Uses httpbin.org/html (no CSP) so we can append <script> tags freely.

Run:

    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        pytest tests/fingerprint/test_math_constants.py -v
"""

import json
import math
import os
import time

import pytest
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

CLOAKFOX_BIN = os.environ.get("CLOAKFOX_BIN")

PROBE_SCRIPT = """
const s = document.createElement('script');
s.textContent = `
  try {
    const out = document.createElement('pre');
    out.id = '_pmathout';
    out.textContent = JSON.stringify({
      pi: Math.PI,
      e: Math.E,
      sin05: Math.sin(0.5),
      windowMathSameAsMath: window.Math === Math,
    });
    document.body.appendChild(out);
  } catch(e) {
    const out = document.createElement('pre');
    out.id = '_pmathout';
    out.textContent = 'ERR: ' + e.message;
    document.body.appendChild(out);
  }
`;
document.body.appendChild(s);
"""


def _build_driver(log_dir: str):
    opts = Options()
    opts.binary_location = CLOAKFOX_BIN
    opts.add_argument("--headless")
    os.makedirs(log_dir, exist_ok=True)
    svc = Service(log_output=f"{log_dir}/geckodriver.log")
    return webdriver.Firefox(options=opts, service=svc)


def _read_math(driver, url: str = "http://httpbin.org/html") -> dict:
    """Navigate, inject probe script, return parsed JSON from DOM."""
    driver.get(url)
    time.sleep(1.5)  # give extension inject time
    driver.execute_script(PROBE_SCRIPT)
    time.sleep(0.3)
    txt = driver.find_element("id", "_pmathout").text
    return json.loads(txt)


@pytest.mark.skipif(
    not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN),
    reason="CLOAKFOX_BIN env var not set or binary missing",
)
def test_math_pi_is_bit_exact_by_default(tmp_path):
    """Math.PI must equal the IEEE default unless constant noise is opted in.

    This test previously asserted the OPPOSITE — that Math.PI diverges — and
    failed, because the policy deliberately changed and the test was never
    updated. It also never ran in CI, so nothing caught the drift.

    CloakfoxMathChild noises the trig FUNCTIONS and leaves the constants
    bit-exact by default (cloakfox.opt.math_constants_noise, default false).
    That is intentional: every real engine returns exactly 3.141592653589793,
    so a perturbed Math.PI is not camouflage — it is a unique, trivially
    queried flag that says "this browser is lying". Same failure mode as
    unseeded timer jitter. Math.sin is the real "did the actor fire" signal
    and is covered by test_math_sin_is_perturbed.
    """
    driver = _build_driver(str(tmp_path))
    try:
        state = _read_math(driver)
        assert state["windowMathSameAsMath"], (
            "window.Math !== Math in page scope — spoofer replaced window.Math "
            "but bare Math identifier still resolves to the engine original"
        )
        assert state["pi"] == math.pi, (
            f"Math.PI == {state['pi']!r}, expected the IEEE default "
            f"({math.pi!r}). Perturbing constants is self-flagging: no real "
            "engine returns anything else, so this is a fingerprint, not a "
            "defence. If constant noise was deliberately enabled, this test "
            "must set cloakfox.opt.math_constants_noise and assert the "
            "bounded-divergence behaviour instead."
        )
    finally:
        driver.quit()


@pytest.mark.skipif(
    not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN),
    reason="CLOAKFOX_BIN env var not set or binary missing",
)
def test_math_pi_deterministic_in_session(tmp_path):
    """Math.PI is stable across reloads within the same session."""
    driver = _build_driver(str(tmp_path))
    try:
        first = _read_math(driver)["pi"]
        second = _read_math(driver)["pi"]
        assert first == second, (
            f"Math.PI drifted across reloads in one session: {first!r} != {second!r}"
        )
    finally:
        driver.quit()


@pytest.mark.skipif(
    not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN),
    reason="CLOAKFOX_BIN env var not set or binary missing",
)
def test_math_pi_is_stable_across_domains(tmp_path):
    """Math.PI is the IEEE constant on every domain.

    Was test_math_pi_differs_across_domains, asserting per-domain divergence.
    Same stale policy as above: constants are bit-exact by default, so they
    are identical everywhere — and must be, since a constant that varies by
    domain is a per-site identifier rather than a defence. Per-domain variation
    belongs to the trig functions, not the constants.
    """
    seen = set()
    for host in ("https://example.com/", "https://example.org/"):
        driver = _build_driver(str(tmp_path / host.replace("://", "_").replace("/", "_")))
        try:
            driver.get(host)
            time.sleep(1.0)
            seen.add(driver.execute_script("return Math.PI;"))
        finally:
            driver.quit()
    assert seen == {math.pi}, (
        f"Math.PI varied across domains ({seen}) or diverged from the IEEE "
        f"default ({math.pi!r}). A constant that changes per site is a "
        "per-site identifier."
    )


@pytest.mark.skipif(
    not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN),
    reason="CLOAKFOX_BIN env var not set or binary missing",
)
def test_math_sin_is_perturbed(tmp_path):
    """Math.sin(0.5) is noisy too (function-level spoof)."""
    driver = _build_driver(str(tmp_path))
    try:
        state = _read_math(driver)
        real = math.sin(0.5)
        delta = abs(state["sin05"] - real)
        assert delta > 0, (
            f"Math.sin(0.5) unspoofed (exact {real!r}) — function-level "
            "spoofer did not run"
        )
        assert delta < 1e-10, (
            f"Math.sin(0.5) noise ({delta:.2e}) exceeds 1e-10 — too large"
        )
    finally:
        driver.quit()
