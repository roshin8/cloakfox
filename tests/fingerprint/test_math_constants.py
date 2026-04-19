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
    svc = Service(log_path=f"{log_dir}/geckodriver.log")
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
def test_math_pi_is_perturbed(tmp_path):
    """Math.PI diverges from the IEEE default."""
    driver = _build_driver(str(tmp_path))
    try:
        state = _read_math(driver)
        assert state["windowMathSameAsMath"], (
            "window.Math !== Math in page scope — spoofer replaced window.Math "
            "but bare Math identifier still resolves to the engine original"
        )
        assert state["pi"] != math.pi, (
            f"Math.PI == IEEE default ({math.pi!r}) — spoofer did not run OR "
            "the per-container noise collapsed to 0. Check math.functions setting."
        )
        assert abs(state["pi"] - math.pi) < 1e-12, (
            f"Math.PI noise ({abs(state['pi'] - math.pi):.2e}) exceeds 1e-12 — "
            "risks breaking numerical code"
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
def test_math_pi_differs_across_domains(tmp_path):
    """Different domains in the same session produce different Math.PI.

    Note: we use different domains rather than different containers because
    the inject script's fallback config path seeds the PRNG from domain only;
    the real per-container seeding runs when the background assigns a container
    profile to the tab, which requires the Multi-Account Containers API to
    route the tab through. Cross-container testing would need either privileged
    Marionette calls to create a container and associate a tab with it, or a
    test-mode pref that forces container-scoped seeding even in the fallback.
    """
    driver = _build_driver(str(tmp_path))
    try:
        pi_a = _read_math(driver, "http://httpbin.org/html")["pi"]
        pi_b = _read_math(driver, "http://example.com/")["pi"]
    finally:
        driver.quit()

    assert pi_a != pi_b, (
        f"Math.PI identical across domains (both {pi_a!r}) — "
        "domain-scoped seeding is not working"
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
